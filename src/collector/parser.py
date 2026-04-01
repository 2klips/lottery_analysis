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
