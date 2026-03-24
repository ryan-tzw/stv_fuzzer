"""
Fuzzing engine: orchestrates the main fuzzing loop.
"""

import time
from datetime import datetime

from fuzzer.config import FuzzerConfig
from fuzzer.core import CorpusManager, Mutator
from fuzzer.core.scheduler import FastScheduler, RandomScheduler, Scheduler
from fuzzer.executors import PersistentCoverageExecutor
from fuzzer.feedback import CoverageFeedback
from fuzzer.logger import FuzzerLogger
from fuzzer.observers.python_coverage import (
    InProcessCoverageObserver,
)
from fuzzer.storage.database import FuzzerDatabase


class FuzzingEngine:
    def __init__(self, config: FuzzerConfig):
        self.config = config

        # Pre-register known grammars
        self._register_grammars()

        # Set up run output directory and database
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir = config.runs_dir / run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)

        self.db = FuzzerDatabase(self.run_dir / "results.db")
        self.corpus = CorpusManager(
            config.corpus_dir, self.db, self.config.grammar, self.config.generator_dir
        )
        self.mutator = self._build_mutator()
        self.scheduler = self._build_scheduler()
        self.executor = PersistentCoverageExecutor(
            config.project_dir, config.harness_path
        )
        self.observer = InProcessCoverageObserver(config.project_dir)
        self.feedback = CoverageFeedback()
        self.logger = FuzzerLogger(self.run_dir, config)

    def _register_grammars(self):
        """Pre-register JSON and IP grammars with custom implementations."""
        try:
            from fuzzer.grammars.grammarRegistry import register_grammar
            from fuzzer.grammars.astBuilder import jsonAstBuilder, ipAstBuilder
            from fuzzer.grammars.operations import (
                JsonGrammarOperations,
                IpGrammarOperations,
            )
            from fuzzer.grammars.unparser import jsonUnparser, ipUnparser

            try:
                from fuzzer.grammars.antlr.json.jsonLexer import jsonLexer
                from fuzzer.grammars.antlr.json.jsonParser import (
                    jsonParser as JSONParser,
                )
                from fuzzer.grammars.antlr.ip.ipLexer import ipLexer
                from fuzzer.grammars.antlr.ip.ipParser import ipParser as IPParser
            except ImportError:
                return
            # Register JSON
            register_grammar(
                "json",
                parser_class=JSONParser,
                lexer_class=jsonLexer,
                ast_builder_class=jsonAstBuilder,
                operations_class=JsonGrammarOperations,
                unparser_class=jsonUnparser,
            )
            # Register IP
            register_grammar(
                "ip",
                parser_class=IPParser,
                lexer_class=ipLexer,
                ast_builder_class=ipAstBuilder,
                operations_class=IpGrammarOperations,
                unparser_class=ipUnparser,
            )
        except Exception as e:
            print(f"[!] Warning: Could not register grammars: {e}")

    def _build_mutator(self) -> Mutator:
        """Build mutator using grammar registry - works with ANY ANTLR grammar."""
        from fuzzer.core.mutator.strategies import BlindRandomStrategy, GrammarStrategy
        from fuzzer.grammars.parser.parser import create_parser
        from fuzzer.grammars.grammarRegistry import get_registry
        from fuzzer.grammars.operations import GenericGrammarOperations

        if not self.config.grammar:
            return Mutator(strategy=BlindRandomStrategy())
        try:
            parser = create_parser(self.config.grammar, self.config.antlr_dir)
            registry = get_registry()
            grammar_config = registry.get(self.config.grammar)
            if grammar_config and grammar_config.get("operations_class"):
                ops = grammar_config["operations_class"]()
            else:
                ops = GenericGrammarOperations()
            return Mutator(strategy=GrammarStrategy(parser, ops))
        except Exception:
            return Mutator(strategy=BlindRandomStrategy())

    def _build_scheduler(self) -> Scheduler:
        if self.config.scheduler == "fast":
            return FastScheduler(
                c=self.config.energy_c, max_energy=self.config.max_energy
            )
        elif self.config.scheduler == "random":
            return RandomScheduler()
        else:
            raise ValueError(f"Unknown scheduler: {self.config.scheduler!r}")

    def run(self) -> None:
        self.corpus.load()

        iteration = 0
        unique_crashes = 0
        start_time = time.monotonic()

        with self.logger:
            self.logger.start(corpus_size=len(self.corpus.seeds()))

            try:
                while True:
                    # Check stopping conditions
                    if (
                        self.config.max_iterations != -1
                        and iteration >= self.config.max_iterations
                    ):
                        self.logger.log_stop_reason(
                            f"reached max iterations ({self.config.max_iterations})"
                        )
                        break
                    if self.config.time_limit != -1:
                        elapsed = time.monotonic() - start_time
                        if elapsed >= self.config.time_limit:
                            self.logger.log_stop_reason(
                                f"reached time limit ({self.config.time_limit}s)"
                            )
                            break

                    # Pick seed and compute energy
                    seed = self.scheduler.next(self.corpus.seeds())
                    self.corpus.record_picked(seed)
                    energy = self.scheduler.energy(seed)

                    for _ in range(energy):
                        mutated = self.mutator.mutate(
                            seed.data, depth=self.config.mutate_depth
                        )

                        stdout, stderr, coverage_file = self.executor.run(mutated)
                        self.corpus.record_fuzzed(seed)

                        signal = self.observer.observe(coverage_file)
                        result = self.feedback.evaluate(signal, stderr)

                        if result.is_crash:
                            is_new = self.db.record_crash(mutated, stderr)
                            if is_new:
                                unique_crashes += 1
                                self.logger.log_crash(iteration, unique_crashes)
                            else:
                                self.logger.log_duplicate_crash(iteration)

                        if result.add_to_corpus:
                            self.corpus.add(mutated)
                            self.logger.log_corpus_add(iteration)

                        iteration += 1
                        self.logger.tick(iteration)

            except KeyboardInterrupt:
                self.logger.log_stop_reason("interrupted by user")

            finally:
                self.db.flush_corpus(self.corpus.seeds())
                self.db.close()

        elapsed = time.monotonic() - start_time
        self.logger.print_summary(iteration, elapsed)
