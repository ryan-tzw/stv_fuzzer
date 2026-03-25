"""
SQLite-backed storage for corpus seeds and crash reports.
"""

import sqlite3
import re
from datetime import datetime, timezone
from pathlib import Path

from fuzzer.corpus import SeedInput, SeedMetadata
from fuzzer.observers.input import ParsedCrash


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_exception_message(message: str) -> str:
    """Normalize crash messages for stable deduplication across minor formatting noise."""
    text = _WHITESPACE_RE.sub(" ", message or "")
    return text.strip().lower()


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
                dedup_key           TEXT,
                data                TEXT    NOT NULL,
                count               INTEGER NOT NULL DEFAULT 1,
                first_seen_at       TEXT    NOT NULL,
                last_seen_at        TEXT    NOT NULL
            );
        """)
        self._migrate_crash_schema()
        self._conn.commit()

    def _migrate_crash_schema(self) -> None:
        """Apply forward-only schema migrations for crash metadata and dedup."""
        cursor = self._conn.execute("PRAGMA table_info(crashes)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        required_columns = {
            "bug_category": "TEXT NOT NULL DEFAULT 'unknown'",
            "category_source": "TEXT NOT NULL DEFAULT 'traceback_fallback'",
            "dedup_key": "TEXT",
        }

        for col, ddl in required_columns.items():
            if col not in existing_columns:
                self._conn.execute(f"ALTER TABLE crashes ADD COLUMN {col} {ddl}")

        # Replace legacy coarse dedup index with semantic fingerprint dedup.
        self._conn.execute("DROP INDEX IF EXISTS crashes_dedup")
        self._conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS crashes_dedup_key ON crashes (dedup_key)"
        )

    @staticmethod
    def _build_dedup_key(parsed: ParsedCrash) -> str:
        category = (parsed.bug_category or "").strip().lower()
        exc_type = (parsed.exception_type or "").strip()
        file_path = (parsed.file or "").strip()
        line = parsed.line
        if parsed.category_source == "final_bug_count":
            return f"{category}|{exc_type}|{file_path}|{line}"

        normalized_message = _normalize_exception_message(parsed.exception_message)
        return f"{category}|{exc_type}|{file_path}|{line}|{normalized_message}"

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
        Record a crash using semantic dedup key:
        (bug_category, exception_type, file, line, normalized_exception_message).
        Increments count and updates last_seen_at for duplicates.
        Returns True if this is a new unique crash, False if it's a duplicate.
        """
        now = _now()
        dedup_key = self._build_dedup_key(parsed)

        existing = self._conn.execute(
            "SELECT id FROM crashes WHERE dedup_key = ?",
            (dedup_key,),
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
                        dedup_key,
                        data,
                        count,
                        first_seen_at,
                        last_seen_at
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    parsed.exception_type,
                    parsed.exception_message,
                    parsed.file,
                    parsed.line,
                    parsed.traceback,
                    parsed.bug_category,
                    parsed.category_source,
                    dedup_key,
                    data,
                    now,
                    now,
                ),
            )
            self._conn.commit()
            return True

    def close(self) -> None:
        self._conn.close()
