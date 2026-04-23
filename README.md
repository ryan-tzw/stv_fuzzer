# STV Fuzzer

Fuzzer project for 50.053 Software Testing and Verification.

## Getting Started

1. Install [`uv`](https://docs.astral.sh/uv/getting-started/installation/).

2. Install project dependencies:

    ```bash
    uv sync
    uv run pre-commit install
    ```

3. Clone target repositories (run from repo root):

    ```bash
    mkdir -p targets/_reference

    # Blackbox / instrumented targets used by profiles
    git clone https://github.com/TrustWare-Research-Group/IPv4-IPv6-parser.git targets/IPv4-IPv6-parser
    git clone https://github.com/TrustWare-Research-Group/cidrize-runner.git targets/cidrize-runner
    git clone https://github.com/TrustWare-Research-Group/json-decoder.git targets/json-decoder

    # Whitebox reference targets used in differential mode
    git clone https://github.com/jcollie/ipyparse.git targets/_reference/ipyparse
    git clone https://github.com/jathanism/cidrize.git targets/_reference/cidrize
    ```

4. (Optional, but recommended) pre-resolve target dependencies:

    ```bash
    uv sync --project targets/json-decoder
    uv sync --project targets/_reference/cidrize
    ```

5. `ipyparse` reference bootstrap:

    ```bash
    cd targets/_reference/ipyparse
    uv init
    uv add pyparsing
    uv sync
    ```

## Run With Profiles (Recommended)

List built-in profiles:

```bash
uv run python -m fuzzer --list-profiles
```

Current profile names (from `src/fuzzer/config.py`):

- `json_decoder`
- `ipv4_parser`
- `ipv6_parser`
- `cidrize_ipv4`
- `cidrize_ipv6`

Run one profile:

```bash
uv run python -m fuzzer --profile json_decoder
```

Run multiple profiles concurrently:

```bash
uv run python -m fuzzer \
  --profiles json_decoder,ipv4_parser,ipv6_parser,cidrize_ipv4,cidrize_ipv6 \
  --parallel-workers 5
```

Notes:

- With `--profiles`, target-specific overrides are intentionally disabled.
- Output is written under `runs/` by default.

## Profile Configuration (Modify / Add New)

Profiles are defined in `src/fuzzer/config.py` under `PROFILE_CONFIGS`.

To modify an existing profile, edit that profile's dictionary.

To create a new profile, add a new key to `PROFILE_CONFIGS`.

- Required for all profiles: `project_dir`, `harness`, `corpus`, `mode`.
- Required for differential profiles: `blackbox_binary`.
- Common differential options: `blackbox_input_flag`, `blackbox_args`, `harness_args`.

Minimal examples:

```python
"my_coverage_profile": {
    "project_dir": Path("targets/my-target"),
    "harness": "my-harness",
    "corpus": "my-corpus",
    "mode": "coverage",
}
```

```python
"my_differential_profile": {
    "project_dir": Path("targets/_reference/my-ref"),
    "harness": "my-harness",
    "corpus": "my-corpus",
    "mode": "differential",
    "blackbox_binary": Path("targets/my-blackbox/bin/my-target"),
    "blackbox_input_flag": "--ipstr",
}
```

## Making Commits

- `pre-commit` runs Ruff lint/format checks. If Ruff auto-formats files, stage those changes and commit again.
- If lint errors remain, fix them before committing.
- `main` is protected; push to a feature branch and open a PR.
