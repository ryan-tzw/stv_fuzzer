import json
import sys
import traceback
from pathlib import Path
from typing import Any


def _stable_print(obj: Any) -> None:
    sys.stdout.write(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str) + "\n"
    )


def _ensure_project_on_syspath() -> None:
    harness_dir = str(Path(__file__).resolve().parent)
    sys.path[:] = [entry for entry in sys.path if entry != harness_dir]

    project_dir = Path.cwd()
    project_str = str(project_dir)
    if project_str not in sys.path:
        sys.path.insert(0, project_str)


def main() -> int:
    _ensure_project_on_syspath()

    raw = sys.stdin.buffer.read()
    s = raw.decode("utf-8", errors="replace")

    try:
        import cidrize  # type: ignore

        result = cidrize.cidrize(s, raise_errors=True)
        _stable_print(result)
        return 0

    except Exception:
        sys.stderr.write(traceback.format_exc())
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
