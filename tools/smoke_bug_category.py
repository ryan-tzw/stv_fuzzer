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

    wrapped_chain_stderr = """Traceback (most recent call last):
  File "netaddr/strategy/ipv4.py", line 128, in str_to_int
OSError: illegal IP address string passed to inet_pton

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "netaddr/ip/__init__.py", line 346, in __init__
  File "netaddr/strategy/ipv4.py", line 132, in str_to_int
netaddr.core.AddrFormatError: '4.436..5' is not a valid IPv4 address string!

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "netaddr/ip/__init__.py", line 1034, in __init__
  File "netaddr/ip/__init__.py", line 902, in parse_ip_network
  File "netaddr/ip/__init__.py", line 348, in __init__
netaddr.core.AddrFormatError: base address '4.436..5' is not IPv4

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "cidrize_runner_stv.py", line 247, in <module>
  File "buggy_cidrize/cidrize_stv.py", line 481, in cidrize
  File "netaddr/ip/__init__.py", line 1045, in __init__
netaddr.core.AddrFormatError: invalid IPNetwork 4.436..5
Traceback (most recent call last):
  File "cidrize_runner_stv.py", line 313, in <module>
  File "cidrize_runner_stv.py", line 160, in bug_count_to_csv
  File "pandas/_libs/parsers.pyx", line 2061, in pandas._libs.parsers.raise_parser_error
pandas.errors.ParserError: Error tokenizing data. C error: Expected 6 fields in line 142, saw 10
[PYI-3768116: ERROR] Failed to execute script 'cidrize_runner_stv' due to unhandled exception!
"""

    wrapper_only_stderr = """[PYI-3768116: ERROR] Failed to execute script 'cidrize_runner_stv' due to unhandled exception!"""

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
        (
            "wrapped-chain",
            parse_crash(wrapped_chain_stderr),
            "invalidity",
            "exception_fallback",
        ),
        (
            "wrapper-only",
            parse_crash(wrapper_only_stderr),
            "unknown",
            "traceback_fallback",
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

    wrapped = parse_crash(wrapped_chain_stderr)
    if wrapped.exception_type != "netaddr.core.AddrFormatError":
        print(
            "[wrapped-chain] fail exception_type="
            f"{wrapped.exception_type} (expected netaddr.core.AddrFormatError)"
        )
        failed = True
    if wrapped.file != "netaddr/ip/__init__.py" or wrapped.line != 1045:
        print(
            "[wrapped-chain] fail location="
            f"{wrapped.file}:{wrapped.line} (expected netaddr/ip/__init__.py:1045)"
        )
        failed = True

    wrapper_only = parse_crash(wrapper_only_stderr)
    if not wrapper_only.exception_type:
        print("[wrapper-only] fail exception_type should be non-empty")
        failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
