from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from enum import Enum
from typing import Protocol, cast

from ._sattline_semantic_models import SemanticRule
from ._sattline_semantic_rules import FRAMEWORK_RULES_BY_KIND
from .framework import Issue, register_issue_metadata_materializer


@dataclass(frozen=True)
class RuleProfile:
    name: str
    description: str
    disabled_rules: tuple[str, ...] = ()
    severity_overrides: dict[str, str] | None = None
    confidence_overrides: dict[str, str] | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "description": self.description,
            "disabled_rules": list(self.disabled_rules),
            "severity_overrides": dict(self.severity_overrides or {}),
            "confidence_overrides": dict(self.confidence_overrides or {}),
        }


def _mapping(raw: object) -> Mapping[str, object] | None:
    if isinstance(raw, Mapping):
        return cast(Mapping[str, object], raw)
    return None


def _normalized_string_tuple(raw: object) -> tuple[str, ...]:
    values = cast(Sequence[object], raw) if isinstance(raw, list) else ()
    return tuple(sorted(value_text for value in values if (value_text := str(value).strip())))


def _normalized_string_mapping(raw: object) -> dict[str, str]:
    mapping = _mapping(raw)
    if mapping is None:
        return {}
    normalized: dict[str, str] = {}
    for rule_id, value in mapping.items():
        rule_text = str(rule_id).strip()
        value_text = str(value).strip()
        if rule_text and value_text:
            normalized[rule_text] = value_text
    return normalized


class _IssueReport(Protocol):
    issues: list[Issue]


