# Corpus Fixtures

This directory is reserved for corpus-backed analyzer and pipeline validation.

Suggested layout:

- `valid/` for fixtures expected to parse and analyze successfully
- `invalid/` for fixtures expected to fail strict validation
- `edge_cases/` for high-risk semantics and parser corner cases
- `semantic/workspace/` for workspace-only semantic corpus fixtures
- `semantic/analyzer/` for analyzer-only corpus fixtures
- `semantic/shared/` for corpus fixtures reused by both workspace and analyzer manifests
- `manifests/` for JSON manifests consumed by `sattlint.devtools.corpus`

Minimal manifest shape:

```json
{
  "case_id": "unused-variable",
  "target_file": "tests/fixtures/corpus/valid/UnusedVariable.s",
  "mode": "workspace",
  "analysis_config": {
    "analysis": {
      "sfc": {
        "mutually_exclusive_steps": [["Idle", "Running"]]
      }
    }
  },
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

`analysis_config` is optional and is merged into the workspace analysis config for that case. Use it when a checked-in fixture depends on analyzer settings such as `analysis.sfc.mutually_exclusive_steps` or `analysis.sfc.step_contracts`.

`load_strategy` is optional. The default is `workspace`, which loads the target through the project graph. Use `direct-parse` only when a dedicated fixture must exercise parser-AST behavior that the workspace loader rejects earlier, such as rules around invalid temporal access. Use `python-factory` sparingly for synthetic `BasePicture` fixtures that cannot be produced from valid source text, such as transform-invariant violations inside the submodule tree.

Analyzer-specific manifests use `mode: "analyzer-<kebab-case-key>"` and assert the direct analyzer issue kinds emitted by that registry-backed analyzer. They do not replace the existing `workspace` manifests, which still validate semantic-layer findings.

Example analyzer manifest:

```json
{
  "case_id": "analyzer-comment-code",
  "target_file": "../semantic/analyzer/CommentedCode.s",
  "mode": "analyzer-comment-code",
  "expectation": {
    "expected_finding_ids": ["comment_code"],
    "artifact_fragments": {
      "status.json": {
        "execution_status": "ok",
        "analyzer_key": "comment-code"
      },
      "summary.json": {
        "rule_counts": {
          "comment_code": 1
        }
      }
    },
    "forbidden_finding_ids": ["corpus.execution-error", "syntax.parse"]
  },
  "required_artifacts": ["findings.json", "status.json", "summary.json"]
}
```

Execution:

- `sattlint-corpus-runner --manifest-dir tests/fixtures/corpus/manifests --output-dir artifacts/analysis`

Included starter manifests:

- `manifests/strict-invalid.json` expects a strict parse failure from `invalid/NotSattLine.s`.
- `manifests/workspace-common-quality-issues.json` expects semantic findings from `tests/fixtures/corpus/semantic/workspace/CommonQualityIssues.s`.

Outputs:

- `artifacts/analysis/corpus_results.json` aggregates pass or fail status across all manifests.
- `artifacts/analysis/corpus_cases/<case_id>/` stores each case's `findings.json`, `status.json`, and `summary.json`.
- `expectation.artifact_fragments` matches JSON subsets inside those artifacts, so strict and workspace cases can pin mode-specific behavior without requiring exact whole-file equality.

CI path:

- `sattlint-repo-audit` forwards the default manifest directory into the analysis pipeline when `tests/fixtures/corpus/manifests/` contains manifest JSON files.

Current workspace manifest expectations:

- `workspace-common-quality-issues` asserts `semantic.read-before-write`, `semantic.unused-variable`, and the matching `summary.json` rule counts.

Current analyzer manifest expectations:

- `analyzer-*` manifests assert direct analyzer issue kinds such as `comment_code`, `module.cyclomatic_complexity`, or `picture_display_paths.unresolved`.
- Analyzer manifests may point at `semantic/analyzer/` for analyzer-only fixtures, `semantic/shared/` when the same file also supports workspace coverage, or specialized non-corpus fixture trees such as `tests/fixtures/analyzer_guardrails/` when an existing guardrail fixture already owns that behavior.
