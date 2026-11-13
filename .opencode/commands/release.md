---
description: Prepare a SattLint release
---

Prepare release `$ARGUMENTS` for SattLint. Treat the argument as the calendar
version (`YYYY.M.N`). If it is empty, derive the next version from
`src/sattlint/__version__.py` and `CHANGELOG.md`, then propose it before
changing files.

Checklist:

1. Read `AGENTS.md`, `AGENTS_REFERENCE.md`, and the current `CHANGELOG.md`.
2. Confirm the version is not already released.
3. Confirm the parser pin matches the supported parser release.
4. Update `src/sattlint/__version__.py`.
5. Move the `Unreleased` entries under the new version and date, and leave a
   fresh `Unreleased` section.
6. Run the full verification ladder from `/verify`.
7. Build the artifacts with `python -m build` and run
   `python -m twine check dist/*`.
8. Smoke-test the built wheel in a clean environment.
9. Propose the exact tag and publish commands, then wait for explicit permission.
   A `v*` tag push publishes to PyPI.

Do not commit, push, tag, publish, or create a GitHub release without explicit
permission for that specific action. Propose the exact commands, then wait.
