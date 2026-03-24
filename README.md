# STV Fuzzer

Fuzzer project for 50.053 Software Testing and Verification

# Getting started

1. [Install uv](https://docs.astral.sh/uv/getting-started/installation/)

2. Install dependencies

    ```
    uv sync
    uv run pre-commit install
    ```

3. Clone targets

    ```
    mkdir targets
    cd targets
    git clone https://github.com/TrustWare-Research-Group/IPv4-IPv6-parser.git
    git clone https://github.com/TrustWare-Research-Group/cidrize-runner.git
    git clone https://github.com/TrustWare-Research-Group/json-decoder.git
    ```

4. Run
    ```
    uv run python -m fuzzer targets/<TARGET_DIR> <HARNESS_FILENAME> <DATA_TYPE>
    ```

# Grammar-based mutation: before vs now

Before this refactor:

- The fuzzer was effectively JSON-focused.
- Mutation was mostly raw character editing on strings.
- The corpus stored only raw input text.
- The execution path was centered on the Python coverage-based target.
- IPv4, IPv6, and `cidrize-runner` did not have a fully integrated grammar-backed path, so runs could fall back to plain string mutation.

Now:

- Grammars are loaded declaratively from `src/fuzzer/grammar/specs/`.
- Seed inputs are parsed into a generic derivation tree rather than a handwritten JSON/IP-specific AST.
- Mutation operates on the derivation tree, then serializes the mutated tree back to text.
- The corpus stores both raw input and `tree_json`, so grammar-backed mutation can be inspected and resumed.
- The same engine now supports all three shipped targets:
  - `json-decoder` via the existing whitebox/coverage path
  - `ipv4-parser`, `ipv6-parser`, and `cidrize-runner` via the new blackbox command-execution path

In short, the old design was "mutate strings and mainly fuzz JSON"; the current design is "load a grammar, build a generic derivation tree, mutate the tree, and run the correct backend for the target".

# How to verify grammar mutation is actually being used

Run a short smoke test:

```
uv run python -m fuzzer targets/<TARGET_DIR> <HARNESS_FILENAME> <DATA_TYPE> --max-iterations 1 --time-limit -1 --runs-dir /tmp/stv-check
```

Then inspect the newest run database:

```
run=$(ls -td /tmp/stv-check/* | head -n1)
sqlite3 "$run/results.db" "select id, quote(data), tree_json is not null from corpus order by id;"
```

How to read the output:

- `tree_json is not null = 1` means the input was stored with a derivation tree, so the grammar-based path was used.
- `tree_json is not null = 0` means the run fell back to plain string mutation.

Example of the difference:

- Old behavior: `'192.168.1.1\n'|0` mutated into something like `'192.168%1.1\n'|0`
- New behavior: `'192.168.1.1'|1` mutated into something like `'192.168.169.1'|1`

For the packaged binary targets (`ipv4-parser`, `ipv6-parser`, `cidrize-runner`), one iteration can take tens of seconds because the target startup cost is high.

# Making commits

- Note: Because the pre-commit is configured with Ruff's linter and formatter, if Ruff makes any formatting changes to your code, it will show an error.
  This should not be a problem, just stage the changes that Ruff made and commit again.

    If it was a lint error however, you need to fix the error and commit again.

- `main` branch is protected so push to a separate branch and make a PR to merge.
