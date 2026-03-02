import json
import sys
import traceback
from typing import Any


def _stable_print(obj: Any) -> None:
    """
    Print a stable representation for differential testing.
    JSON-encode with sorted keys so dict ordering doesn't create false mismatches.
    """
    sys.stdout.write(json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n")


def main() -> int:
    """
    JSON decoder harness for fuzzing.
    Reads JSON input from stdin (required).
    """
    raw = sys.stdin.buffer.read()
    if not raw:
        sys.stderr.write(
            "Error: No input provided. JSON input is required via stdin.\n"
        )
        return 1

    s = raw.decode("utf-8", errors="replace")

    try:
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
