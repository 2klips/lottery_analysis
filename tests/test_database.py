"""Unit tests for lottery database storage."""

from datetime import date
from pathlib import Path

import pytest

from src.models.lottery import PensionRound
from src.storage.database import LotteryDatabase


@pytest.fixture()
def sample_round() -> PensionRound:
    """Create a sample PensionRound for testing."""
    return PensionRound(
        round_number=1,
        draw_date=date(2020, 5, 7),
        group=4,
        numbers=[1, 6, 2, 1, 3, 2],
        bonus_numbers=[2, 7, 8, 2, 3, 9],
    )


@pytest.fixture()
def db(tmp_path: Path) -> LotteryDatabase:
    """Create an in-memory-like database in temp directory."""
    db_path = tmp_path / "test.db"
    database = LotteryDatabase(db_path=db_path)
    yield database
    database.close()


class TestLotteryDatabase:
    """Test LotteryDatabase CRUD operations."""

    def test_insert_round(self, db: LotteryDatabase, sample_round: PensionRound) -> None:
        """Insert a single round successfully."""
        assert db.insert_round(sample_round) is True
        assert db.get_round_count() == 1

    def test_insert_duplicate_ignored(self, db: LotteryDatabase, sample_round: PensionRound) -> None:
        """Duplicate insert returns False and count stays 1."""
        db.insert_round(sample_round)
        assert db.insert_round(sample_round) is False
        assert db.get_round_count() == 1

    def test_get_round(self, db: LotteryDatabase, sample_round: PensionRound) -> None:
        """Retrieve a round by number."""
        db.insert_round(sample_round)
        result = db.get_round(1)
        assert result is not None
        assert result.round_number == 1
        assert result.group == 4
        assert result.numbers == [1, 6, 2, 1, 3, 2]

    def test_get_round_missing(self, db: LotteryDatabase) -> None:
        """Missing round returns None."""
        assert db.get_round(999) is None

    def test_get_all_rounds(self, db: LotteryDatabase) -> None:
        """Get all rounds sorted by round_number."""
        rounds = [
            PensionRound(round_number=3, draw_date=date(2020, 5, 21), group=4,
                         numbers=[5, 4, 4, 9, 5, 5], bonus_numbers=[6, 1, 3, 3, 6, 9]),
            PensionRound(round_number=1, draw_date=date(2020, 5, 7), group=4,
                         numbers=[1, 6, 2, 1, 3, 2], bonus_numbers=[2, 7, 8, 2, 3, 9]),
        ]
        db.insert_rounds(rounds)
        result = db.get_all_rounds()
        assert len(result) == 2
        assert result[0].round_number == 1
        assert result[1].round_number == 3

    def test_get_latest_round_number(self, db: LotteryDatabase, sample_round: PensionRound) -> None:
        """Get the highest round number."""
        db.insert_round(sample_round)
        assert db.get_latest_round_number() == 1

    def test_get_latest_round_number_empty(self, db: LotteryDatabase) -> None:
        """Empty database returns None."""
        assert db.get_latest_round_number() is None

    def test_bulk_insert(self, db: LotteryDatabase) -> None:
        """Bulk insert multiple rounds."""
        rounds = [
            PensionRound(round_number=i, draw_date=date(2020, 5, 7 + i * 7), group=(i % 5) + 1,
                         numbers=[i % 10] * 6, bonus_numbers=[0] * 6)
            for i in range(1, 4)
        ]
        count = db.insert_rounds(rounds)
        assert count == 3
        assert db.get_round_count() == 3

    def test_progress_save_load(self, db: LotteryDatabase, tmp_path: Path) -> None:
        """Save and load progress."""
        db.save_progress(42)
        assert db.load_progress() == 42

    def test_export_json(self, db: LotteryDatabase, sample_round: PensionRound, tmp_path: Path) -> None:
        """Export rounds to JSON file."""
        db.insert_round(sample_round)
        export_path = tmp_path / "export.json"
        count = db.export_to_json(export_path)
        assert count == 1
        assert export_path.exists()
