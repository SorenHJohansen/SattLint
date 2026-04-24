---
description: "Use when changing Python tests in SattLint. Covers focused pytest routing, fixture reuse, and stable assertion patterns for repo-venv workflows."
name: "Python Test Instructions"
applyTo: ["tests/test_*.py", "tests/helpers/**"]
---
# Python Tests

- Start with the narrowest pytest module or test name that covers the touched behavior.
- Run focused pytest through the repo venv as routed by [validation map](../skills/validation-routing/references/validation-map.md); do not start with the VS Code test runner.
- Reuse existing helpers and fixtures before adding new scaffolding.
- Prefer deterministic assertions on findings, artifact fragments, or explicit fields over broad snapshot-style checks.
- If production behavior changes, update the nearest existing test module before adding broader regression coverage.
