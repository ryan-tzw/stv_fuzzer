from __future__ import annotations


def _make_parsed_crash(
    *,
    message: str,
    category: str = "invalidity",
    line: int = 384,
    category_source: str = "trigger_line",
):
    from fuzzer.observers.input import ParsedCrash

    return ParsedCrash(
        exception_type="JSONDecodeError",
        exception_message=message,
        file="buggy_json/decoder_stv.py",
        line=line,
        traceback="Traceback ...",
        bug_category=category,
        category_source=category_source,
    )


def _assert_equal(actual: int, expected: int, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected}, got {actual}")


def main() -> int:
    import sqlite3
    import tempfile
    from pathlib import Path

    from fuzzer.storage.database import FuzzerDatabase

    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "results.db"
        db = FuzzerDatabase(db_path)

        # 1) final_bug_count: same site/category + different messages -> dedup hit.
        c1 = _make_parsed_crash(
            message="invalid IPNetwork 0.140..49",
            category_source="final_bug_count",
        )
        c2 = _make_parsed_crash(
            message="invalid IPNetwork .2.2.281",
            category_source="final_bug_count",
        )
        assert db.record_crash("input-a", c1) is True
        assert db.record_crash("input-b", c2) is False

        # 2) final_bug_count: different line -> new unique crash.
        c3 = _make_parsed_crash(
            message="invalid IPNetwork 1.1.1.a",
            line=1046,
            category_source="final_bug_count",
        )
        assert db.record_crash("input-c", c3) is True

        # 3) non-final_bug_count: message formatting variants still dedup.
        c4 = _make_parsed_crash(message="Expecting   value")
        c5 = _make_parsed_crash(message="expecting value")
        assert db.record_crash("input-d", c4) is True
        assert db.record_crash("input-e", c5) is False

        # 4) non-final_bug_count: different message -> new unique crash.
        c6 = _make_parsed_crash(message="Unterminated string")
        assert db.record_crash("input-f", c6) is True

        # 5) non-final_bug_count: same site/message + different category -> new unique.
        c7 = _make_parsed_crash(
            message="Unterminated string",
            category="bonus_untracked",
        )
        assert db.record_crash("input-g", c7) is True

        rows = db._conn.execute("SELECT COUNT(*) AS n FROM crashes").fetchone()
        _assert_equal(int(rows["n"]), 5, "crash row count after dedup scenarios")
        db.close()

    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "results.db"
        db = FuzzerDatabase(db_path)

        # 6) Same site/category + message formatting variants -> dedup hit.
        c1 = _make_parsed_crash(message="Expecting   value")
        c2 = _make_parsed_crash(message="expecting value")
        assert db.record_crash("input-a", c1) is True
        assert db.record_crash("input-b", c2) is False

        # 7) Same site/category + different message -> new unique crash.
        c3 = _make_parsed_crash(message="Unterminated string")
        assert db.record_crash("input-c", c3) is True

        # 8) Same site/message + different category -> new unique crash.
        c4 = _make_parsed_crash(
            message="Unterminated string",
            category="bonus_untracked",
        )
        assert db.record_crash("input-d", c4) is True

        rows = db._conn.execute("SELECT COUNT(*) AS n FROM crashes").fetchone()
        _assert_equal(int(rows["n"]), 3, "crash row count after dedup scenarios")
        db.close()

    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "legacy.db"
        conn = sqlite3.connect(db_path)
        conn.executescript(
            """
            CREATE TABLE crashes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exception_type TEXT NOT NULL,
                exception_message TEXT NOT NULL,
                file TEXT NOT NULL,
                line INTEGER NOT NULL,
                traceback TEXT NOT NULL,
                bug_category TEXT NOT NULL DEFAULT 'unknown',
                category_source TEXT NOT NULL DEFAULT 'traceback_fallback',
                data TEXT NOT NULL,
                count INTEGER NOT NULL DEFAULT 1,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            );
            CREATE UNIQUE INDEX crashes_dedup ON crashes (exception_type, file, line);
            """
        )
        conn.commit()
        conn.close()

        db = FuzzerDatabase(db_path)
        assert (
            db.record_crash("legacy-input", _make_parsed_crash(message="Legacy check"))
            is True
        )

        index_rows = db._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' ORDER BY name"
        ).fetchall()
        index_names = {row["name"] for row in index_rows}
        if "crashes_dedup" in index_names:
            raise AssertionError("legacy crashes_dedup index should be dropped")
        if "crashes_dedup_key" not in index_names:
            raise AssertionError("crashes_dedup_key index should exist after migration")
        db.close()

    print("smoke_crash_dedup: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
