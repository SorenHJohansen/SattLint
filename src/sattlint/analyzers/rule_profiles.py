from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from .issue import Issue
from .sattline_semantics import SemanticRule, get_rule_for_framework_issue_kind


@dataclass(frozen=True)
class RuleProfile:
    name: str
    description: str
    disabled_rules: tuple[str, ...] = ()
    severity_overrides: dict[str, str] | None = None
    confidence_overrides: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "disabled_rules": list(self.disabled_rules),
            "severity_overrides": dict(self.severity_overrides or {}),
            "confidence_overrides": dict(self.confidence_overrides or {}),
        }


_EXTRA_RULES_BY_KIND: dict[str, SemanticRule] = {
    "comment_code": SemanticRule(
        id="semantic.commented-code",
        source="comment-code",
        category="module-structure",
        severity="warning",
        applies_to="source-file",
        description="Commented-out code fragments make active logic harder to review and can drift away from real behavior.",
        confidence="style",
        explanation="Commented-out code obscures intent and often preserves stale logic that no longer matches the compiled path.",
        suggestion="Delete dead commented code, or replace it with a short comment that explains the active design choice.",
    ),
    "comment_code_read_error": SemanticRule(
        id="semantic.comment-code-read-error",
        source="comment-code",
        category="module-structure",
        severity="error",
        applies_to="source-file",
        description="Comment-code analysis could not read a requested source file.",
        confidence="definite",
        explanation="If the source cannot be read reliably, comment-code findings for that file are incomplete.",
        suggestion="Fix the file path or encoding issue and rerun the analysis.",
    ),
    "mms.duplicate_tag": SemanticRule(
        id="semantic.mms-duplicate-tag",
        source="mms-interface",
        category="interface-contracts",
        severity="error",
        applies_to="mms-tag",
        description="Multiple MMS mappings reuse the same external tag.",
        confidence="definite",
        explanation="Duplicate external MMS tags make ownership ambiguous and can route updates to the wrong consumer.",
        suggestion="Give each MMS signal a unique external tag, or consolidate the mappings behind one canonical owner.",
    ),
    "mms.datatype_mismatch": SemanticRule(
        id="semantic.mms-datatype-mismatch",
        source="mms-interface",
        category="interface-contracts",
        severity="error",
        applies_to="mms-mapping",
        description="Connected MMS signals use incompatible datatypes.",
        confidence="definite",
        explanation="Datatype mismatches at the MMS boundary can truncate values or break external contracts.",
        suggestion="Align the connected datatypes, or add an explicit compatible conversion before the MMS boundary.",
    ),
    "mms.naming_drift": SemanticRule(
        id="semantic.mms-naming-drift",
        source="mms-interface",
        category="engineering-spec",
        severity="warning",
        applies_to="mms-mapping",
        description="MMS-facing names drift from the external tag or interface naming contract.",
        confidence="style",
        explanation="Naming drift at the MMS boundary makes cross-system traceability harder for operators and reviewers.",
        suggestion="Rename the signal or external tag so the MMS interface stays traceable end to end.",
    ),
    "mms.dead_tag": SemanticRule(
        id="semantic.mms-dead-tag",
        source="mms-interface",
        category="interface-contracts",
        severity="warning",
        applies_to="mms-tag",
        description="Configured MMS tags are not used by the analyzed code path.",
        confidence="likely",
        explanation="Dead MMS tags increase interface noise and can hide stale integrations.",
        suggestion="Remove the unused tag, or reconnect the code path that is expected to publish or consume it.",
    ),
    "naming.inconsistent_style": SemanticRule(
        id="semantic.naming-inconsistent-style",
        source="naming-consistency",
        category="engineering-spec",
        severity="warning",
        applies_to="symbol",
        description="Variables, modules, or instances drift away from the configured naming style.",
        confidence="style",
        explanation="Inconsistent naming style makes the codebase slower to scan and weakens shared engineering conventions.",
        suggestion="Rename the symbol to the configured style, or update the naming allowlist if the exception is intentional.",
    ),
    "module.cyclomatic_complexity": SemanticRule(
        id="semantic.cyclomatic-complexity.module",
        source="cyclomatic-complexity",
        category="module-structure",
        severity="warning",
        applies_to="module",
        description="Program or module control flow exceeds the configured cyclomatic complexity threshold.",
        confidence="style",
        explanation="High block-level complexity makes scan behavior harder to review and increases the chance of hidden edge cases.",
        suggestion="Split the logic into smaller equation blocks or helper modules so each unit has one clear control purpose.",
    ),
    "step.cyclomatic_complexity": SemanticRule(
        id="semantic.cyclomatic-complexity.step",
        source="cyclomatic-complexity",
        category="control-flow",
        severity="warning",
        applies_to="step",
        description="SFC step logic exceeds the configured cyclomatic complexity threshold.",
        confidence="style",
        explanation="Complex active step logic is harder to reason about than explicit step decomposition.",
        suggestion="Split the step into smaller states or move side conditions into clearer transitions.",
    ),
    "module.parameter_drift": SemanticRule(
        id="semantic.parameter-drift",
        source="parameter-drift",
        category="interface-contracts",
        severity="warning",
        applies_to="module-instance-group",
        description="Instances of the same moduletype drift on resolved literal parameter values.",
        confidence="likely",
        explanation="Parameter drift across sibling instances makes behavior harder to compare and often hides accidental divergence.",
        suggestion="Standardize the shared parameter value, or document the deliberate exception with a clearly named variant module.",
    ),
    "scan_cycle.resource_usage": SemanticRule(
        id="semantic.scan-loop-resource-usage",
        source="scan-loop-resource-usage",
        category="control-flow",
        severity="warning",
        applies_to="scan-cycle-call",
        description="Non precision-scan-safe calls appear inside continuously executed scan-cycle logic.",
        confidence="likely",
        explanation="Expensive or non precision-scan-safe calls inside the scan loop can add jitter and hide timing-sensitive failures.",
        suggestion="Move the call to a less frequent path, cache the result, or isolate it behind a dedicated slower scan group.",
    ),
    "module.version_drift": SemanticRule(
        id="semantic.module-version-drift",
        source="version-drift",
        category="module-structure",
        severity="warning",
        applies_to="module-family",
        description="Repeated modules with the same name have drifted structurally beyond expected date-code differences.",
        confidence="likely",
        explanation="Version drift across repeated modules makes rollout and troubleshooting harder because the same named unit no longer behaves consistently.",
        suggestion="Realign the variants, or rename the intentionally different module so the divergence is explicit.",
    ),
    "sorting.loop_output_refactor": SemanticRule(
        id="semantic.loop-output-refactor",
        source="loop-output-refactor",
        category="control-flow",
        severity="warning",
        applies_to="equation-block-cycle",
        description="A dependency loop across sorted equation or active-step blocks should be refactored to make the delay point explicit.",
        confidence="likely",
        explanation="Cross-block dependency loops force at least one scan of delay and make execution order harder to reason about from the code alone.",
        suggestion="Split the participating blocks, move the feedback write to a later block, or make one chosen cycle variable STATE so the delay point is explicit.",
    ),
}


