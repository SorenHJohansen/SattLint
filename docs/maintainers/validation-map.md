# Validation Map

Canonical first-check command source for SattLint maintainer surfaces.

- Parser, grammar, transformer, AST, or strict validation:
  `python -m pytest tests/test_cli.py -x -q --tb=short`
  or `sattlint syntax-check <target>`
- CLI routing or argparse behavior:
  `python -m pytest tests/test_cli.py -x -q --tb=short`
- Interactive / menu / Textual app behavior:
  `python -m pytest tests/test_app_analysis_part*.py tests/test_app_textual.py tests/test_cli.py -x -q --tb=short`
- Analyzer behavior (rule-specific):
  `python -m pytest tests/analyzers/test_<rule>.py -x -q --tb=short`
- Analyzer registry / guardrail invariants:
  `python -m pytest tests/test_analyzer_guardrails.py -x -q --tb=short`
- Project / config loading:
  `python -m pytest tests/test_project*.py -x -q --tb=short`
- ICF and graphics analysis:
  `python -m pytest -k icf or -k graphics -x -q --tb=short`
- Python behavior with a nearby focused test:
  `python -m pytest <test_file> -x -q --tb=short`
- Finish gate for touched Python files:
  `python -m ruff check <touched_python_files>`
  then
  `python -m pyright <touched_python_files>`
- Fast local hygiene gate:
  `python -m pre_commit run --all-files`
- Full local validation before push:
  `python -m ruff check . && python -m ruff format --check . && python -m pyright src/sattlint && python -m pytest -q --tb=short`