_EXTRA_RULES_BY_KIND: dict[str, SemanticRule] = {
    "comment_code": SemanticRule(
        id="semantic.commented-code",
        source="comment-code",
        category="module-structure",
        severity="warning",
        applies_to="source-file",
        description="Commented-out code fragments make active logic harder to review and can drift away from real behavior.",
        name="Commented-out code",
        example="(* RunCommand = 1;   <- old logic kept as a comment, no longer active *)\nOutput = RawInput;",
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
        name="Comment-code read error",
        example="(* configured source path S:\\Programs\\Pump.s has an invalid encoding *)\n(* comment-code analysis cannot read the file *)",
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
        name="Duplicate MMS tag",
        example='SUBMODULES\n   MmsA Invocation\n      ( 0.0, 0.0, 0.0, 0.4, 0.4 ) : MmsMapper (MmsTag => "CONTROL.ACTIVE");\n   MmsB Invocation\n      ( 0.5, 0.0, 0.0, 0.4, 0.4 ) : MmsMapper (MmsTag => "CONTROL.ACTIVE");',
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
        name="MMS datatype mismatch",
        example="SUBMODULES\n   MmsA Invocation\n      ( 0.0, 0.0, 0.0, 0.4, 0.4 ) : MmsMapper (MmsData => RawCounter);\n   (* RawCounter is integer but the MMS tag expects real *)",
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
        name="MMS naming drift",
        example='SUBMODULES\n   MmsA Invocation\n      ( 0.0, 0.0, 0.0, 0.4, 0.4 ) : MmsMapper (MmsTag => "PUMP.SPEED");\n   (* local signal named pumpSpeed does not follow the external tag naming rule *)',
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
        name="Dead MMS tag",
        example='SUBMODULES\n   MmsA Invocation\n      ( 0.0, 0.0, 0.0, 0.4, 0.4 ) : MmsMapper (MmsTag => "LEVEL.SENSOR");\n   (* LEVEL.SENSOR is configured but never referenced by the code path *)',
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
        name="Inconsistent naming style",
        example="LOCALVARIABLES\n   PumpSpeed: integer := 0;   (* configured style is camelCase: pumpSpeed *)",
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
        name="High module complexity",
        example="ModuleCode\n   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :\n      IF A AND B OR C THEN\n         IF D THEN ... ENDIF;\n      ENDIF;   (* many nested branches push complexity past the limit *)",
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
        name="High step complexity",
        example="SEQSTEP Run\n   ACTIVECODE\n      IF A THEN\n         IF B THEN\n            Cmd = 1;\n         ENDIF;\n      ENDIF;   (* too many nested branches for one step *)",
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
        name="Parameter drift",
        example="SUBMODULES\n   PumpA Invocation\n      ( 0.0, 0.0, 0.0, 0.4, 0.4 ) : PumpType (MaxSpeed => 1500);\n   PumpB Invocation\n      ( 0.5, 0.0, 0.0, 0.4, 0.4 ) : PumpType (MaxSpeed => 3500);\n   (* sibling instances of PumpType resolve different MaxSpeed values *)",
        confidence="likely",
        explanation="Parameter drift across sibling instances makes behavior harder to compare and often hides accidental divergence.",
        suggestion="Standardize the shared parameter value, or document the deliberate exception with a clearly named variant module.",
    ),
    "data_dependency.path": SemanticRule(
        id="semantic.data-dependency-path",
        source="data-dependency",
        category="control-flow",
        severity="warning",
        applies_to="assignment-chain",
        description="A write is connected to an upstream transitive dependency chain.",
        name="Dependency path",
        example="ModuleCode\n   A = B + 1;\n   B = C + 1;   (* B depends on C, so A depends on C transitively *)",
        confidence="likely",
        explanation="Transitive assignment chains make execution order more important and can hide where a final value really comes from.",
        suggestion="Shorten the chain, or split intermediate computations so the owning write is easier to trace.",
    ),
    "data_dependency.initialization_order": SemanticRule(
        id="semantic.data-dependency-initialization-order",
        source="data-dependency",
        category="control-flow",
        severity="error",
        applies_to="assignment-order",
        description="A write depends on another local value before that value is initialized in the same scope.",
        name="Initialization order",
        example="ModuleCode\n   Result = Temp + 1;   (* Result depends on Temp ... *)\n   Temp = RawInput;     (* ... but Temp is initialized later in the scope *)",
        confidence="definite",
        explanation="Initialization-order dependencies can make the resulting value depend on scan order or undefined startup state.",
        suggestion="Initialize the upstream value earlier, or refactor the write so it does not depend on a later assignment.",
    ),
    "module.version_drift": SemanticRule(
        id="semantic.module-version-drift",
        source="version-drift",
        category="module-structure",
        severity="warning",
        applies_to="module-family",
        description="Repeated modules with the same name have drifted structurally beyond expected date-code differences.",
        name="Version drift",
        example="(* PumpModule dated 2026-01-01 defines two extra equations *)\n(* compared with PumpModule dated 2026-06-01 in the same library *)",
        confidence="likely",
        explanation="Version drift across repeated modules makes rollout and troubleshooting harder because the same named unit no longer behaves consistently.",
        suggestion="Realign the variants, or rename the intentionally different module so the divergence is explicit.",
    ),
    "icf.program_mismatch": SemanticRule(
        id="semantic.icf-program-mismatch",
        source="icf",
        category="engineering-spec",
        severity="error",
        applies_to="icf-config",
        description="An .icf entry references a different program than the .icf file it belongs to.",
        name="ICF program mismatch",
        example="(* in UnitA.icf *)\nOPR_ID=F::Program:UnitB.Clean.T.OPR_ID   (* should reference Program:UnitA *)",
        confidence="likely",
        explanation="An .icf file is validated against the program named by the file stem; an entry pointing at another program will be resolved against the wrong target.",
        suggestion="Correct the Program:Path value so it matches the program the .icf file is for.",
    ),
    "icf.unresolved_path": SemanticRule(
        id="semantic.icf-unresolved-path",
        source="icf",
        category="interface-contracts",
        severity="error",
        applies_to="icf-config",
        description="An .icf entry points at a path that cannot be resolved in the target program.",
        name="ICF unresolved path",
        example="STATE_NO=F::Program:UnitA.OpStart.MissingSignal.STATE_NO   (* path does not exist *)",
        confidence="likely",
        explanation="A reference that cannot be resolved will never bind the configured external value, so the mapping is silently inactive.",
        suggestion="Point the entry at a module/variable path that exists in the referenced program.",
    ),
    "icf.invalid_field_path": SemanticRule(
        id="semantic.icf-invalid-field-path",
        source="icf",
        category="interface-contracts",
        severity="error",
        applies_to="icf-config",
        description="An .icf entry targets a field path or datatype that does not match the resolved variable.",
        name="ICF invalid field path",
        example="VALUE=F::Program:UnitA.Record.Nested.Nope.VALUE   (* Nope is not a field of Record *)",
        confidence="likely",
        explanation="A field or datatype mismatch means the configured value cannot be applied to the declared variable.",
        suggestion="Fix the field path or align the mapped datatype with the variable declaration.",
    ),
    "icf.reference_case_mismatch": SemanticRule(
        id="semantic.icf-reference-case-mismatch",
        source="icf",
        category="engineering-spec",
        severity="warning",
        applies_to="icf-config",
        description="An .icf reference uses a different letter case than the resolved target name.",
        name="ICF reference case mismatch",
        example="VALUE=F::Program:UnitA.logValue.VALUE   (* declared name is LogValue *)",
        confidence="likely",
        explanation="Case drift makes the mapping fragile and harder to audit against the declared name.",
        suggestion="Match the reference case to the declared module/variable name.",
    ),
    "icf.unit_tag_mismatch": SemanticRule(
        id="semantic.icf-unit-tag-mismatch",
        source="icf",
        category="interface-contracts",
        severity="warning",
        applies_to="icf-config",
        description="An .icf unit tag does not match the resolved unit structure.",
        name="ICF unit tag mismatch",
        example="(* in [Unit UnitB] *)\nVALUE=F::Program:UnitA.Clean.T.VALUE   (* tag points at UnitA instead of UnitB *)",
        confidence="likely",
        explanation="A unit tag that disagrees with the target unit can route the value to the wrong place.",
        suggestion="Align the unit tag with the unit declared in the referenced program.",
    ),
    "icf.group_tag_mismatch": SemanticRule(
        id="semantic.icf-group-tag-mismatch",
        source="icf",
        category="interface-contracts",
        severity="warning",
        applies_to="icf-config",
        description="An .icf group tag suffix does not match the expected group-key rule.",
        name="ICF group tag mismatch",
        example="(* configured group suffix is JournalData_DCStoMES *)\nTAG=F::Program:UnitA.JournalA.Group.JournalData_Wrong  (* wrong suffix *)",
        confidence="likely",
        explanation="Group tag suffixes carry semantic meaning; a wrong suffix breaks grouping.",
        suggestion="Correct the group tag suffix to match the configured group-key rule.",
    ),
    "icf.missing_journal_field": SemanticRule(
        id="semantic.icf-missing-journal-field",
        source="icf",
        category="engineering-spec",
        severity="warning",
        applies_to="icf-config",
        description="An .icf journal entry is missing required parameter fields.",
        name="ICF missing journal field",
        example="(* [Journal Clean] requires CR_ID and OPR_ID *)\nCR_ID=F::Program:UnitA.Clean.T.CR_ID   (* OPR_ID entry is missing *)",
        confidence="likely",
        explanation="Journal entries without the required fields will not record complete audit information.",
        suggestion="Add the missing journal parameter fields to the entry.",
    ),
    "icf.unit_structure_drift": SemanticRule(
        id="semantic.icf-unit-structure-drift",
        source="icf",
        category="module-structure",
        severity="warning",
        applies_to="icf-config",
        description="An .icf unit structure has drifted from the expected layout.",
        name="ICF unit structure drift",
        example="(* the UnitA section changed from SingleUnit to MultiUnit layout *)\n(* existing .icf entries no longer match the new structure *)",
        confidence="likely",
        explanation="Structural drift makes the configuration inconsistent with the engineering layout.",
        suggestion="Realign the unit structure with the expected layout.",
    ),
    "icf.value_prefix_inconsistency": SemanticRule(
        id="semantic.icf-value-prefix-inconsistency",
        source="icf",
        category="engineering-spec",
        severity="warning",
        applies_to="icf-config",
        description="An .icf value mixes letters from different prefix groups.",
        name="ICF value prefix inconsistency",
        example="VALUE=AB::Program:UnitA.Value.VALUE   (* mixes group A and B prefixes in one value *)",
        confidence="likely",
        explanation="Mixed value-prefix letters can cause the value to be misclassified or routed incorrectly.",
        suggestion="Use a single consistent value-prefix letter for the value.",
    ),
    "icf.program_load_failed": SemanticRule(
        id="semantic.icf-program-load-failed",
        source="icf",
        category="engineering-spec",
        severity="warning",
        applies_to="icf-config",
        description="The program referenced by an .icf file could not be loaded for validation.",
        name="ICF program load failed",
        example="(* UnitB.icf references Program:UnitB which failed to load *)\n(* its entries cannot be validated at all *)",
        confidence="likely",
        explanation="Without the referenced program the .icf entries cannot be validated, so the check is incomplete.",
        suggestion="Make the referenced program loadable, or remove the .icf file that points at it.",
    ),
    "icf.issue": SemanticRule(
        id="semantic.icf-issue",
        source="icf",
        category="engineering-spec",
        severity="warning",
        applies_to="icf-config",
        description="An ICF configuration entry failed validation.",
        name="ICF entry invalid",
        example="VALUE=F::Program:UnitA.Clean.T.VALUE   (* entry violates a validation rule *)",
        confidence="likely",
        explanation="A configuration entry does not satisfy the ICF validation rules.",
        suggestion="Review and correct the failing .icf entry.",
    ),
}

