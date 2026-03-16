"""Simple executor that runs a command with given stdin and returns output."""

from subprocess import PIPE, run
from typing import List, Optional, Tuple


class RawProcessExecutor:
    """Execute an arbitrary command without coverage, returning stdout/stderr.

    Intended as the blackbox side of a differential executor; not used
    standalone by the fuzzing engine.
    """

    def __init__(
        self,
        cmd: List[str],
        cwd: Optional[str] = None,
        env: Optional[dict] = None,
    ) -> None:
        self.cmd = cmd
        self.cwd = cwd
        self.env = env

    def run(self, input_data: str | None = None) -> Tuple[str, str, int]:
        """Run the command, feeding *input_data* to stdin.

        Returns ``(stdout, stderr, returncode)``.
        """
        result = run(
            self.cmd,
            stdout=PIPE,
            stderr=PIPE,
            text=True,
            cwd=self.cwd,
            env=self.env,
            input=input_data,
        )
        return result.stdout, result.stderr, result.returncode
