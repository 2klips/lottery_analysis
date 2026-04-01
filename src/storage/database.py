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
    """Manage lottery persistence in SQLite and progress JSON."""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS pension_rounds (
                round_number INTEGER PRIMARY KEY,
                draw_date TEXT NOT NULL,
                group_number INTEGER NOT NULL,
                num_1 INTEGER NOT NULL, num_2 INTEGER NOT NULL, num_3 INTEGER NOT NULL,
                num_4 INTEGER NOT NULL, num_5 INTEGER NOT NULL, num_6 INTEGER NOT NULL,
                bonus_1 INTEGER NOT NULL, bonus_2 INTEGER NOT NULL, bonus_3 INTEGER NOT NULL,
                bonus_4 INTEGER NOT NULL, bonus_5 INTEGER NOT NULL, bonus_6 INTEGER NOT NULL,
                day_of_week INTEGER, month INTEGER, week_of_year INTEGER,
                digit_sum INTEGER, bonus_digit_sum INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS pension_round_sets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                round_number INTEGER NOT NULL,
                set_number INTEGER NOT NULL,
                draw_date TEXT NOT NULL,
                group_number INTEGER NOT NULL,
                num_1 INTEGER NOT NULL, num_2 INTEGER NOT NULL, num_3 INTEGER NOT NULL,
                num_4 INTEGER NOT NULL, num_5 INTEGER NOT NULL, num_6 INTEGER NOT NULL,
                bonus_1 INTEGER NOT NULL, bonus_2 INTEGER NOT NULL, bonus_3 INTEGER NOT NULL,
                bonus_4 INTEGER NOT NULL, bonus_5 INTEGER NOT NULL, bonus_6 INTEGER NOT NULL,
                day_of_week INTEGER, month INTEGER, week_of_year INTEGER,
                digit_sum INTEGER, bonus_digit_sum INTEGER,
                winner_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(round_number, set_number)
            )
            """
        )
        self.connection.commit()

    def insert_round(self, round_data: PensionRound) -> bool:
        cursor = self.connection.execute(
            """
            INSERT OR IGNORE INTO pension_rounds (
                round_number, draw_date, group_number,
                num_1, num_2, num_3, num_4, num_5, num_6,
                bonus_1, bonus_2, bonus_3, bonus_4, bonus_5, bonus_6,
                day_of_week, month, week_of_year, digit_sum, bonus_digit_sum
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self._round_tuple(round_data),
        )
        self.connection.commit()
        return cursor.rowcount > 0

    def insert_rounds(self, rounds: list[PensionRound]) -> int:
        rows = [self._round_tuple(item) for item in rounds]
        before_changes = self.connection.total_changes
        self.connection.executemany(
            """
            INSERT OR IGNORE INTO pension_rounds (
                round_number, draw_date, group_number,
                num_1, num_2, num_3, num_4, num_5, num_6,
                bonus_1, bonus_2, bonus_3, bonus_4, bonus_5, bonus_6,
                day_of_week, month, week_of_year, digit_sum, bonus_digit_sum
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        self.connection.commit()
        return self.connection.total_changes - before_changes

    def insert_round_set(self, round_data: PensionRound, set_number: int, winner_count: int = 0) -> bool:
        cursor = self.connection.execute(
            """
            INSERT OR IGNORE INTO pension_round_sets (
                round_number, set_number, draw_date, group_number,
                num_1, num_2, num_3, num_4, num_5, num_6,
                bonus_1, bonus_2, bonus_3, bonus_4, bonus_5, bonus_6,
                day_of_week, month, week_of_year, digit_sum, bonus_digit_sum, winner_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self._round_set_tuple(round_data, set_number, winner_count),
        )
        self.connection.commit()
        return cursor.rowcount > 0

    def insert_round_sets(self, sets: list[tuple[PensionRound, int, int]]) -> int:
        rows = [self._round_set_tuple(round_data, set_number, winner_count) for round_data, set_number, winner_count in sets]
        before_changes = self.connection.total_changes
        self.connection.executemany(
            """
            INSERT OR IGNORE INTO pension_round_sets (
                round_number, set_number, draw_date, group_number,
                num_1, num_2, num_3, num_4, num_5, num_6,
                bonus_1, bonus_2, bonus_3, bonus_4, bonus_5, bonus_6,
                day_of_week, month, week_of_year, digit_sum, bonus_digit_sum, winner_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        self.connection.commit()
        return self.connection.total_changes - before_changes

    def get_round(self, round_number: int) -> PensionRound | None:
        row = self.connection.execute("SELECT * FROM pension_rounds WHERE round_number = ?", (round_number,)).fetchone()
        return None if row is None else self._row_to_round(row)

    def get_all_rounds(self) -> list[PensionRound]:
        rows = self.connection.execute("SELECT * FROM pension_rounds ORDER BY round_number ASC").fetchall()
        return [self._row_to_round(row) for row in rows]

    def get_all_round_sets(self) -> list[PensionRound]:
        rows = self.connection.execute(
            "SELECT * FROM pension_round_sets ORDER BY round_number ASC, set_number ASC"
        ).fetchall()
        return [self._row_to_round(row) for row in rows]

    def get_round_numbers_missing_sets(self) -> list[int]:
        rows = self.connection.execute(
            """
            SELECT pr.round_number
            FROM pension_rounds pr
            LEFT JOIN (
                SELECT round_number, COUNT(*) AS set_cnt
                FROM pension_round_sets
                GROUP BY round_number
            ) prs ON prs.round_number = pr.round_number
            WHERE COALESCE(prs.set_cnt, 0) < 6
            ORDER BY pr.round_number ASC
            """
        ).fetchall()
        return [int(row["round_number"]) for row in rows]

    def get_latest_round_number(self) -> int | None:
        row = self.connection.execute("SELECT MAX(round_number) AS latest_round FROM pension_rounds").fetchone()
        if row is None or row["latest_round"] is None:
            return None
        return int(row["latest_round"])

    def get_round_count(self) -> int:
        row = self.connection.execute("SELECT COUNT(*) AS cnt FROM pension_rounds").fetchone()
        return int(row["cnt"]) if row is not None else 0

    def get_round_set_count(self) -> int:
        row = self.connection.execute("SELECT COUNT(*) AS cnt FROM pension_round_sets").fetchone()
        return int(row["cnt"]) if row is not None else 0

    def save_progress(self, last_round: int) -> None:
        PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {"last_round": last_round}
        PROGRESS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_progress(self) -> int | None:
        if not PROGRESS_PATH.exists():
            return None
        try:
            return int(json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))["last_round"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            logger.warning("Failed to load progress file: %s", error)
            return None

    def close(self) -> None:
        self.connection.close()

    def export_to_json(self, filepath: Path) -> int:
        rounds = self.get_all_rounds()
        filepath.parent.mkdir(parents=True, exist_ok=True)
        payload = [round_item.to_dict() for round_item in rounds]
        filepath.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return len(payload)

    @staticmethod
    def _round_tuple(round_data: PensionRound) -> tuple[object, ...]:
        return (
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
        )

    @staticmethod
    def _round_set_tuple(
        round_data: PensionRound,
        set_number: int,
        winner_count: int,
    ) -> tuple[object, ...]:
        return (
            round_data.round_number,
            set_number,
            round_data.draw_date.isoformat(),
            round_data.group,
            *round_data.numbers,
            *round_data.bonus_numbers,
            round_data.day_of_week,
            round_data.month,
            round_data.week_of_year,
            round_data.digit_sum,
            round_data.bonus_digit_sum,
            winner_count,
        )

    @staticmethod
    def _row_to_round(row: sqlite3.Row) -> PensionRound:
        round_item = PensionRound.from_dict(
            {
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
        )
        if round_item is None:
            msg = f"Invalid row data for round {row['round_number']}"
            raise ValueError(msg)
        return round_item
