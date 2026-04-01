"""Parser utilities for Pension Lottery 720+ responses."""

from __future__ import annotations

import json

from bs4 import BeautifulSoup

from ..models.lottery import PensionRound
from ..utils.logging_config import get_logger

logger = get_logger(__name__)


class LotteryParser:
    """Parse HTML/JSON responses from the lottery endpoints."""

    @staticmethod
    def parse_latest_round(html: str) -> int | None:
        """Parse latest round number from main page HTML.

        The main page has: ``<strong id="drwNo720">308</strong>``

        Args:
            html: Main page HTML source.

        Returns:
            Parsed round number, or ``None`` when not found.
        """
        soup = BeautifulSoup(html, "lxml")
        tag = soup.select_one("strong#drwNo720")

        if tag is None:
            return None

        text = tag.text.strip()
        return int(text) if text.isdigit() else None

    @staticmethod
    def parse_round_list(json_text: str) -> list[PensionRound]:
        """Parse the round list API response into ``PensionRound`` objects.

        Args:
            json_text: Raw JSON response text.

        Returns:
            Round list sorted by ``round_number`` ascending.
        """
        records = LotteryParser._extract_result_list(json_text)
        rounds: list[PensionRound] = []

        for record in records:
            if not isinstance(record, dict):
                continue

            try:
                rounds.append(PensionRound.from_api_response(record))
            except (KeyError, TypeError, ValueError) as error:
                logger.warning("Skipping invalid round record: %s", error)

        return sorted(rounds, key=lambda item: item.round_number)

    @staticmethod
    def parse_round_detail(json_text: str) -> dict[str, object] | None:
        """Parse round detail API response for additional data.

        Args:
            json_text: Raw JSON response text from detail endpoint.

        Returns:
            First detail record as dictionary, or ``None`` when unavailable.
        """
        records = LotteryParser._extract_result_list(json_text)
        if not records:
            return None

        first_record = records[0]
        return first_record if isinstance(first_record, dict) else None

    @staticmethod
    def parse_winner_info(json_text: str) -> dict[str, object] | None:
        """Parse winner count API response.

        Args:
            json_text: Raw JSON response text from winner endpoint.

        Returns:
            Dictionary containing winner ranks for the requested round,
            or ``None`` if parsing fails.
        """
        records = LotteryParser._extract_result_list(json_text)
        if not records:
            return None

        cleaned_records = [item for item in records if isinstance(item, dict)]
        if not cleaned_records:
            return None

        round_number = cleaned_records[0].get("ltEpsd")
        return {"round_number": round_number, "winner_ranks": cleaned_records}

    @staticmethod
    def parse_all_sets(json_text: str) -> list[PensionRound]:
        """Parse all 6 winning number sets from the detail API response.

        Groups the 48 records into 6 sets of 8, extracts 1등 number + bonus from
        each set, and returns valid ``PensionRound`` objects.

        Args:
            json_text: Raw JSON response text from detail endpoint.

        Returns:
            Up to 6 parsed winning sets for a single round.
        """
        records = LotteryParser._extract_result_list(json_text)
        dict_records = [record for record in records if isinstance(record, dict)]
        rounds: list[PensionRound] = []

        for start_idx in range(0, len(dict_records), 8):
            set_records = dict_records[start_idx:start_idx + 8]
            if len(set_records) < 8:
                continue

            first_rank = next(
                (
                    record
                    for record in set_records
                    if record.get("wnBndNo") not in (None, "")
                ),
                None,
            )
            if first_rank is None:
                continue

            bonus = next(
                (
                    record
                    for record in set_records
                    if LotteryParser._is_bonus_record(record)
                ),
                set_records[-1],
            )

            numbers_str = str(first_rank.get("wnRnkVl", ""))
            bonus_str = str(bonus.get("wnRnkVl", ""))
            if len(numbers_str) != 6 or len(bonus_str) != 6:
                continue

            data = {
                "psltEpsd": first_rank.get("psltEpsd"),
                "psltRflYmd": first_rank.get("psltRflYmd"),
                "wnBndNo": first_rank.get("wnBndNo"),
                "wnRnkVl": numbers_str,
                "bnsRnkVl": bonus_str,
            }

            try:
                rounds.append(PensionRound.from_api_response(data))
            except (KeyError, TypeError, ValueError) as error:
                logger.warning("Skipping invalid detailed set record: %s", error)

        return rounds

    @staticmethod
    def _extract_result_list(json_text: str) -> list[object]:
        """Extract result list from varying API response structures.

        Args:
            json_text: Raw JSON payload.

        Returns:
            List-like result payload. Empty list when not found.
        """
        try:
            payload = json.loads(json_text)
        except json.JSONDecodeError as error:
            logger.error("Invalid JSON payload: %s", error)
            return []

        if isinstance(payload, list):
            return payload

        if not isinstance(payload, dict):
            return []

        result = payload.get("result")
        if isinstance(result, list):
            return result

        data = payload.get("data")
        if isinstance(data, dict):
            nested_result = data.get("result")
            if isinstance(nested_result, list):
                return nested_result

        return []

    @staticmethod
    def _is_bonus_record(record: dict[object, object]) -> bool:
        """Return whether a detail row represents bonus digits."""
        wn_rank_value = str(record.get("wnRnkVl", ""))
        if len(wn_rank_value) != 6:
            return False

        wn_bnd_no = record.get("wnBndNo")
        if wn_bnd_no not in (None, ""):
            return False

        wn_sq_no = record.get("wnSqNo")
        if str(wn_sq_no) == "8":
            return True

        return str(record.get("wnAmt")) == "120000000"
