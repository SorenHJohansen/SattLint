---
description: "Use when changing Python tests in SattLint. Covers focused pytest routing, fixture reuse, and stable assertion patterns for repo-venv workflows."
name: "Python Test Instructions"
applyTo: ["tests/**/*.py", "tests/helpers/**"]
---
# Python Tests

- Start with the narrowest pytest module or test name that covers the touched behavior.
- Run focused pytest through the repo venv as routed by [validation map](../../docs/maintainers/validation-map.md); do not start with the VS Code test runner.
- Reuse existing helpers and fixtures before adding new scaffolding.
- Prefer `@pytest.mark.parametrize` when the assertion shape stays the same across multiple inputs; collapse copy-paste cases before adding another near-duplicate test body.
- Use the repo's defined pytest markers (`unit`, `integration`, `parser`, `analyzer`, `slow`) intentionally when they improve routing or selection, and keep them truthful because pytest runs with `--strict-markers`.
- Keep test state isolated. Reset globals and caches, tear down threads or background workers, and avoid mutable shared fixtures unless the shared state itself is the behavior under test.
- Prefer deterministic assertions on findings, artifact fragments, or explicit fields over broad snapshot-style checks.
- If production behavior changes, update the nearest existing test module before adding broader regression coverage.
