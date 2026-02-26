import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Any


def _add_target_to_syspath() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    target_dir = repo_root / "targets" / "json-decoder"
    sys.path.insert(0, str(target_dir))


def _stable_print(obj: Any) -> None:
    """
    Print a stable representation for differential testing.
    JSON-encode with sorted keys so dict ordering doesn't create false mismatches.
    """
    sys.stdout.write(json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n")


def main() -> int:
    """
    JSON decoder harness for fuzzing.
    Either reads from stdin, or accepts a JSON filepath argument
    Uses default.json from the corpus if no input is provided.
    """
    _add_target_to_syspath()

    default_json = Path(__file__).parent / "corpus" / "default.json"

    parser = argparse.ArgumentParser(description="JSON decoder harness")
    parser.add_argument(
        "file",
        nargs="?",
        type=Path,
        default=None,
        help="JSON file to decode (reads from stdin if omitted, falls back to default.json)",
    )
    args = parser.parse_args()

    if args.file:
        raw = args.file.read_bytes()
    elif not sys.stdin.isatty():
        raw = sys.stdin.buffer.read()
    else:
        raw = default_json.read_bytes()

    s = raw.decode("utf-8", errors="replace")

    try:
        # Import after sys.path adjustment
        import json_decoder_stv  # type: ignore

        obj = json_decoder_stv.loads(s)

        # If the decoder returns a Python object, print stable JSON
        _stable_print(obj)

        return 0

    except Exception:
        sys.stderr.write(f"ERR:{traceback.format_exc()}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
