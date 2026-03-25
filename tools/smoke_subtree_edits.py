def main() -> int:
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    src_dir = repo_root / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    from fuzzer.grammar.loader import load_parser
    from fuzzer.grammar.parser import parse_input
    from fuzzer.mutator.tree.operations import SubtreeDelete, SubtreeDuplicate

    cases = [
        ("ipv4", "192.168.0.1"),
        ("ipv6", "2001:db8::1"),
        ("json", '{"a":1,"b":[2,3],"c":4}'),
    ]

    failed = False
    retries = 40

    for grammar_name, seed in cases:
        parser = load_parser(grammar_name)
        operations = [
            ("delete", SubtreeDelete(grammar_name=grammar_name)),
            ("duplicate", SubtreeDuplicate(grammar_name=grammar_name)),
        ]

        for op_name, operation in operations:
            outputs: list[str] = []
            parseable = 0
            for _ in range(retries):
                value = operation.mutate(seed)
                outputs.append(value)
                if parse_input(parser, value).success:
                    parseable += 1

            unique_outputs = sorted(set(outputs))
            changed = any(v != seed for v in unique_outputs)
            non_string = any(not isinstance(v, str) for v in unique_outputs)

            print(f"[{grammar_name}/{op_name}] seed: {seed}")
            print(f"[{grammar_name}/{op_name}] unique_outputs: {len(unique_outputs)}")
            print(f"[{grammar_name}/{op_name}] parseable: {parseable}/{len(outputs)}")
            for sample in unique_outputs[:10]:
                print(sample)
            print()

            if non_string:
                failed = True
                print(
                    f"[{grammar_name}/{op_name}] error: non-string output encountered"
                )
                print()
            if not changed:
                failed = True
                print(f"[{grammar_name}/{op_name}] error: no output changed from seed")
                print()

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