def _default_profiles() -> dict[str, RuleProfile]:
    return {
        "default": RuleProfile(
            name="default",
            description="Balanced default analyzer profile.",
        ),
        "strict-pharma": RuleProfile(
            name="strict-pharma",
            description="Promotes style and maintainability drift during regulated review.",
            severity_overrides={
                "semantic.naming-inconsistent-style": "error",
                "semantic.cyclomatic-complexity.module": "error",
                "semantic.cyclomatic-complexity.step": "error",
            },
        ),
        "legacy-plant": RuleProfile(
            name="legacy-plant",
            description="Suppresses style-heavy advisories while preserving contract and correctness findings.",
            disabled_rules=(
                "semantic.naming-role-mismatch",
                "semantic.naming-inconsistent-style",
                "semantic.cyclomatic-complexity.module",
                "semantic.cyclomatic-complexity.step",
                "semantic.loop-output-refactor",
            ),
        ),
    }


def _normalize_profile_payload(name: str, payload: object) -> RuleProfile:
    if not isinstance(payload, dict):
        return _default_profiles().get(name, RuleProfile(name=name, description=f"Custom profile {name}."))
    disabled_rules = tuple(
        sorted(str(rule_id).strip() for rule_id in payload.get("disabled_rules", []) if str(rule_id).strip())
    )
    severity_overrides = {
        str(rule_id).strip(): str(value).strip()
        for rule_id, value in dict(payload.get("severity_overrides", {})).items()
        if str(rule_id).strip() and str(value).strip()
    }
    confidence_overrides = {
        str(rule_id).strip(): str(value).strip()
        for rule_id, value in dict(payload.get("confidence_overrides", {})).items()
        if str(rule_id).strip() and str(value).strip()
    }
    return RuleProfile(
        name=name,
        description=str(payload.get("description") or f"Custom profile {name}."),
        disabled_rules=disabled_rules,
        severity_overrides=severity_overrides,
        confidence_overrides=confidence_overrides,
    )


