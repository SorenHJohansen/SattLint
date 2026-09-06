# Releasing SattLint

This document is the release procedure for SattLint. Releases are cut from
`main` by tagging a commit with `vX.Y.Z`; the `Publish` workflow
(`.github/workflows/publish.yml`) builds, gates, and publishes to PyPI.

## Versioning

SattLint follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
The version is single-sourced from `src/sattlint/__version__.py` and read
dynamically by `pyproject.toml` (`tool.setuptools.dynamic`).

Classifier decision (recorded 2026-09-05): `Development Status :: 5 -
Production/Stable` is asserted in `pyproject.toml` because the imminent 1.0.0
release is the intended stable state. Re-evaluate if a release is delayed
significantly; `4 - Beta` is the fallback until a tag exists.

## Pre-release checklist

Run every item and confirm before tagging:

- [ ] Working tree is clean on `main` (or the release branch is fully merged).
- [ ] Full local gate is green:
      `python -m pre_commit run --all-files`,
      `python -m ruff check .`,
      `python -m ruff format --check .`,
      `python -m pyright src/sattlint`,
      `python -m pytest -q --tb=short`.
- [ ] `CHANGELOG.md` has a dated `## [X.Y.Z]` entry for the release and the
      `[Unreleased]` block is empty.
- [ ] `sattlint --version` reports the intended version.
- [ ] `python -m build` and `python -m twine check dist/*` pass with no
      warnings (including no license deprecation warning).
- [ ] Documentation references match the shipped surface (commands, paths,
      exit codes). See `docs/exec-plans/release-1.0-and-doc-alignment.md`.

## PyPI environment protection (manual, GitHub settings)

`publish.yml` targets the `pypi-release` deployment environment. Trusted
publishing (OIDC) is enabled, but **required-reviewer protection is not
configured in the repository**. Before the first production release, configure
the environment in GitHub settings:

1. Open **Settings > Environments > pypi-release**.
2. Add **Required reviewers** (at least one account with write access).
3. Optionally restrict the deployment branch to `main`.

Until a reviewer is configured, a tag push can publish without human review.
Verify with:

```sh
gh api repos/SorenHJohansen/SattLint/environments/pypi-release \
  --jq '.protection_rules[].type'
```

## Tag and publish

The `Publish` workflow runs the full CI gate (`ci.yml` as a reusable workflow)
on the tagged commit before building. A tag on a commit whose CI gate fails
cannot proceed to `build`.

```sh
# From a clean main
git tag v1.0.0
git push origin v1.0.0
```

The workflow then:

1. Runs the CI gate on the tagged commit.
2. Builds sdist + wheel and runs `twine check`.
3. Runs a clean-venv smoke (`--version`, `--help`, one `syntax-check`).
4. Publishes to PyPI via trusted publishing.

## Post-publish verification

- [ ] `pipx install sattlint` (or `pipx upgrade sattlint`) succeeds.
- [ ] `sattlint --version` reports the released version.
- [ ] `sattlint --help` lists the documented commands.
- [ ] `sattlint syntax-check <sample.s>` behaves as documented.
- [ ] Create a GitHub Release for the tag with the CHANGELOG entry as notes
      (the `Publish` workflow does not create releases automatically).
