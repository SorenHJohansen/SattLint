# Maintainer CI

Keep CI small and predictable.

## Workflow Layout

- `.github/workflows/ci.yml` - default pull-request and main-branch validation
- `.github/workflows/nightly.yml` - scheduled full-health pass and artifact snapshot
- `.github/workflows/publish.yml` - build and publish flow for releases
- `.github/actions/setup-ci-tooling/action.yml` - shared Python, uv, Node, markdownlint, and actionlint setup

## Default Validation Path

- `ci.yml` is the normal required workflow.
- `nightly.yml` is where the heavier recurring health snapshot lives.
- `publish.yml` stays release-focused and avoids duplicating normal validation.

AI-touched files are blocked locally through `.github/hooks/ai-edit-gate.json` and `scripts/run_ai_edit_gate.py`, which reuses `scripts/check_ratchet_policy.py` for touched-file policy checks.

## Required Script Entrypoints

- `scripts/context_health.py`
- `scripts/repo_health.py`
- `scripts/check_ratchet_policy.py`
- `scripts/install_actionlint.py`
- `scripts/run_repo_python.py`

Keep this list small. If a script stops being CI-owned, remove its final workflow reference and remove it from this page in the same change.