_ALL_ISSUE_RULES_BY_KIND: dict[str, SemanticRule] = {
    **FRAMEWORK_RULES_BY_KIND,
    **_EXTRA_RULES_BY_KIND,
}


def _default_profiles() -> dict[str, RuleProfile]:
    return {
        "default": RuleProfile(
            name="default",
            description="Default profile that runs only correctness checks.",
        ),
    }


def _normalize_profile_payload(name: str, payload: object) -> RuleProfile:
    payload_map = _mapping(payload)
    if payload_map is None:
        return _default_profiles().get(name, RuleProfile(name=name, description=f"Custom profile {name}."))
    disabled_rules = _normalized_string_tuple(payload_map.get("disabled_rules", []))
    severity_overrides = _normalized_string_mapping(payload_map.get("severity_overrides", {}))
    confidence_overrides = _normalized_string_mapping(payload_map.get("confidence_overrides", {}))
    return RuleProfile(
        name=name,
        description=str(payload_map.get("description") or f"Custom profile {name}."),
        disabled_rules=disabled_rules,
        severity_overrides=severity_overrides,
        confidence_overrides=confidence_overrides,
    )


def get_configured_rule_profiles(config: Mapping[str, object] | None) -> dict[str, RuleProfile]:
    profiles = _default_profiles()
    analysis = _mapping(config.get("analysis") if config is not None else None)
    profile_config = _mapping(analysis.get("rule_profiles") if analysis is not None else None)
    configured_profiles = _mapping(profile_config.get("profiles") if profile_config is not None else None)
    if configured_profiles is not None:
        for name, payload in configured_profiles.items():
            profile_name = str(name).strip()
            if not profile_name:
                continue
            profiles[profile_name] = _normalize_profile_payload(profile_name, payload)
    return profiles


