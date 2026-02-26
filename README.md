# STV Fuzzer

Fuzzer project for 50.053 Software Testing and Verification

# Getting started
1. [Install uv](https://docs.astral.sh/uv/getting-started/installation/)

2. Install dependencies
    ```
    uv sync
    uv run pre-commit install
    ```

3. Run
    ```
    uv run python -m fuzzer
    ```

# Making commits

- Note: Because the pre-commit is configured with Ruff, if Ruff makes any changes to your code, it will show an error.
This is not a problem, just stage the changes and commit again.
- `main` branch is protected so push to a separate branch and make a PR to merge.