def get_configured_rule_profiles(config: dict[str, Any] | None) -> dict[str, RuleProfile]:
    profiles = _default_profiles()
    analysis = {} if not isinstance(config, dict) else dict(config.get("analysis") or {})
    profile_config = dict(analysis.get("rule_profiles") or {})
    configured_profiles = profile_config.get("profiles")
    if isinstance(configured_profiles, dict):
        for name, payload in configured_profiles.items():
            profile_name = str(name).strip()
            if not profile_name:
                continue
            profiles[profile_name] = _normalize_profile_payload(profile_name, payload)
    return profiles


def get_active_rule_profile(config: dict[str, Any] | None) -> RuleProfile:
    profiles = get_configured_rule_profiles(config)
    analysis = {} if not isinstance(config, dict) else dict(config.get("analysis") or {})
    profile_config = dict(analysis.get("rule_profiles") or {})
    active_name = str(profile_config.get("active") or "default").strip() or "default"
    return profiles.get(active_name, profiles["default"])


def get_default_rule_profile_report() -> dict[str, Any]:
    profiles = _default_profiles()
    return {
        "active": "default",
        "profiles": [profiles[name].to_dict() for name in sorted(profiles)],
    }


def _resolve_issue_rule(issue_kind: str) -> SemanticRule | None:
    return _EXTRA_RULES_BY_KIND.get(issue_kind) or get_rule_for_framework_issue_kind(issue_kind)


def materialize_issue_metadata(issue: Issue) -> Issue:
    rule = _resolve_issue_rule(issue.kind)
    if rule is None:
        return issue
    return replace(
        issue,
        rule_id=issue.rule_id or rule.id,
        severity=issue.severity or rule.severity,
        confidence=issue.confidence or rule.confidence,
        explanation=issue.explanation or rule.explanation or rule.description,
        suggestion=issue.suggestion or rule.suggestion,
    )


def apply_rule_profile_to_issue(issue: Issue, profile: RuleProfile) -> Issue | None:
    materialized = materialize_issue_metadata(issue)
    if materialized.rule_id in set(profile.disabled_rules):
        return None
    if materialized.rule_id is None:
        return materialized
    severity = (profile.severity_overrides or {}).get(materialized.rule_id, materialized.severity)
    confidence = (profile.confidence_overrides or {}).get(materialized.rule_id, materialized.confidence)
    return replace(materialized, severity=severity, confidence=confidence)


def apply_rule_profile_to_report(analyzer_key: str, report: Any, config: dict[str, Any] | None):
    del analyzer_key
    issues = getattr(report, "issues", None)
    if not isinstance(issues, list):
        return report
    profile = get_active_rule_profile(config)
    report.issues = [
        updated for issue in issues for updated in [apply_rule_profile_to_issue(issue, profile)] if updated is not None
    ]
    return report
