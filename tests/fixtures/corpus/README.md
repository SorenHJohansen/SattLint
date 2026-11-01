# Corpus Fixtures

This directory holds the analyzer corpus. Language-validation fixtures live in
the `sattline-parser` repository, whose validation manifest is the rule oracle;
this corpus never duplicates them.

Layout:

- `valid/` for fixtures expected to parse and analyze successfully
- `edge_cases/` for high-risk semantics and parser corner cases
- `semantic/workspace/` for workspace-only semantic corpus fixtures
- `semantic/analyzer/` for analyzer-only corpus fixtures
- `semantic/shared/` for corpus fixtures reused by both workspace and analyzer manifests
- `manifests/` for the analyzer manifests read by the corpus tests

Manifest shape:

```json
{
  "case_id": "analyzer-comment-code",
  "target_file": "../semantic/analyzer/CommentedCode.s",
  "mode": "analyzer-comment-code",
  "expectation": {
    "expected_finding_ids": ["comment_code"],
    "artifact_fragments": {
      "status.json": {
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

`expected_finding_ids` lists the finding ids the analyzer must emit, and
`forbidden_finding_ids` lists ids it must never emit for that target.

Execution:

- `tests/test_corpus_analyzers.py` and `tests/corpus/test_corpus_regression_exactness.py`
  load every `manifests/analyzer-*.json` file, run the named analyzer over the
  target, and assert the findings against the expectation.
- Analyzer manifests may point at `semantic/analyzer/`, `semantic/shared/`,
  `valid/`, or a specialized fixture tree such as
  `tests/fixtures/analyzer_guardrails/`.
