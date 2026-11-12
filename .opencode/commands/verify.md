---
description: Run the SattLint verification ladder
---

Verify the current change in SattLint. Treat `$ARGUMENTS` as an optional scope
hint (a file, a test path, or a subsystem).

Run these checks in order. Use the repository virtual environment when one
exists, otherwise use the project Python.

1. Run the smallest focused test that covers the change.
2. Run `python -m ruff check .`
3. Run `python -m ruff format --check .`
4. Run `python -m pyright src/sattlint tests`
5. Run `python -m pytest -q --tb=short`
6. If packaging, version, or dependencies changed, run `python -m build` and
   `python -m twine check dist/*`.
7. If Markdown changed, run `python -m pre_commit run --all-files`.

Report each command and its result. If a check fails, stop and report the failure
with the exact command and output. Do not fix unrelated failures.
