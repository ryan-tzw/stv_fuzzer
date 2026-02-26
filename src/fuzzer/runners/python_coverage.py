"""
Runs a python script with coverage.py
For fuzzing python scripts
"""

import subprocess


class PythonCoverageRunner:
    def __init__(self, script_path, script_args=None):
        self.script_path = script_path
        self.script_args = script_args or []

    def run(self):
        # Run the script with coverage.py
        result = subprocess.run(
            ["uv", "run", "python", "-m", "coverage", "run", self.script_path, *self.script_args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        return result.stdout, result.stderr


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run a python script with coverage.py")
    parser.add_argument("script_path", help="Path to the python script to run")
    parser.add_argument(
        "script_args", nargs=argparse.REMAINDER, help="Arguments to pass to the script"
    )
    args = parser.parse_args()

    runner = PythonCoverageRunner(args.script_path, args.script_args)
    stdout, stderr = runner.run()
    print("STDOUT:", stdout)
    print("STDERR:", stderr)
