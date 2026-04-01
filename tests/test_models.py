"""Unit tests for lottery data models."""

from datetime import date

import pytest

from src.models.lottery import PensionRound


class TestPensionRound:
    """Test PensionRound dataclass."""

    def test_valid_creation(self) -> None:
        """Create a valid PensionRound instance."""
        r = PensionRound(
            round_number=1,
            draw_date=date(2020, 5, 7),
            group=4,
            numbers=[1, 6, 2, 1, 3, 2],
            bonus_numbers=[2, 7, 8, 2, 3, 9],
        )
        assert r.round_number == 1
        assert r.group == 4
        assert r.numbers == [1, 6, 2, 1, 3, 2]
        assert r.digit_sum == 15
        assert r.bonus_digit_sum == 31
        assert r.day_of_week == 3  # Thursday

    def test_invalid_group_raises(self) -> None:
        """Group outside 1-5 raises ValueError."""
        with pytest.raises(ValueError, match="group"):
            PensionRound(
                round_number=1,
                draw_date=date(2020, 5, 7),
                group=0,
                numbers=[1, 2, 3, 4, 5, 6],
                bonus_numbers=[0, 0, 0, 0, 0, 0],
            )

    def test_invalid_digit_raises(self) -> None:
        """Digit outside 0-9 raises ValueError."""
        with pytest.raises(ValueError, match="digits must be"):
            PensionRound(
                round_number=1,
                draw_date=date(2020, 5, 7),
                group=1,
                numbers=[1, 2, 3, 4, 5, 10],
                bonus_numbers=[0, 0, 0, 0, 0, 0],
            )

    def test_wrong_length_raises(self) -> None:
        """Numbers list not length 6 raises ValueError."""
        with pytest.raises(ValueError, match="exactly 6"):
            PensionRound(
                round_number=1,
                draw_date=date(2020, 5, 7),
                group=1,
                numbers=[1, 2, 3],
                bonus_numbers=[0, 0, 0, 0, 0, 0],
            )

    def test_to_dict_roundtrip(self) -> None:
        """to_dict and from_dict roundtrip preserves data."""
        original = PensionRound(
            round_number=42,
            draw_date=date(2021, 2, 18),
            group=4,
            numbers=[9, 7, 4, 2, 3, 1],
            bonus_numbers=[8, 9, 2, 2, 4, 3],
        )
        data = original.to_dict()
        restored = PensionRound.from_dict(data)

        assert restored is not None
        assert restored.round_number == original.round_number
        assert restored.numbers == original.numbers
        assert restored.bonus_numbers == original.bonus_numbers

    def test_from_api_response(self) -> None:
        """from_api_response correctly parses API format."""
        api_data = {
            "psltEpsd": 42,
            "psltRflYmd": "20210218",
            "wnBndNo": "4",
            "wnRnkVl": "974231",
            "bnsRnkVl": "892243",
        }
        r = PensionRound.from_api_response(api_data)
        assert r.round_number == 42
        assert r.group == 4
        assert r.numbers == [9, 7, 4, 2, 3, 1]
        assert r.bonus_numbers == [8, 9, 2, 2, 4, 3]
        assert r.draw_date == date(2021, 2, 18)

    def test_from_dict_invalid_returns_none(self) -> None:
        """from_dict with invalid data returns None."""
        assert PensionRound.from_dict({"bad": "data"}) is None
