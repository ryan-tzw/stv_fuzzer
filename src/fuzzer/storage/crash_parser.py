"""Crash parsing abstractions for converting stderr into structured reports."""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class CrashReport:
    exception_type: str
    exception_message: str
    file: str
    line: int
    traceback: str


class CrashParser(ABC):
    """Convert stderr text into a structured crash report."""

    @abstractmethod
    def parse(self, stderr: str) -> CrashReport: ...


class PythonTracebackCrashParser(CrashParser):
    """Parse Python traceback text from stderr into a CrashReport."""

    _FILE_LINE_RE = re.compile(r'\s*File "(.+)", line (\d+)')

    def parse(self, stderr: str) -> CrashReport:
        tb_text = stderr.strip()
        if tb_text.startswith("ERR:"):
            tb_text = tb_text[4:]

        lines = tb_text.strip().splitlines()
        last_line = lines[-1].strip() if lines else ""
        if ":" in last_line:
            exc_type, exc_msg = last_line.split(":", 1)
        else:
            exc_type, exc_msg = last_line, ""

        file_match = None
        for line in reversed(lines):
            file_match = self._FILE_LINE_RE.match(line)
            if file_match:
                break

        crash_file = file_match.group(1) if file_match else "unknown"
        crash_line = int(file_match.group(2)) if file_match else -1

        return CrashReport(
            exception_type=exc_type.strip(),
            exception_message=exc_msg.strip(),
            file=crash_file,
            line=crash_line,
            traceback=tb_text.strip(),
        )
