# Repository Audit

## Summary

- Critical: 0
- High: 12
- Medium: 6
- Low: 0

## Findings

- [HIGH] harness-freshness: ExecPlan Progress is fully complete but the file still lives under docs/exec-plans/active/. Move it to docs/exec-plans/completed/. (docs/exec-plans/active/41-t-wave-6-app-config-and-doc-gardener-surface-split.md:1)
- [HIGH] harness-freshness: ExecPlan Progress is fully complete but the file still lives under docs/exec-plans/active/. Move it to docs/exec-plans/completed/. (docs/exec-plans/active/46-t-wave-7-ai-chat-observability-and-feedback-loop.md:1)
- [HIGH] harness-freshness: ExecPlan Progress is fully complete but the file still lives under docs/exec-plans/active/. Move it to docs/exec-plans/completed/. (docs/exec-plans/active/47-t-wave-7-audit-runner-and-artifact-freshness.md:1)
- [HIGH] harness-freshness: ExecPlan Progress is fully complete but the file still lives under docs/exec-plans/active/. Move it to docs/exec-plans/completed/. (docs/exec-plans/active/48-t-wave-7-codegraph-health-and-fallback-guards.md:1)
- [HIGH] harness-freshness: ExecPlan Progress is fully complete but the file still lives under docs/exec-plans/active/. Move it to docs/exec-plans/completed/. (docs/exec-plans/active/49-t-wave-7-ai-request-contracts-and-guidance-hardening.md:1)
- [HIGH] typing: No parameter named "dirty" (src/sattlint/_app_graphics_menus.py:492)
- [HIGH] typing: Argument of type "(path: Path, rules: dict[str, Any], *, dirty: bool) -> None" cannot be assigned to parameter "print_graphics_rules_summary_fn" of type "(Path, dict[str, Any]) -> None" in function "graphics_rules_menu"
  Type "(path: Path, rules: dict[str, Any], *, dirty: bool) -> None" is not assignable to type "(Path, dict[str, Any]) -> None"
    Extra parameter "dirty" (src/sattlint/app_graphics.py:377)
- [HIGH] typing: "AstDiffDetail" is unknown import symbol (tests/_analyzers_suites_test_support.py:48)
- [HIGH] typing: "_build_upgrade_notes" is unknown import symbol (tests/_analyzers_suites_test_support.py:53)
- [HIGH] typing: "_collect_named_item_diffs" is unknown import symbol (tests/_analyzers_suites_test_support.py:54)
- [HIGH] typing: "_diff_normalized_variants" is unknown import symbol (tests/_analyzers_suites_test_support.py:57)
- [HIGH] typing: "_normalize_ast_value" is unknown import symbol (tests/_analyzers_suites_test_support.py:59)
- [MEDIUM] architecture: Structural debt regressed beyond the checked-in ratchet baseline. (<repo>)
  Detail: source_file_over_budget_count: 3 > 0
- [MEDIUM] logging-observability: Library module uses print() instead of structured logging or return values. (src/sattlint/_config_self_check.py)
- [MEDIUM] maintenance: Generated output drifted from its source-digest manifest. (artifacts/ai-chat-fixture)
  Detail: Generated output drifted from its source-digest manifest (changed sources: src/sattlint/devtools/ai_chat_observability.py).
- [MEDIUM] maintenance: Generated output drifted from its source-digest manifest. (artifacts/audit)
  Detail: Generated output drifted from its source-digest manifest (changed sources: src/sattlint/devtools/pipeline.py, src/sattlint/devtools/repo_audit_entrypoints.py).
- [MEDIUM] maintenance: Generated output drifted from its source-digest manifest. (artifacts/audit-ai-gc-recheck)
  Detail: Generated output drifted from its source-digest manifest (changed sources: src/sattlint/devtools/repo_audit_entrypoints.py).
- [MEDIUM] maintenance: Generated output drifted from its source-digest manifest. (artifacts/audit-full-current)
  Detail: Generated output drifted from its source-digest manifest (changed sources: src/sattlint/devtools/pipeline.py).
