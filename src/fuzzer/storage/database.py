"""
SQLite-backed storage for corpus seeds and crash reports.
"""

import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fuzzer.corpus import SeedInput, SeedMetadata
from fuzzer.metrics.metrics import MetricsSnapshot
from fuzzer.observers.input import ParsedCrash


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_WHITESPACE_RE = re.compile(r"\s+")
_JSON_POS_SUFFIX_RE = re.compile(
    r":\s*line\s+\d+\s+column\s+\d+\s*\(char\s+\d+\)\s*$",
    flags=re.IGNORECASE,
)
_CONTEXTUAL_NUMBER_RE = re.compile(
    r"\b(?P<label>line|column|char|offset|position)\s+(?P<num>\d+)\b",
    flags=re.IGNORECASE,
)
_LARGE_NUMBER_RE = re.compile(r"\b\d{3,}\b")


def _normalize_exception_message(message: str) -> str:
    """Normalize crash messages for stable deduplication across minor formatting noise."""
    return _canonicalize_exception_message("", message)


def _canonicalize_exception_message(exception_type: str, message: str) -> str:
    """Canonicalize volatile message fields while preserving semantic error distinctions."""
    text = message or ""
    lowered_exc = (exception_type or "").split(".")[-1].strip().lower()

    # Normalize context-dependent positions in parser-style messages.
    text = _CONTEXTUAL_NUMBER_RE.sub(lambda m: f"{m.group('label')} <n>", text)
    text = _LARGE_NUMBER_RE.sub("<n>", text)

    # JSONDecodeError appends dynamic offset suffixes which should not define uniqueness.
    if lowered_exc == "jsondecodeerror":
        text = _JSON_POS_SUFFIX_RE.sub("", text)

    text = _WHITESPACE_RE.sub(" ", text)
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

            CREATE TABLE IF NOT EXISTS fuzzer_metrics (
                id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp             TEXT     NOT NULL,
                corpus_size           INTEGER  NOT NULL,
                interesting_seed      INTEGER  NOT NULL,
                unique_crashes        INTEGER  NOT NULL,
                total_crashes         INTEGER  NOT NULL,
                line_coverage         INTEGER  NOT NULL DEFAULT 0,
                branch_coverage       INTEGER  NOT NULL DEFAULT 0,
                total_edges           INTEGER  NOT NULL,
                executions            INTEGER  NOT NULL,
                executions_per_sec    REAL     NOT NULL
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
        normalized_exc_type = exc_type.split(".")[-1].lower()
        file_path = (parsed.file or "").strip()
        line = parsed.line
        if parsed.category_source == "final_bug_count":
            return f"{category}|{exc_type}|{file_path}|{line}"
        if normalized_exc_type in {"addrformaterror", "jsondecodeerror"}:
            return f"{category}|{normalized_exc_type}|{file_path}|{line}"

        normalized_message = _canonicalize_exception_message(
            parsed.exception_type, parsed.exception_message
        )
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
    # Metrics
    # ------------------------------------------------------------------

    def record_metrics(self, metrics: MetricsSnapshot) -> None:
        self._conn.execute(
            """
            INSERT INTO fuzzer_metrics (
                timestamp,
                corpus_size,
                interesting_seed,
                unique_crashes,
                total_crashes,
                line_coverage,
                branch_coverage,
                total_edges,
                executions,
                executions_per_sec
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                metrics.timestamp,
                metrics.corpus_size,
                metrics.interesting_seed,
                metrics.unique_crashes,
                metrics.total_crashes,
                metrics.line_coverage,
                metrics.branch_coverage,
                metrics.total_edges,
                metrics.executions,
                metrics.execs_per_sec,
            ),
        )
        self._conn.commit()

    def get_last_metrics(self) -> dict:
        cursor = self._conn.execute(
            "SELECT * FROM fuzzer_metrics ORDER BY timestamp DESC LIMIT 1"
        )
        row = cursor.fetchone()

        if row is None:
            return {}

        columns = [col[0] for col in cursor.description]
        return dict(zip(columns, row))

    def get_coverage_data(self) -> list[tuple[str, int]]:
        rows = self._conn.execute(
            "SELECT timestamp, total_edges FROM fuzzer_metrics ORDER BY timestamp"
        )
        return [(ts, edges) for ts, edges in rows]

    def get_unique_bugs_data(self) -> list[tuple[str, int]]:
        rows = self._conn.execute(
            "SELECT timestamp, unique_crashes FROM fuzzer_metrics ORDER BY timestamp"
        )
        return [(ts, uniq) for ts, uniq in rows]

    def get_interesting_data(self) -> list[tuple[str, int]]:
        rows = self._conn.execute(
            "SELECT timestamp, interesting_seed FROM fuzzer_metrics ORDER BY timestamp"
        )
        return [(ts, seed) for ts, seed in rows]

    def get_corpus_size(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM corpus").fetchone()
        return int(row[0]) if row is not None else 0

    def get_latest_metrics_summary(self) -> dict[str, object]:
        row = self._conn.execute(
            """
            SELECT
                executions,
                corpus_size,
                unique_crashes,
                line_coverage,
                branch_coverage,
                total_edges,
                executions_per_sec
            FROM fuzzer_metrics
            ORDER BY timestamp DESC
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            return {
                "executions": 0,
                "corpus_size": self.get_corpus_size(),
                "unique_crashes": 0,
                "executions_per_sec": 0.0,
                "line_coverage": 0,
                "branch_coverage": 0,
                "arc_coverage": 0,
            }

        return {
            "executions": int(row["executions"]),
            "corpus_size": int(row["corpus_size"]),
            "unique_crashes": int(row["unique_crashes"]),
            "executions_per_sec": float(row["executions_per_sec"]),
            "line_coverage": int(row["line_coverage"]),
            "branch_coverage": int(row["branch_coverage"]),
            "arc_coverage": int(row["total_edges"]),
        }

    def get_crash_site_summary(self, *, limit: int = 10) -> list[dict[str, object]]:
        rows = self._conn.execute(
            """
            SELECT
                bug_category,
                exception_type,
                file,
                line,
                SUM(count) AS total_hits,
                COUNT(*) AS variants
            FROM crashes
            GROUP BY bug_category, exception_type, file, line
            ORDER BY total_hits DESC, variants DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

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
