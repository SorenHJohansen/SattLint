---
description: "Use when changing sattlint CLI routing, argparse surfaces, interactive app menus, config flows, or console UX in SattLint. Covers menu and command invariants plus test routing."
name: "CLI App Instructions"
applyTo: ["src/sattlint/app.py", "src/sattlint/config.py", "tests/test_cli.py", "tests/test_app*.py"]
---
# CLI App

- Keep CLI flags, menu numbering, and prompt flows aligned with tests.
- Installed `sattlint` must still call `app.cli()` and `app.main()` without argv must still open the interactive menu.
- Prefer repo-venv command paths so CLI behavior matches installed entrypoints.
- Choose the first focused validation route from [validation map](../skills/validation-routing/references/validation-map.md) and match it to CLI routing versus interactive menu behavior.
- Do not use the VS Code test runner as the first validation path here.