def get_active_rule_profile(config: Mapping[str, object] | None) -> RuleProfile:
    profiles = get_configured_rule_profiles(config)
    analysis = _mapping(config.get("analysis") if config is not None else None)
    profile_config = _mapping(analysis.get("rule_profiles") if analysis is not None else None)
    active_name = str(profile_config.get("active") if profile_config is not None else "default").strip() or "default"
    return profiles.get(active_name, profiles["default"])


def get_default_rule_profile_report() -> dict[str, object]:
    profiles = _default_profiles()
    return {
        "active": "default",
        "profiles": [profiles[name].to_dict() for name in sorted(profiles)],
    }


def _resolve_issue_rule(issue_kind: str) -> SemanticRule | None:
    return _ALL_ISSUE_RULES_BY_KIND.get(issue_kind)


def get_issue_rules_for_source(source: str) -> tuple[tuple[str, SemanticRule], ...]:
    return tuple((issue_kind, rule) for issue_kind, rule in _ALL_ISSUE_RULES_BY_KIND.items() if rule.source == source)


def _normalized_issue_kind(issue: Issue) -> str | None:
    raw_kind = getattr(issue, "kind", None)
    if isinstance(raw_kind, Enum):
        raw_kind = raw_kind.value
    kind_text = str(raw_kind).strip() if raw_kind is not None else ""
    return kind_text or None


