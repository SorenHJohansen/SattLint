# Ratchet Rebaseline Approval 2026-05-19 Global Strict

Approved-by: Repository owner via chat request
Reason: Authorize the same-change protected-path update that collapses `pyproject.toml` from an explicit per-file `tool.pyright.strict` list to repo-wide `typeCheckingMode = "strict"` for `src` after focused proof confirmed that the full source tree is already strict-clean under the equivalent temporary global-strict configuration. This approval covers only the monotonic global strict collapse and removal of the now-obsolete `tool.sattlint.typing_ratchet.strict_roots` entry; it does not waive any ratchet, coverage, structural, or follow-up validation requirements.
