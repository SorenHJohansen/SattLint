# Validation Map

Canonical first-check command source for SattLint customization surfaces. Use first matching rule.

- Parser, grammar, transformer, AST, or strict validation:
  `python scripts/run_repo_python.py -m sattlint syntax-check <target>`
- Workspace, semantic core, editor facade, LSP, or VS Code client:
  `python scripts/run_repo_python.py -m pytest <test_file> -x -q --tb=short`
  then restart with `sattlineLsp.restartServer` if touched surface requires it.
- CLI routing or argparse behavior:
  `python scripts/run_repo_python.py -m pytest --no-cov tests/test_cli.py -x -q --tb=short`
- CLI menu, prompt, or interactive app behavior:
  `python scripts/run_repo_python.py -m pytest --no-cov tests/test_app_menus.py tests/test_app_analysis.py tests/test_cli.py -x -q --tb=short`
- Documentation generation or classification behavior:
  `python scripts/run_repo_python.py -m pytest --no-cov tests/test_docgen.py -x -q --tb=short`
  add `tests/test_app_docgen.py` or `tests/test_app_menus.py` when docgen entry points changed.
- Repo audit or devtools pipeline:
  `python scripts/run_repo_python.py -m sattlint.devtools.repo_audit --profile quick --output-dir artifacts/audit`
  or focused pytest such as `tests/test_repo_audit.py` or `tests/test_pipeline.py` when that is narrower.
- Python behavior with a nearby focused test:
  `python scripts/run_repo_python.py -m pytest <test_file> -x -q --tb=short`
- Finish gate for touched Python files:
  `python scripts/run_repo_python.py -m ruff check <touched_python_files>`
  then
  `python scripts/run_repo_python.py -m pyright <touched_python_files>`
- Shared infra, repo-audit, hooks, or cross-subsystem Python wiring after focused checks:
  owner-suite validation or `python scripts/run_repo_python.py -m sattlint.devtools.repo_audit --profile quick --output-dir artifacts/audit`
- Fast local hygiene gate:
  `python scripts/run_repo_python.py -m pre_commit run --all-files`
- Local pre-push gate:
  `python scripts/run_repo_python.py -m sattlint.devtools.repo_audit --profile full --check-my-changes --output-dir artifacts/audit`
- Full gate procedure and reporting live in `Repo Verify`.
