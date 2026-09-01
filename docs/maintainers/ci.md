# Maintainer CI

Keep CI small and predictable.

## Workflow Layout

- `.github/workflows/ci.yml` - default pull-request and main-branch validation (clean install, Ruff, Pyright, full pytest, clean-wheel smoke on Linux and Windows)
- `.github/workflows/publish.yml` - build and publish flow for releases

## Default Validation Path

- `ci.yml` is the normal required workflow.
- `publish.yml` stays release-focused and avoids duplicating normal validation.

Required gates in `ci.yml`:

- Ruff lint and format check
- Pyright on `src/sattlint`
- Full pytest suite
- Clean-wheel install and `sattlint` command smokes (Linux and Windows)

No required command masks failures (`|| true`, `continue-on-error`, or equivalent).
