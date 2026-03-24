#!/bin/bash

set -e

ROOT=$(pwd)
GRAMMAR_DIR="src/fuzzer/grammars/grammar"
GENERATOR_DIR="src/fuzzer/grammars/generator"
ANTLR_OUTPUT_DIR="src/fuzzer/grammars/antlr"

mkdir -p "$GENERATOR_DIR"
mkdir -p "$ANTLR_OUTPUT_DIR"

cd "$GRAMMAR_DIR"

echo "=== Grammar Compilation Script ==="
echo "Scanning for grammar files in: $GRAMMAR_DIR"
# Compile all .g4 grammar files found in the directory
for grammar_file in *.g4; do
    if [ ! -f "$grammar_file" ]; then
        continue
    fi
    grammar_name="${grammar_file%.g4}"
    echo "Compiling $grammar_name grammar..."
    grammar_output_dir="$ROOT/$ANTLR_OUTPUT_DIR/$grammar_name"

    mkdir -p "$grammar_output_dir"
    grammarinator-process "$grammar_file" -o "$ROOT/$GENERATOR_DIR" --no-action
    antlr4 -Dlanguage=Python3 -visitor -o "$grammar_output_dir" "$grammar_file"
done

cd "$ROOT"

echo "=== Compilation Complete ==="
echo "ANTLR output directory: $ANTLR_OUTPUT_DIR"
echo "Generator output directory: $GENERATOR_DIR"
