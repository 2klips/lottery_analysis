"""SQLite storage layer for Pension Lottery 720+ data."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ..models.lottery import PensionRound
from ..utils.logging_config import get_logger

DB_PATH = Path(__file__).parent.parent.parent / "data" / "lottery.db"
PROGRESS_PATH = Path(__file__).parent.parent.parent / "data" / "progress.json"

logger = get_logger(__name__)


class LotteryDatabase:
    """Manage lottery data persistence in SQLite and JSON progress files."""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        """Initialize database connection and schema.

        Args:
            db_path: SQLite database file path.
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        """Create required database tables if they do not exist."""
        query = """
        CREATE TABLE IF NOT EXISTS pension_rounds (
            round_number INTEGER PRIMARY KEY,
            draw_date TEXT NOT NULL,
            group_number INTEGER NOT NULL,
            num_1 INTEGER NOT NULL,
            num_2 INTEGER NOT NULL,
            num_3 INTEGER NOT NULL,
            num_4 INTEGER NOT NULL,
            num_5 INTEGER NOT NULL,
            num_6 INTEGER NOT NULL,
            bonus_1 INTEGER NOT NULL,
            bonus_2 INTEGER NOT NULL,
            bonus_3 INTEGER NOT NULL,
            bonus_4 INTEGER NOT NULL,
            bonus_5 INTEGER NOT NULL,
            bonus_6 INTEGER NOT NULL,
            day_of_week INTEGER,
            month INTEGER,
            week_of_year INTEGER,
            digit_sum INTEGER,
            bonus_digit_sum INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
        self.connection.execute(query)
        self.connection.commit()

    def insert_round(self, round_data: PensionRound) -> bool:
        """Insert a single round.

        Args:
            round_data: Round model to insert.

        Returns:
            ``True`` if inserted, ``False`` if already exists.
        """
        query = """
        INSERT OR IGNORE INTO pension_rounds (
            round_number, draw_date, group_number,
            num_1, num_2, num_3, num_4, num_5, num_6,
            bonus_1, bonus_2, bonus_3, bonus_4, bonus_5, bonus_6,
            day_of_week, month, week_of_year, digit_sum, bonus_digit_sum
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        cursor = self.connection.execute(
            query,
            (
                round_data.round_number,
                round_data.draw_date.isoformat(),
                round_data.group,
                *round_data.numbers,
                *round_data.bonus_numbers,
                round_data.day_of_week,
                round_data.month,
                round_data.week_of_year,
                round_data.digit_sum,
                round_data.bonus_digit_sum,
            ),
        )
        self.connection.commit()
        return cursor.rowcount > 0

    def insert_rounds(self, rounds: list[PensionRound]) -> int:
        """Bulk insert rounds.

        Args:
            rounds: List of round models.

        Returns:
            Count of newly inserted rows.
        """
        query = """
        INSERT OR IGNORE INTO pension_rounds (
            round_number, draw_date, group_number,
            num_1, num_2, num_3, num_4, num_5, num_6,
            bonus_1, bonus_2, bonus_3, bonus_4, bonus_5, bonus_6,
            day_of_week, month, week_of_year, digit_sum, bonus_digit_sum
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        rows = [
            (
                item.round_number,
                item.draw_date.isoformat(),
                item.group,
                *item.numbers,
                *item.bonus_numbers,
                item.day_of_week,
                item.month,
                item.week_of_year,
                item.digit_sum,
                item.bonus_digit_sum,
            )
            for item in rounds
        ]
        before_changes = self.connection.total_changes
        self.connection.executemany(query, rows)
        self.connection.commit()
        return self.connection.total_changes - before_changes

    def get_round(self, round_number: int) -> PensionRound | None:
        """Get a specific round by number.

        Args:
            round_number: Round number to retrieve.

        Returns:
            Matching ``PensionRound`` or ``None``.
        """
        query = "SELECT * FROM pension_rounds WHERE round_number = ?"
        row = self.connection.execute(query, (round_number,)).fetchone()
        if row is None:
            return None
        return self._row_to_round(row)

    def get_all_rounds(self) -> list[PensionRound]:
        """Get all rounds sorted by round number.

        Returns:
            List of all stored rounds.
        """
        query = "SELECT * FROM pension_rounds ORDER BY round_number ASC"
        rows = self.connection.execute(query).fetchall()
        return [self._row_to_round(row) for row in rows]

    def get_latest_round_number(self) -> int | None:
        """Get the highest round number in storage.

        Returns:
            Latest round number or ``None`` if no data.
        """
        query = "SELECT MAX(round_number) AS latest_round FROM pension_rounds"
        row = self.connection.execute(query).fetchone()
        if row is None or row["latest_round"] is None:
            return None
        return int(row["latest_round"])

    def get_round_count(self) -> int:
        """Get total number of stored rounds.

        Returns:
            Count of records in ``pension_rounds``.
        """
        query = "SELECT COUNT(*) AS cnt FROM pension_rounds"
        row = self.connection.execute(query).fetchone()
        return int(row["cnt"]) if row is not None else 0

    def save_progress(self, last_round: int) -> None:
        """Save collection progress to JSON file.

        Args:
            last_round: Last successfully collected round number.
        """
        PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {"last_round": last_round}
        PROGRESS_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load_progress(self) -> int | None:
        """Load last successful round from progress file.

        Returns:
            Last round number or ``None`` if file missing/invalid.
        """
        if not PROGRESS_PATH.exists():
            return None

        try:
            content = PROGRESS_PATH.read_text(encoding="utf-8")
            payload = json.loads(content)
            return int(payload["last_round"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            logger.warning("Failed to load progress file: %s", error)
            return None

    def close(self) -> None:
        """Close database connection."""
        self.connection.close()

    def export_to_json(self, filepath: Path) -> int:
        """Export all rounds to JSON file.

        Args:
            filepath: Destination JSON path.

        Returns:
            Number of exported rounds.
        """
        rounds = self.get_all_rounds()
        filepath.parent.mkdir(parents=True, exist_ok=True)
        payload = [round_item.to_dict() for round_item in rounds]
        filepath.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return len(payload)

    @staticmethod
    def _row_to_round(row: sqlite3.Row) -> PensionRound:
        """Convert SQLite row into ``PensionRound`` model.

        Args:
            row: Database row from ``pension_rounds``.

        Returns:
            Parsed round model.
        """
        data = {
            "round_number": int(row["round_number"]),
            "draw_date": str(row["draw_date"]),
            "group": int(row["group_number"]),
            "numbers": [
                int(row["num_1"]),
                int(row["num_2"]),
                int(row["num_3"]),
                int(row["num_4"]),
                int(row["num_5"]),
                int(row["num_6"]),
            ],
            "bonus_numbers": [
                int(row["bonus_1"]),
                int(row["bonus_2"]),
                int(row["bonus_3"]),
                int(row["bonus_4"]),
                int(row["bonus_5"]),
                int(row["bonus_6"]),
            ],
        }
        round_item = PensionRound.from_dict(data)
        if round_item is None:
            msg = f"Invalid row data for round {row['round_number']}"
            raise ValueError(msg)
        return round_item
