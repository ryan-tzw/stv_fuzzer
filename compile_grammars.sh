#!/bin/bash

ROOT=$(pwd)
GRAMMAR_DIR="src/fuzzer/grammars/grammar"
ANTLR_OUTPUT_DIR="src/fuzzer/grammars/antlr"

mkdir -p "$GENERATOR_DIR"
mkdir -p "$ANTLR_OUTPUT_DIR"

cd "$GRAMMAR_DIR"

echo "Compiling JSON grammar..."
antlr4 -Dlanguage=Python3 -visitor -o "$ROOT/$ANTLR_OUTPUT_DIR/json" json.g4

echo "Compiling IP grammar..."
antlr4 -Dlanguage=Python3 -visitor -o "$ROOT/$ANTLR_OUTPUT_DIR/ip" ip.g4

cd "$ROOT"

