# python-afl baseline benchmark

This directory runs [python-afl](https://github.com/jwilk/python-afl) against
the same 5 run configurations STV Fuzzer is benchmarked on, for direct
cross-fuzzer comparison. **No files under `src/fuzzer/` are modified.**

Only the harnesses, seeds, and benchmark scripts are intended to be committed.
The `python-afl` package, AFL++ installation, `.venv-python-afl/`, and
generated benchmark outputs under `benchmarks/python_afl/runs/` are local-only.

## Setup

### macOS / Linux (arm64 or x86_64)

```bash
# 1. AFL++ (macOS via Homebrew; Linux via apt/brew/distro)
brew install afl++             # macOS
# sudo apt install afl++       # Ubuntu / Debian

# 2. Dedicated Python 3.11 venv with python-afl and target libs
python3.11 -m venv .venv-python-afl
.venv-python-afl/bin/pip install --upgrade pip
.venv-python-afl/bin/pip install python-afl cidrize netaddr pyparsing
.venv-python-afl/bin/pip install git+https://github.com/jcollie/ipyparse.git

# 3. Sanity check
.venv-python-afl/bin/python -c "import afl, ipyparse, cidrize; print('ok')"
```

### Windows

**Native Windows is not supported** — upstream AFL has no Windows port.
Use **WSL2 (Ubuntu)** and run the Linux setup above inside WSL.

## Architecture match (macOS)

`afl-fuzz` and the venv Python must report the same architecture, or the
fork server will hang. Verify:

```bash
file /opt/homebrew/Cellar/afl++/*/libexec/afl-fuzz   # arm64 on Apple silicon
file .venv-python-afl/bin/python                      # must match
```

## Layout

```
benchmarks/python_afl/
├── README.md               # this file
├── run_benchmark.py        # orchestrator: 3x15min x 5 configs
├── parse_plot_data.py      # AFL plot_data -> normalized CSV
├── aggregate_results.py    # mean/stdev across runs -> summary.md
├── seeds/
│   ├── json/seed_000
│   ├── ipv4/seed_000
│   ├── ipv6/seed_000
│   ├── cidrize_ipv4/seed_000
│   └── cidrize_ipv6/seed_000   # 1-byte starter seeds (fair blind start)
└── runs/<UTC-timestamp>/       # created per benchmark invocation
    ├── meta.json
    ├── results.jsonl           # appended by run_benchmark as runs complete
    ├── results.csv             # written by aggregate_results.py
    ├── results_mean.csv
    ├── summary.md
    └── <target>/
        ├── run0/               # AFL output root
        │   └── default/{plot_data,crashes,queue,...}
        ├── run0.log            # py-afl-fuzz stdout+stderr
        ├── run0.plot.csv       # normalized plot_data
        ├── run0.summary.json   # classified crash counts
        └── run1.*, run2.*
```

## Harnesses (under `tools/`)

Each harness mirrors the `fuzz_json_python_afl.py` pattern: import once,
call `afl.init()`, read stdin/argv, raise a labeled `RuntimeError` on
bug (AFL treats nonzero exit as a crash → stored in `default/crashes/`).

| Target         | Harness                            | Oracle                                       |
|----------------|------------------------------------|----------------------------------------------|
| json           | fuzz_json_python_afl.py            | stdlib `json.loads` vs `buggy_json.loads`    |
| ipv4           | fuzz_ipv4_python_afl.py            | `ipaddress.IPv4Address` vs `ipyparse.ipv4`   |
| ipv6           | fuzz_ipv6_python_afl.py            | `ipaddress.IPv6Address` vs `ipyparse.ipv6`   |
| cidrize_ipv4   | fuzz_cidrize_ipv4_python_afl.py    | `cidrize` self-consistency + round-trip      |
| cidrize_ipv6   | fuzz_cidrize_ipv6_python_afl.py    | same                                         |

## Running the benchmark

### One target, default cadence (3 runs × 15 minutes = ~45 min)

```bash
.venv-python-afl/bin/python benchmarks/python_afl/run_benchmark.py \
  --target json --runs 3 --seconds 900
```

### All targets (~3h45min wall-clock)

```bash
.venv-python-afl/bin/python benchmarks/python_afl/run_benchmark.py \
  --target all --runs 3 --seconds 900
```

### Quick dry-run per target (60s, sanity check only)

```bash
.venv-python-afl/bin/python benchmarks/python_afl/run_benchmark.py \
  --target json --runs 1 --seconds 60 \
  --out /tmp/afl_dryrun
```

## Aggregating after the runs

`run_benchmark.py` writes `run<k>.plot.csv` + `run<k>.summary.json`
incrementally. After all runs finish, generate the combined CSV + report:

```bash
.venv-python-afl/bin/python benchmarks/python_afl/aggregate_results.py \
  benchmarks/python_afl/runs/<timestamp>/
# writes: results.csv, results_mean.csv, summary.md
```

## Replaying a single crash artifact

```bash
.venv-python-afl/bin/python tools/replay_python_afl_case.py \
  --target ipv4 benchmarks/python_afl/runs/<ts>/ipv4/run0/default/crashes/id:000000,...
```

## Summarizing crashes manually

```bash
.venv-python-afl/bin/python tools/summarize_python_afl_artifacts.py \
  --target cidrize_ipv4 benchmarks/python_afl/runs/<ts>/cidrize_ipv4/run0
```

## Comparison with STV Fuzzer

The harnesses fuzz the same Python code that STV Fuzzer exercises:

- **json** — both fuzz `buggy_json.decoder_stv` directly (whitebox for both tools).
- **ipv4/ipv6/cidrize_{ipv4,ipv6}** — STV Fuzzer treats these as blackbox
  binary targets in differential mode. python-afl has no way to
  instrument a compiled binary, so the baseline fuzzes the Python
  reference implementation (`ipyparse`, `cidrize`) that the blackbox
  binaries wrap. This is the same Python code path STV's differential
  harness ultimately exercises.

Metric mapping for the writeup:

| python-afl (AFL `plot_data`)        | STV Fuzzer           | Meaning                     |
|-------------------------------------|----------------------|-----------------------------|
| `edges_found`                        | `arc_coverage`       | Branch-level coverage       |
| `saved_crashes` (dedup via summary) | `unique_crashes`     | Distinct bugs               |
| `execs_per_sec`                      | `execs_per_sec`      | Raw throughput              |
| `paths_total` (= `corpus_count`)     | corpus size          | Diversity of interesting inputs |

Note: python-afl's fork-per-exec model on macOS is 10-100x slower than
STV Fuzzer's in-process mutation loop. For fairness, compare **coverage
per wall-second** and **bugs per wall-minute**, not raw `execs/sec`.

## macOS AFL env vars

`run_benchmark.py` sets the following automatically (mirrors what the
previous python-afl runs in `runs/python_afl_compare_600_rerun/` used):

- `AFL_SKIP_BIN_CHECK=1` — accept a Python interpreter as the target binary
- `AFL_SKIP_CPUFREQ=1` — macOS does not expose Linux-style cpufreq
- `AFL_I_DONT_CARE_ABOUT_MISSING_CRASHES=1` — macOS crash reporter interferes
- `AFL_NO_UI=1` — AFL++ TUI degrades in subprocess-captured logs
- `AFL_DUMB_FORKSRV=1` — disables persistent-mode check for python-afl

If AFL complains about the ReportCrash daemon, either accept the warning
(`AFL_I_DONT_CARE_ABOUT_MISSING_CRASHES=1` suppresses exit) or disable
the daemon with the commands printed in AFL's startup banner.

## Reproducibility

Always run all 5 configs on **one machine** for a given benchmark set.
CPU/memory variance across machines invalidates `execs/sec` and
coverage-per-wall-second averages. The canonical machine is your Mac;
teammates who need to reproduce use WSL2 and accept that absolute
numbers will differ (relative ordering of targets should not).
