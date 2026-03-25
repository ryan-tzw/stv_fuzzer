def main() -> int:
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    src_dir = repo_root / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    from fuzzer.observers.bug_category import parse_crash

    jsondecode_stderr = """Traceback (most recent call last):
  File "/tmp/harness.py", line 10, in <module>
    run()
buggy_json.decoder_stv.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
"""

    functional_stderr = """Traceback (most recent call last):
  File "/tmp/harness.py", line 20, in <module>
    run()
buggy_ipyparse.ipv4_stv.FunctionalBug: Invalid ipv4 calculation.
"""

    trigger_line_stderr = """An validity bug has been triggered
Traceback (most recent call last):
  File "/tmp/harness.py", line 20, in <module>
    run()
buggy_ipyparse.ipv4_stv.FunctionalBug: Invalid ipv4 calculation.
"""

    final_bug_count_stderr = """Final bug count: defaultdict(<class 'int'>, {(
    'reliability', <class 'pkg.mod.ReliabilityBug'>, 'oops', '/tmp/target.py', 88): 1})
TRACEBACK=================================================
Traceback (most recent call last):
  File "/tmp/harness.py", line 30, in <module>
    run()
pkg.mod.ReliabilityBug: oops
=================================================
"""

    checks = [
        (
            "jsondecode",
            parse_crash(jsondecode_stderr),
            "bonus_untracked",
            "exception_fallback",
        ),
        (
            "functional",
            parse_crash(functional_stderr),
            "functional",
            "exception_fallback",
        ),
        ("trigger-line", parse_crash(trigger_line_stderr), "validity", "trigger_line"),
        (
            "final-bug-count",
            parse_crash(final_bug_count_stderr),
            "reliability",
            "final_bug_count",
        ),
    ]

    failed = False
    for name, parsed, want_cat, want_src in checks:
        ok = parsed.bug_category == want_cat and parsed.category_source == want_src
        status = "ok" if ok else "fail"
        print(
            f"[{name}] {status} category={parsed.bug_category} "
            f"source={parsed.category_source}"
        )
        if not ok:
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
