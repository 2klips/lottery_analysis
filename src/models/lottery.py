"""Lottery data models for Pension Lottery 720+."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass
class PensionRound:
    """Represents a single Pension Lottery 720+ draw result."""

    round_number: int
    draw_date: date
    group: int
    numbers: list[int]
    bonus_numbers: list[int]
    day_of_week: int = field(init=False)
    month: int = field(init=False)
    week_of_year: int = field(init=False)
    digit_sum: int = field(init=False)
    bonus_digit_sum: int = field(init=False)

    def __post_init__(self) -> None:
        """Validate fields and populate derived attributes."""
        if not 1 <= self.group <= 5:
            msg = "group must be between 1 and 5"
            raise ValueError(msg)

        self._validate_digits(self.numbers, "numbers")
        self._validate_digits(self.bonus_numbers, "bonus_numbers")

        self.day_of_week = self.draw_date.weekday()
        self.month = self.draw_date.month
        self.week_of_year = self.draw_date.isocalendar().week
        self.digit_sum = sum(self.numbers)
        self.bonus_digit_sum = sum(self.bonus_numbers)

    @staticmethod
    def _validate_digits(values: list[int], field_name: str) -> None:
        """Validate a lottery digit list.

        Args:
            values: Digit list to validate.
            field_name: Human-readable field name for errors.

        Raises:
            ValueError: If length is not 6 or any digit is outside 0-9.
        """
        if len(values) != 6:
            msg = f"{field_name} must have exactly 6 digits"
            raise ValueError(msg)

        for digit in values:
            if not 0 <= digit <= 9:
                msg = f"{field_name} digits must be between 0 and 9"
                raise ValueError(msg)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the round model to a dictionary.

        Returns:
            JSON-serializable dictionary of all fields.
        """
        return {
            "round_number": self.round_number,
            "draw_date": self.draw_date.isoformat(),
            "group": self.group,
            "numbers": self.numbers,
            "bonus_numbers": self.bonus_numbers,
            "day_of_week": self.day_of_week,
            "month": self.month,
            "week_of_year": self.week_of_year,
            "digit_sum": self.digit_sum,
            "bonus_digit_sum": self.bonus_digit_sum,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PensionRound | None:
        """Deserialize a dictionary into a ``PensionRound``.

        Args:
            data: Serialized lottery round dictionary.

        Returns:
            ``PensionRound`` instance when valid, otherwise ``None``.
        """
        try:
            return cls(
                round_number=int(data["round_number"]),
                draw_date=date.fromisoformat(str(data["draw_date"])),
                group=int(data["group"]),
                numbers=[int(value) for value in data["numbers"]],
                bonus_numbers=[int(value) for value in data["bonus_numbers"]],
            )
        except (KeyError, TypeError, ValueError):
            return None

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> PensionRound:
        """Create from API response.

        API fields:
        - psltEpsd: round number (int)
        - psltRflYmd: draw date as "YYYYMMDD" string
        - wnBndNo: group number as string "1"-"5"
        - wnRnkVl: winning 6-digit number as string like "920388"
        - bnsRnkVl: bonus 6-digit number as string like "752744"

        Args:
            data: Single round JSON record from lottery API.

        Returns:
            Parsed ``PensionRound`` instance.
        """
        draw_date = datetime.strptime(str(data["psltRflYmd"]), "%Y%m%d").date()
        numbers_str = str(data["wnRnkVl"])
        bonus_numbers_str = str(data["bnsRnkVl"])

        return cls(
            round_number=int(data["psltEpsd"]),
            draw_date=draw_date,
            group=int(data["wnBndNo"]),
            numbers=[int(char) for char in numbers_str],
            bonus_numbers=[int(char) for char in bonus_numbers_str],
        )
