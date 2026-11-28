---
description: "Use when changing sattlint CLI routing, argparse surfaces, interactive app menus, config flows, or console UX in SattLint. Covers menu and command invariants plus test routing."
name: "CLI App Instructions"
applyTo: ["src/sattlint/cli/**", "src/sattlint/config/**", "src/sattlint/application/**", "tests/app/test_cli*.py", "tests/app/test_app*.py"]
---
# CLI App

- Keep CLI flags, headless JSON payloads, menu numbering, and prompt flows aligned with tests.
- Installed `sattlint` must dispatch headless subcommands when given arguments. With no arguments it opens the Textual interactive shell only when stdin and stdout are terminals, and otherwise prints the usage and exits 2.
- `sattlint project check` validates the project schema, configured roots, and target identity without analysis; language and parse validation belong to `sattline-parser`.
- Prefer repo-venv command paths so CLI behavior matches installed entrypoints.
- Choose the first focused validation route from [validation map](../../AGENTS_REFERENCE.md#validation-map) and match it to CLI routing versus Textual interactive-shell behavior.
- Do not use the VS Code test runner as the first validation path here.
