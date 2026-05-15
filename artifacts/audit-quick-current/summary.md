# Repository Audit

## Summary

- Critical: 0
- High: 7
- Medium: 6
- Low: 0

## Findings

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
  Detail: Generated output drifted from its source-digest manifest (changed sources: src/sattlint/devtools/pipeline.py).
- [MEDIUM] maintenance: Generated output drifted from its source-digest manifest. (artifacts/audit-ai-gc-recheck)
  Detail: Generated output drifted from its source-digest manifest (changed sources: src/sattlint/devtools/repo_audit_entrypoints.py).
- [MEDIUM] maintenance: Generated output drifted from its source-digest manifest. (artifacts/audit-full-current)
  Detail: Generated output drifted from its source-digest manifest (changed sources: src/sattlint/devtools/pipeline.py).
