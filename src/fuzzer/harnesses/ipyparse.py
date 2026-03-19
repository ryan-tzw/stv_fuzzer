import importlib
import importlib.util
import json
import sys
import traceback
import types
from pathlib import Path
from typing import Protocol


class _ParserProtocol(Protocol):
    def parseString(self, text: str) -> list[int]: ...


def _stable_print(value: object) -> None:
    sys.stdout.write(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")


def _ensure_target_paths() -> None:
    project_dir = Path.cwd()
    for path in (project_dir / "src", project_dir):
        path_str = str(path)
        if path.exists() and path_str not in sys.path:
            sys.path.insert(0, path_str)


def _remove_harness_dir_from_syspath() -> None:
    harness_dir = str(Path(__file__).resolve().parent)
    sys.path[:] = [p for p in sys.path if p != harness_dir]


def _load_module_from_file(module_name: str, file_path: Path) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ModuleNotFoundError(f"Cannot load module {module_name} from {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_parsers() -> tuple[_ParserProtocol, _ParserProtocol]:
    _ensure_target_paths()
    _remove_harness_dir_from_syspath()

    # If a plain module named ``ipyparse`` is already loaded, it blocks package imports.
    existing = sys.modules.get("ipyparse")
    if existing is not None and not hasattr(existing, "__path__"):
        del sys.modules["ipyparse"]

    try:
        from ipparse.ipv4 import IPv4  # type: ignore
        from ipparse.ipv6 import IPv6_WholeString  # type: ignore

        return IPv4, IPv6_WholeString
    except ModuleNotFoundError:
        try:
            # Reference target package name is ``ipyparse`` but internal imports use ``ipparse``.
            ipy_pkg = importlib.import_module("ipyparse")
            ipv4_mod = importlib.import_module("ipyparse.ipv4")

            sys.modules.setdefault("ipparse", ipy_pkg)
            sys.modules["ipparse.ipv4"] = ipv4_mod

            ipv6_mod = importlib.import_module("ipyparse.ipv6")
            return ipv4_mod.IPv4, ipv6_mod.IPv6_WholeString
        except ModuleNotFoundError:
            repo_root = Path(__file__).resolve().parents[3]
            candidates = [
                Path.cwd() / "src" / "ipyparse",
                repo_root / "targets" / "_reference" / "ipyparse" / "src" / "ipyparse",
            ]
            src_pkg = next((p for p in candidates if p.is_dir()), None)
            if src_pkg is None:
                raise

            ipv4_mod = _load_module_from_file("_stv_ipyparse_ipv4", src_pkg / "ipv4.py")

            # Alias as ``ipparse`` so legacy import in ipv6.py keeps working.
            ipparse_pkg = types.ModuleType("ipparse")
            ipparse_pkg.__path__ = [str(src_pkg)]
            sys.modules["ipparse"] = ipparse_pkg
            sys.modules["ipparse.ipv4"] = ipv4_mod

            ipv6_mod = _load_module_from_file("_stv_ipyparse_ipv6", src_pkg / "ipv6.py")
            return ipv4_mod.IPv4, ipv6_mod.IPv6_WholeString


def _parse_ip(ip_str: str) -> list[int]:
    IPv4, IPv6_WholeString = _load_parsers()

    if ":" in ip_str:
        return list(IPv6_WholeString.parseString(ip_str))
    return list(IPv4.parseString(ip_str))


def main() -> int:
    raw = sys.stdin.buffer.read()
    if not raw:
        sys.stderr.write("Error: No input provided. IP input is required via stdin.\n")
        return 1

    ip_str = raw.decode("utf-8", errors="replace")

    try:
        parsed = _parse_ip(ip_str)
        _stable_print(parsed)
        return 0
    except Exception:
        sys.stderr.write(f"ERR:{traceback.format_exc()}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
