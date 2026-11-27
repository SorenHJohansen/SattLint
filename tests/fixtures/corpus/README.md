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
- `manifests/` for the corpus manifests; only the analyzer family has an executing harness

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

- `tests/test_corpus_analyzers.py` loads every manifest whose `mode` starts
  with `analyzer-`, runs the named analyzer over the target, and asserts the
  finding ids and summary counts against the expectation.
- `tests/corpus/test_manifest_schema.py` validates every manifest under
  `manifests/`: it parses (rejecting duplicate JSON keys), declares the
  required fields, names an existing target, resolves every analyzer key it
  declares, rejects duplicate expected/forbidden ids, and requires
  `finding_count == sum(rule_counts)` when both are present. It does not run
  analyzers.
- Analyzer manifests may point at `semantic/analyzer/`, `semantic/shared/`,
  `valid/`, or a specialized fixture tree such as
  `tests/fixtures/analyzer_guardrails/`.