def _issue_has_rule_metadata(issue: Issue) -> bool:
    return all(
        hasattr(issue, field_name) for field_name in ("rule_id", "severity", "confidence", "explanation", "suggestion")
    )


def _derived_rule_id(issue: Issue) -> str | None:
    normalized_kind = _normalized_issue_kind(issue)
    if normalized_kind is None:
        return None
    rule = _resolve_issue_rule(normalized_kind)
    return rule.id if rule is not None else None


def materialize_issue_metadata(issue: Issue) -> Issue:
    if not _issue_has_rule_metadata(issue):
        return issue
    normalized_kind = _normalized_issue_kind(issue)
    if normalized_kind is None:
        return issue
    rule = _resolve_issue_rule(normalized_kind)
    if rule is None:
        return issue
    return replace(
        issue,
        rule_id=getattr(issue, "rule_id", None) or rule.id,
        severity=getattr(issue, "severity", None) or rule.severity,
        confidence=getattr(issue, "confidence", None) or rule.confidence,
        explanation=getattr(issue, "explanation", None) or rule.explanation or rule.description,
        suggestion=getattr(issue, "suggestion", None) or rule.suggestion,
    )


def apply_rule_profile_to_issue(issue: Issue, profile: RuleProfile) -> Issue | None:
    materialized = materialize_issue_metadata(issue)
    resolved_rule_id = getattr(materialized, "rule_id", None) or _derived_rule_id(materialized)
    if resolved_rule_id in set(profile.disabled_rules):
        return None
    if resolved_rule_id is None or not _issue_has_rule_metadata(materialized):
        return materialized
    severity = (profile.severity_overrides or {}).get(resolved_rule_id, getattr(materialized, "severity", None))
    confidence = (profile.confidence_overrides or {}).get(resolved_rule_id, getattr(materialized, "confidence", None))
    return replace(materialized, severity=severity, confidence=confidence)


def apply_rule_profile_to_report(analyzer_key: str, report: object, config: Mapping[str, object] | None) -> object:
    del analyzer_key
    issues = getattr(report, "issues", None)
    if not isinstance(issues, list):
        return report
    typed_report = cast(_IssueReport, report)
    typed_issues = cast(list[Issue], issues)
    profile = get_active_rule_profile(config)
    typed_report.issues = [
        updated
        for issue in typed_issues
        for updated in [apply_rule_profile_to_issue(issue, profile)]
        if updated is not None
    ]
    return typed_report


register_issue_metadata_materializer(materialize_issue_metadata)
