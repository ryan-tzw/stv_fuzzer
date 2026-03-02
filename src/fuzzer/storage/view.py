"""
View the contents of a fuzzer results database.
"""

import argparse
import sqlite3
import textwrap
from pathlib import Path


def _conn(db_path: Path) -> sqlite3.Connection:
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def show_summary(conn: sqlite3.Connection) -> None:
    corpus_count = conn.execute("SELECT COUNT(*) FROM corpus").fetchone()[0]
    crash_count = conn.execute("SELECT COUNT(*) FROM crashes").fetchone()[0]
    total_crash_hits = conn.execute(
        "SELECT COALESCE(SUM(count), 0) FROM crashes"
    ).fetchone()[0]

    print("=== Summary ===")
    print(f"  Corpus entries : {corpus_count}")
    print(f"  Unique crashes : {crash_count}")
    print(f"  Total crash hits: {total_crash_hits}")
    print()


def show_corpus(conn: sqlite3.Connection, show_data: bool = False) -> None:
    rows = conn.execute(
        "SELECT id, times_picked, times_fuzzed, created_at, data FROM corpus ORDER BY id"
    ).fetchall()

    print(f"=== Corpus ({len(rows)} entries) ===")
    for row in rows:
        print(
            f"  [{row['id']:>4}] picked={row['times_picked']:>4}  fuzzed={row['times_fuzzed']:>4}  created={row['created_at']}"
        )
        if show_data:
            preview = textwrap.shorten(row["data"], width=120, placeholder="...")
            print(f"         data: {preview}")
    print()


def show_crashes(
    conn: sqlite3.Connection, show_traceback: bool = False, show_data: bool = False
) -> None:
    rows = conn.execute(
        """
        SELECT id, exception_type, exception_message, file, line,
               count, first_seen_at, last_seen_at, traceback, data
        FROM crashes
        ORDER BY count DESC
        """
    ).fetchall()

    print(f"=== Crashes ({len(rows)} unique) ===")
    for row in rows:
        print(
            f"  [{row['id']:>4}] {row['exception_type']}: {textwrap.shorten(row['exception_message'], width=60, placeholder='...')}"
        )
        print(f"         file : {row['file']}:{row['line']}")
        print(
            f"         count: {row['count']}  first={row['first_seen_at']}  last={row['last_seen_at']}"
        )
        if show_data:
            preview = textwrap.shorten(row["data"], width=120, placeholder="...")
            print(f"         input: {preview}")
        if show_traceback:
            indented = textwrap.indent(row["traceback"], prefix="           ")
            print(f"         traceback:\n{indented}")
        print()


def main() -> int:
    parser = argparse.ArgumentParser(description="View fuzzer results database")
    parser.add_argument("db_path", type=Path, help="Path to the results.db file")
    parser.add_argument("--corpus", action="store_true", help="Show corpus entries")
    parser.add_argument("--crashes", action="store_true", help="Show crash entries")
    parser.add_argument(
        "--data", action="store_true", help="Include input data in output"
    )
    parser.add_argument(
        "--traceback",
        action="store_true",
        help="Include full tracebacks in crash output",
    )
    parser.add_argument(
        "--all",
        dest="show_all",
        action="store_true",
        help="Show everything (corpus + crashes + data + tracebacks)",
    )
    args = parser.parse_args()

    conn = _conn(args.db_path)

    show_all = args.show_all
    display_corpus = args.corpus or show_all
    display_crashes = args.crashes or show_all
    show_data = args.data or show_all
    show_tb = args.traceback or show_all

    # Default: show summary + crashes if no specific section requested
    if not display_corpus and not display_crashes:
        show_summary(conn)
        show_crashes(conn, show_traceback=show_tb, show_data=show_data)
    else:
        show_summary(conn)
        if display_corpus:
            show_corpus(conn, show_data=show_data)
        if display_crashes:
            show_crashes(conn, show_traceback=show_tb, show_data=show_data)

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
