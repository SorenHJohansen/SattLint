# Validation Map

Canonical first-check command source for SattLint customization surfaces. Use first matching rule.

- Parser, grammar, transformer, AST, or strict validation:
  `& ".venv/Scripts/sattlint.exe" syntax-check <target>`
- Workspace, semantic core, editor facade, LSP, or VS Code client:
  `& ".venv/Scripts/python.exe" -m pytest <test_file> -x -q --tb=short`
  then restart with `sattlineLsp.restartServer` if touched surface requires it.
- CLI routing or argparse behavior:
  `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_cli.py -x -q --tb=short`
- CLI menu, prompt, or interactive app behavior:
  `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_app.py tests/test_app_menus.py tests/test_app_analysis.py -x -q --tb=short`
- Documentation generation or classification behavior:
  `& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_docgen.py -x -q --tb=short`
  add `tests/test_app.py` or `tests/test_gui.py` when docgen entry points changed.
- Repo audit or devtools pipeline:
  `& ".venv/Scripts/sattlint-repo-audit.exe" --profile quick --output-dir artifacts/audit`
  or focused pytest such as `tests/test_repo_audit.py` or `tests/test_pipeline.py` when that is narrower.
- Python behavior with a nearby focused test:
  `& ".venv/Scripts/python.exe" -m pytest <test_file> -x -q --tb=short`
- Final repo gate:
  `& ".venv/Scripts/pre-commit.exe" run --all-files`
  then
  `& ".venv/Scripts/python.exe" -m pytest`
  Full gate procedure and reporting live in `Repo Verify`.
