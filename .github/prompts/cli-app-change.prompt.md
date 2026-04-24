---
description: "Fix or change sattlint CLI routing, argparse behavior, interactive menus, config flows, or console UX using the CLI specialist"
name: "CLI App Change"
argument-hint: "Describe CLI or app-menu change to make"
agent: "CLI App Menu"
---
Investigate and implement the requested CLI, app-menu, or console UX change in SattLint.

Requirements:
- Read `.github/coordination/current-work.md` before first edit and claim touched files when useful.
- Anchor on `src/sattlint/app.py` or the nearest controlling CLI/config entry point instead of broad repo exploration.
- Preserve console entrypoint behavior: installed `sattlint` still routes through `app.cli()` and `app.main()` with no argv still opens the interactive menu unless the request explicitly changes that behavior.
- Choose the first focused validation route from [validation map](../skills/validation-routing/references/validation-map.md) and matching CLI instructions.
- Report changed files, validation run, and any menu numbering, prompt-flow, or CLI-surface changes that downstream tests must absorb.
