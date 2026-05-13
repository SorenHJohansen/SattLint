# Ratchet Rebaseline Approval 2026-05-13

Approved-by: Repository owner via chat request
Reason: Authorize the same-change protected-path updates needed to satisfy current ratchet policy evidence without loosening any baseline. This approval covers adding `src/sattline_parser/models/_ast_model_support.py` and `src/sattlint/_app_analysis_variable_analyses.py` to `pyproject.toml` `tool.pyright.strict` after same-change proof that the files belong in the strict scope, and removing the stale `src/sattline_parser/models/ast_model.py` structural debt entry from `artifacts/analysis/file_debt_ratchet.json` after same-change shrink work brings the file below the structural target. This approval does not waive monotonic structural, typing, or coverage ratchet rules.
