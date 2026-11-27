# CI and Release

GitHub Actions is the trust boundary. A pull request runs the full gate, `main`
runs the same gate on every push, and a release tag runs the gate again before
publishing. Supported interpreters are Python 3.13 and 3.14; supported
desktop platforms are Linux and Windows.

## Workflows

| Workflow | Trigger | Purpose |
| --- | --- | --- |
| `ci.yml` | Pull request, push to `main`, manual, reusable call | Lint, type-check, test, fuzz, dependency audit, docs checks, packaging on 3.13 and 3.14. |
| `publish.yml` | `v*` tag or manual dispatch | Run the release gate, check tag ancestry, build, verify metadata and reproducibility, smoke both artifacts, publish to PyPI. |
| `scorecard.yml` | Weekly schedule and push to `main` | OpenSSF supply-chain analysis. |

## CI jobs

### Linux gate

1. Check out the repository.
2. Install Python 3.13.
3. Install `uv` with a cache keyed by `uv.lock`.
4. Install the locked development environment.
5. Run Ruff lint.
6. Run Ruff format check.
7. Run Pyright on production code and tests.
8. Run the release state check; for a tag, verify the tag matches the package
   version.
9. Run the pre-commit hygiene hooks, skipping the hooks already run directly.
10. Run the full pytest suite with coverage and an 80 percent floor.
11. Build a wheel, install it into a clean virtual environment, and smoke the
    package version, the UI import, and the CLI entry point. The packaging
    matrix below proves the wheel and the sdist on both supported interpreters;
    this step is the quick 3.13 smoke inside the gate.

### Windows gate

Runs the same lint, format, type, test, and clean-wheel smoke path on Windows.
It does not run the coverage floor or the fuzz jobs.

### Packaging matrix

Runs on Python 3.13 and 3.14. Each job:

1. Sets `SOURCE_DATE_EPOCH` to a fixed instant.
2. Builds the wheel and the sdist twice. The wheel is compared byte for byte,
   so a build that embeds wall-clock time fails the job. The sdist backend
   stamps its archive metadata with the build instant, so the two sdists are
   compared by member names and member bytes instead.
3. Runs `twine check` over both artifacts.
4. Installs the wheel and the sdist into separate clean virtual environments,
   then runs `sattlint --version` and `sattlint analyzers list` from each.
5. Asserts the sdist carries the changelog, the license, the readme, and the
   packaged stylesheet, and carries no tests, docs, scripts, workflow files, or
   generated `egg-info` files beyond the `SOURCES.txt` setuptools appends.
6. Asserts the wheel carries `sattlint/ui/app_textual.tcss` and the packaged
   `sattlint/assets` files. This is the check that catches a wheel built
   without its package data, because the UI import falls back instead of
   failing.

### Fuzz smoke

Runs the ICF and graphics fuzz targets on Linux x86_64 with a bounded run count
and a time limit. A crash in a SattLint-owned reader fails the job.

### Dependency audit

Runs `pip-audit` against the locked dependency set.

### Docs

1. Runs markdownlint over the configured Markdown files.
2. Runs `scripts/check_docs.py`.

The docs checker validates:

- every relative link target exists;
- every relative anchor resolves to a heading in the target Markdown file;
- every Markdown file under `docs/` is linked from `docs/README.md`.

Markdown style and documentation reachability are part of the required gate, so
a broken link cannot merge.

## Local equivalents

```bash
python -m pre_commit run --all-files
python -m ruff check .
python -m ruff format --check .
python -m pyright src/sattlint tests
python -m pytest -q --tb=short
python scripts/check_docs.py
```

Run markdownlint through pre-commit when the hook is installed, or through the
same markdownlint configuration used by CI.

## Distribution contents

`MANIFEST.in` gives the source distribution an explicit policy:

- included: `CHANGELOG.md`, `LICENSE`, `README.md`, the package sources under
  `src/sattlint`, and the packaged assets including `app_textual.tcss`;
- excluded: `tests/`, `docs/`, `scripts/`, `.github/`, and generated
  `egg-info` files. Setuptools appends `src/sattlint.egg-info/SOURCES.txt`
  after the manifest runs; that file is the only `egg-info` member in the
  archive.

The wheel carries the same package and asset set through
`[tool.setuptools.package-data]`. The packaging matrix installs the sdist as
well as the wheel, asserts the wheel carries the stylesheet and package assets,
and fails when either archive would ship an incomplete install. The build
backend is pinned in `[build-system]` so the wheel comparison measures the
project, not a backend release that happened between two builds.

## Versioning

SattLint uses calendar versioning:

```text
vYYYY.M.number
```

`YYYY` is the year, `M` is the month, and `number` is the release count within
that month. The package version is single-sourced from
`src/sattlint/__version__.py` and read dynamically by `pyproject.toml`.

## Release checklist

1. Confirm `main` is clean and fully merged.
2. Run the full local gate.
3. Confirm `CHANGELOG.md` has a dated entry for the release and that the
   unreleased block is empty.
4. Confirm `sattlint --version` reports the intended version.
5. Confirm `python -m build` and `python -m twine check dist/*` pass, and that
   two builds with the same `SOURCE_DATE_EPOCH` produce an identical wheel and
   identical sdist member contents.
6. Confirm documentation matches the shipped commands, paths, exit codes, and
   configuration.
7. Confirm the release commit is an ancestor of `main`.
8. Tag the commit:

   ```bash
   git tag vYYYY.M.number
   git push origin vYYYY.M.number
   ```

## Publish workflow

The publish workflow:

1. Runs `ci.yml` as the release gate.
2. Checks that the package version matches the tag, or the expected version
   supplied to a manual dispatch.
3. For a tag, checks that the tagged commit is an ancestor of `main`, so a tag
   on a side branch cannot publish code that never passed the main gate.
4. Builds the source distribution and wheel.
5. Runs `twine check`.
6. Installs the wheel into a clean environment and smokes the package version,
   the UI import, the CLI entry point, and `sattlint --version`.
7. Uploads the distributions.
8. Publishes to PyPI through trusted publishing when the trigger is a `v*` tag.

A workflow-level concurrency group serializes every publish run and never
cancels an in-progress publish. A manual dispatch builds and validates without
publishing. Re-running a publish fails when the version already exists; it never
reports a false success.

## Environment protection

The `pypi-release` environment is restricted to tags matching `v*`. A release
tag ruleset blocks moving or deleting an existing release tag. Re-check both
settings after a repository transfer or environment rename.

## Post-publish verification

- `pipx install sattlint` or `pipx upgrade sattlint` succeeds.
- `sattlint --version` reports the released version.
- `sattlint --help` lists the documented commands.
- `sattlint analyzers list` works without a project.
- The GitHub Release is created manually from the tag, using the changelog
  entry as release notes.

## Related pages

- [Testing](testing.md)
- [Development](development.md)
- [Documentation maintenance](documentation.md)
