"""
SQLite-backed storage for corpus seeds and crash reports.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fuzzer.core.corpus import SeedInput, SeedMetadata
from fuzzer.observers.input import ParsedCrash


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class FuzzerDatabase:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS corpus (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                data            TEXT    NOT NULL,
                times_picked    INTEGER NOT NULL DEFAULT 0,
                times_fuzzed    INTEGER NOT NULL DEFAULT 0,
                created_at      TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS crashes (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                exception_type      TEXT    NOT NULL,
                exception_message   TEXT    NOT NULL,
                file                TEXT    NOT NULL,
                line                INTEGER NOT NULL,
                traceback           TEXT    NOT NULL,
                bug_category        TEXT    NOT NULL DEFAULT 'unknown',
                category_source     TEXT    NOT NULL DEFAULT 'traceback_fallback',
                data                TEXT    NOT NULL,
                count               INTEGER NOT NULL DEFAULT 1,
                first_seen_at       TEXT    NOT NULL,
                last_seen_at        TEXT    NOT NULL
            );

            CREATE UNIQUE INDEX IF NOT EXISTS crashes_dedup
                ON crashes (exception_type, file, line);
        """)
        self._ensure_crash_category_columns()
        self._conn.commit()

    def _ensure_crash_category_columns(self) -> None:
        """Backfill crash category columns for pre-migration databases."""
        cursor = self._conn.execute("PRAGMA table_info(crashes)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        required_columns = {
            "bug_category": "TEXT NOT NULL DEFAULT 'unknown'",
            "category_source": "TEXT NOT NULL DEFAULT 'traceback_fallback'",
        }

        for col, ddl in required_columns.items():
            if col not in existing_columns:
                self._conn.execute(f"ALTER TABLE crashes ADD COLUMN {col} {ddl}")

    # ------------------------------------------------------------------
    # Corpus
    # ------------------------------------------------------------------

    def save_seed(self, seed: SeedInput) -> None:
        """Persist a new seed to the corpus table."""
        self._conn.execute(
            """
            INSERT INTO corpus (data, times_picked, times_fuzzed, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                seed.data,
                seed.metadata.times_picked,
                seed.metadata.times_fuzzed,
                _now(),
            ),
        )
        self._conn.commit()

    def flush_corpus(self, seeds: list[SeedInput]) -> None:
        """Overwrite all corpus rows with the current in-memory seed state (for resume)."""
        self._conn.execute("DELETE FROM corpus")
        self._conn.executemany(
            "INSERT INTO corpus (data, times_picked, times_fuzzed, created_at) VALUES (?, ?, ?, ?)",
            [
                (s.data, s.metadata.times_picked, s.metadata.times_fuzzed, _now())
                for s in seeds
            ],
        )
        self._conn.commit()

    def load_seeds(self) -> list[SeedInput]:
        """Load all corpus rows as SeedInput objects."""
        rows = self._conn.execute(
            "SELECT data, times_picked, times_fuzzed FROM corpus ORDER BY id"
        ).fetchall()
        return [
            SeedInput(
                data=row["data"],
                metadata=SeedMetadata(
                    times_picked=row["times_picked"],
                    times_fuzzed=row["times_fuzzed"],
                ),
            )
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Crashes
    # ------------------------------------------------------------------

    def record_crash(self, data: str, parsed: ParsedCrash) -> bool:
        """
        Record a crash, deduplicating by (exception_type, file, line).
        Increments count and updates last_seen_at for duplicates.
        Returns True if this is a new unique crash, False if it's a duplicate.
        """
        now = _now()

        existing = self._conn.execute(
            "SELECT id FROM crashes WHERE exception_type = ? AND file = ? AND line = ?",
            (parsed.exception_type, parsed.file, parsed.line),
        ).fetchone()

        if existing:
            self._conn.execute(
                "UPDATE crashes SET count = count + 1, last_seen_at = ? WHERE id = ?",
                (now, existing["id"]),
            )
            self._conn.commit()
            return False
        else:
            self._conn.execute(
                """
                INSERT INTO crashes
                    (
                        exception_type,
                        exception_message,
                        file,
                        line,
                        traceback,
                        bug_category,
                        category_source,
                        data,
                        count,
                        first_seen_at,
                        last_seen_at
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    parsed.exception_type,
                    parsed.exception_message,
                    parsed.file,
                    parsed.line,
                    parsed.traceback,
                    parsed.bug_category,
                    parsed.category_source,
                    data,
                    now,
                    now,
                ),
            )
            self._conn.commit()
            return True

    def close(self) -> None:
        self._conn.close()
