# Adopting SattLint in CI

This page is a minimal, runnable adoption path for a team that already has a
checked-in `.slproj` file. It installs SattLint, validates the project, runs the
analyzers, publishes SARIF to code scanning, and archives the Change Review.

## Minimal workflow

Put this in `.github/workflows/sattlint.yml` in the repository that holds the
SattLine code and the `.slproj` file:

```yaml
name: SattLint

on:
  push:
  pull_request:

permissions:
  contents: read
  security-events: write

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"

      - name: Install SattLint
        run: pipx install sattlint

      - name: Validate the project
        run: sattlint project check

      - name: Analyze and write SARIF
        run: sattlint analyze --fail-on warning --format sarif --output build/sattlint.sarif

      - name: Upload SARIF
        if: always()
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: build/sattlint.sarif
```

`sattlint` discovers the `.slproj` file from the repository root. Pass
`--project PATH` if the file lives elsewhere.

## What each step proves

- `project check` validates the schema, the configured roots, and target
  identity without running analyzers. It exits `1` when the project needs a fix.
- `analyze --fail-on warning` fails the job on a correctness defect or a risky
  pattern, while naming and design advice stays visible as `info`.
- `--format sarif` writes a SARIF 2.1.0 document. A finding with no source
  location is a document-level result and is never given a fake position.
- `--output build/sattlint.sarif` creates the missing `build/` directory. The
  same is true for `review --output-dir` and the review output directory.

## Baseline the known findings

On the first adoption, accept the current findings and commit the baseline:

```bash
sattlint analyze --format json --fail-on none --output build/findings.json
sattlint baseline update --run latest
git add .sattlint-baseline.json
git commit -m "Record the SattLint baseline"
```

After that, gate only on new or more severe findings:

```bash
sattlint analyze --fail-on warning --baseline .sattlint-baseline.json
```

A stale baseline entry is reported, never fatal. `sattlint baseline update`
prunes entries that no longer occur.

## Change Review artifacts

The review command writes the official JSON and Markdown artifacts and creates
its output directory when it is missing:

```yaml
      - name: Generate Change Review
        run: sattlint review --output-dir change-review --format json --quiet

      - name: Upload Change Review
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: change-review
          path: change-review/
```

- `0`: every selected target generated both artifacts.
- `1`: a partial review; the artifacts that were generated are still uploaded.
- `2`: a missing project, no selected target, or an unusable output directory.

## Query the stored history

The run store is local to the machine or runner. In CI it is useful for a
follow-up step in the same job, not as a cross-run database:

```bash
sattlint runs list --format json
sattlint findings --run latest --group-by target --format json
```

Use `sattlint runs prune` to remove records this build cannot read. A plain
prune never deletes a readable run; `--keep N` adds a bounded retention cut.

## Related pages

- [CLI reference](cli.md)
- [Change Review](change-review.md)
- [Caching and runs](caching-and-runs.md)
- [CI and release](ci-and-release.md) for SattLint's own pipeline
