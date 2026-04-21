# Corpus Fixtures

This directory is reserved for corpus-backed analyzer and pipeline validation.

Suggested layout:

- `valid/` for fixtures expected to parse and analyze successfully
- `invalid/` for fixtures expected to fail strict validation
- `edge_cases/` for high-risk semantics and parser corner cases
- `manifests/` for JSON manifests consumed by `sattlint.devtools.corpus`

Minimal manifest shape:

```json
{
  "case_id": "unused-variable",
  "target_file": "tests/fixtures/corpus/valid/UnusedVariable.s",
  "mode": "workspace",
  "expectation": {
    "expected_finding_ids": ["unused"],
    "forbidden_finding_ids": ["secret-assignment"],
    "artifact_fragments": {
      "status.json": {
        "execution_status": "ok"
      },
      "summary.json": {
        "rule_counts": {
          "unused": 1
        }
      }
    }
  },
  "required_artifacts": ["findings.json"]
}
```

Execution:

- `sattlint-corpus-runner --manifest-dir tests/fixtures/corpus/manifests --output-dir artifacts/analysis`

Included starter manifests:

- `manifests/strict-invalid.json` expects a strict parse failure from `invalid/NotSattLine.s`.
- `manifests/workspace-common-quality-issues.json` expects semantic findings from `tests/fixtures/sample_sattline_files/CommonQualityIssues.s`.

Outputs:

- `artifacts/analysis/corpus_results.json` aggregates pass or fail status across all manifests.
- `artifacts/analysis/corpus_cases/<case_id>/` stores each case's `findings.json`, `status.json`, and `summary.json`.
- `expectation.artifact_fragments` matches JSON subsets inside those artifacts, so strict and workspace cases can pin mode-specific behavior without requiring exact whole-file equality.

CI path:

- `sattlint-repo-audit` forwards the default manifest directory into the analysis pipeline when `tests/fixtures/corpus/manifests/` contains manifest JSON files.

Current workspace manifest expectations:

- `workspace-common-quality-issues` asserts `semantic.read-before-write`, `semantic.unused-variable`, and the matching `summary.json` rule counts.
