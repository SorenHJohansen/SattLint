# Testing

Tests are the executable contract for SattLint. A behavior change needs a test
that fails without the change, and a bug fix needs a regression test that
captures the failure.

## Running tests

Use the locked environment:

```bash
uv run python -m pytest -q --tb=short
```

Or the active virtual environment:

```bash
python -m pytest -q --tb=short
```

Useful forms:

```bash
# One module
python -m pytest tests/app/test_cli.py -q --tb=short

# One owner directory
python -m pytest tests/analyzers -q --tb=short

# One test by name
python -m pytest -q -k "variable_usage"

# Skip slow tests
python -m pytest -q -m "not slow"
```

The suite enforces a 60-second per-test timeout. A stalled test fails rather
than hanging a CI job.

## Markers

| Marker | Use |
| --- | --- |
| `slow` | Long-running tests, deselectable with `-m "not slow"`. |
| `integration` | Tests that combine multiple layers. |
| `unit` | Focused unit tests. |
| `parser` | Parser-surface behavior. |
| `analyzer` | Analyzer behavior. |

Markers are strict: an unregistered marker is a configuration error.

## Test map

| Directory | Owns |
| --- | --- |
| `tests/analyzers/` | Analyzer rules, registry invariants, architecture guards, cross-analyzer suites. |
| `tests/app/` | CLI routing, headless payloads, Textual shell, menus, analysis workflows, configuration UI. |
| `tests/cache/` | Cache keys, integrity, resilience, payload classes. |
| `tests/change_review/` | Semantic diff, normalization, review generation. |
| `tests/core/` | Semantic snapshot, symbol table, type graph, call signatures, syntax, profiling, origin matching. |
| `tests/corpus/` | Corpus manifests, differential reporting, crash sweeps, production imports. |
| `tests/graphics/` | Graphics companion paths, PictureDisplay assets and runtime. |
| `tests/models/` | Issue model records. |
| `tests/project/` | Project I/O, parser adapter, graph invariants, migration, string capacities, failure state. |
| `tests/reporting/` | Report rendering and labels. |
| `tests/runs/` | Run store behavior. |
| `tests/helpers/` | Shared test support. Not a test suite itself. |
| `tests/fixtures/` | SattLine samples, projects, corpus inputs, analyzer guardrail fixtures, parser surface fixtures. |

Cross-cutting guard suites:

- `tests/test_dependency_guard.py` checks layering and parser import boundaries.
- `tests/test_casefolding_guard.py` checks case-insensitive comparison rules.
- `tests/test_corpus_analyzers.py` exercises analyzers over the corpus.

## Choosing the first check

Start with the owning suite:

| Change | First check |
| --- | --- |
| CLI routing or argparse | `tests/app/test_cli.py` |
| Headless commands and JSON | `tests/app/test_cli_headless.py` |
| Analysis workflow | `tests/app/test_analysis_*.py` |
| Textual shell | `tests/app/test_app_textual*.py` |
| Analyzer rule | `tests/analyzers/test_<rule>.py` |
| Analyzer registry invariants | `tests/analyzers/test_analyzer_guardrails.py` |
| Project or configuration loading | `tests/project/` and `tests/app/test_cli_config.py` |
| ICF or graphics | `python -m pytest -k "icf or graphics"` |
| Cache keys or cache integrity | `tests/cache/` |
| Change Review | `tests/change_review/` |
| Semantic snapshot or resolution | `tests/core/` |
| Run store | `tests/runs/` |

Then widen to Ruff, Pyright, and the full suite.

## Fixtures

Fixtures are public and must stay safe to publish:

- use synthetic names;
- do not include customer names, private paths, or internal identifiers;
- keep a fixture minimal enough to explain the behavior it proves;
- prefer a named fixture over a large inline source string when the test is
  about analyzer behavior;
- add a corpus case when a parser or analyzer regression needs realistic shape.

Useful fixture groups:

- `tests/fixtures/sample_sattline_files/` for broad sample programs and
  libraries;
- `tests/fixtures/projects/` for `.slproj` variants such as standard and custom
  string capacities;
- `tests/fixtures/corpus/` for corpus inputs and manifests;
- `tests/fixtures/analyzer_guardrails/` for analyzer invariant cases;
- `tests/fixtures/parser_surface/` for parser API shape checks;
- `tests/fixtures/sample_pds_scripts/` for PDS script samples.

## Test helpers

Shared helpers live in `tests/helpers/`. They cover:

- stubs for parser and application seams;
- project fixtures;
- Textual support;
- variable and access contract support;
- graphics attachment support;
- Change Review support.

A helper that is used by two suites belongs in `tests/helpers/`, not copied
between test modules.

## Coverage

CI enforces an aggregate coverage floor of 80 percent on the Linux gate. The
broader project target is 100 percent focused coverage for the touched slice.
Coverage is necessary but not sufficient: a test that executes a line without
asserting behavior does not prove the contract.

## Fuzzing

SattLint owns two input readers that are fuzzed with Atheris:

| Target | Reader | Format |
| --- | --- | --- |
| `scripts/fuzz/icf_fuzzer.py` | ICF decoding and parsing | `.icf` |
| `scripts/fuzz/graphics_fuzzer.py` | Graphics validation | `.g` / `.y` |

The fuzzers do not target the external parser grammar; that package owns its own
fuzzing. A crash in a SattLint-owned reader is a real failure.

Local run:

```bash
python -m pip install -e ".[fuzz]"
python scripts/fuzz/icf_fuzzer.py -runs=100000 -max_len=4096
python scripts/fuzz/graphics_fuzzer.py -runs=100000 -max_len=4096
```

Atheris requires Linux and Python 3.11 or newer; CI runs bounded smoke runs on
Linux x86_64.

## Related pages

- [Development](development.md)
- [CI and release](ci-and-release.md)
- [Documentation maintenance](documentation.md)
