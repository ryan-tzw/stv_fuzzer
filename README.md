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

4. Compile grammars

    ```bash 
    chmode +x compile_grammars.sh
    compile_grammars.sh
    ```

    This will automatically compile all `.g4` grammar files in `src/fuzzer/grammars/grammar/` and generate ANTLR lexer, parser, and visitor classes.

5. Run

    ```
    uv run python -m fuzzer targets/<TARGET_DIR> <HARNESS_FILENAME> <DATA_TYPE>
    ```

# Adding a New Grammar

To add a new grammar to the fuzzer:

1. **Create your grammar file**

   Create a new `.g4` grammar file in `src/fuzzer/grammars/grammar/`:
   ```
   src/fuzzer/grammars/grammar/mygrammar.g4
   ```

2. **Compile the grammar**

   Run the compile script to generate ANTLR classes automatically:
   ```
   bash compile_grammars.sh
   ```

   This will:
   - Generate ANTLR Lexer, Parser, and Visitor classes in `src/fuzzer/grammars/antlr/mygrammar/`
   - Generate grammar patterns in `src/fuzzer/grammars/generator/`

3. **Register the grammar (if needed)**

    For basic grammars that use generic components, no registration is needed. 
    
    For custom implementations with specialized `AstBuilder`, `Operations`, or `Unparser` classes, add a registration call to `src/fuzzer/engine.py` in the `_register_grammars()` method, following the JSON and IP examples:
    
    ```python
    register_grammar(
        "mygrammar",
        parser_class=MygrammarParser,
        lexer_class=MygrammarLexer,
        ast_builder_class=MygrammarAstBuilder,      # Optional: custom logic
        operations_class=MygrammarGrammarOperations, # Optional: custom operations
        unparser_class=MygrammarUnparser,            # Optional: custom unparsing
    )
    ```

4. **Run the fuzzer**

   Use your new grammar with the fuzzer:
   ```
   uv run python -m fuzzer targets/<TARGET_DIR> <HARNESS_FILENAME> mygrammar
   ```

# Making commits

- Note: Because the pre-commit is configured with Ruff's linter and formatter, if Ruff makes any formatting changes to your code, it will show an error.
  This should not be a problem, just stage the changes that Ruff made and commit again.

    If it was a lint error however, you need to fix the error and commit again.

- `main` branch is protected so push to a separate branch and make a PR to merge.
