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

# Making commits

- Note: Because the pre-commit is configured with Ruff's linter and formatter, if Ruff makes any formatting changes to your code, it will show an error.
  This should not be a problem, just stage the changes that Ruff made and commit again.

        If it was a lint error however, you need to fix the error and commit again.

- `main` branch is protected so push to a separate branch and make a PR to merge.
