def main() -> int:
    import sqlite3
    import tempfile
    from pathlib import Path
    import sys

    repo_root = Path(__file__).resolve().parents[1]
    src_dir = repo_root / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    from fuzzer.corpus.manager import CorpusManager
    from fuzzer.storage.database import FuzzerDatabase

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        db_path = root / "results.db"
        corpus_dir = root / "corpus"
        corpus_dir.mkdir(parents=True, exist_ok=True)
        (corpus_dir / "samples.json").write_text('["x","x","y","x"]', encoding="utf-8")

        db = FuzzerDatabase(db_path)

        # Seed duplicate corpus rows directly to simulate old runs.
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO corpus (data, times_picked, times_fuzzed, created_at) VALUES (?, ?, ?, ?)",
            ("dup", 2, 3, "2026-01-01T00:00:00+00:00"),
        )
        conn.execute(
            "INSERT INTO corpus (data, times_picked, times_fuzzed, created_at) VALUES (?, ?, ?, ?)",
            ("dup", 5, 7, "2026-01-01T00:00:01+00:00"),
        )
        conn.commit()
        conn.close()

        manager = CorpusManager(corpus_dir, db, grammar_name="json")
        manager.load()

        seeds = manager.seeds()
        dup = [s for s in seeds if s.data == "dup"]
        if len(dup) != 1:
            print("error: duplicate rows were not merged on load")
            db.close()
            return 1

        if dup[0].metadata.times_picked != 7 or dup[0].metadata.times_fuzzed != 10:
            print("error: merged duplicate metadata was not summed correctly")
            db.close()
            return 1

        before = len(manager.seeds())
        manager.add("dup")
        after = len(manager.seeds())
        if after != before:
            print("error: add() is not idempotent for existing seed data")
            db.close()
            return 1

        db.close()
        print("Corpus dedup smoke passed.")
        print(
            f"merged_dup_counts: picked={dup[0].metadata.times_picked} fuzzed={dup[0].metadata.times_fuzzed}"
        )
        print(f"seed_count_stable_on_duplicate_add: {before} -> {after}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
