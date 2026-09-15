from __future__ import annotations

from dataclasses import replace
from enum import Enum

from ._sattline_semantic_models import SemanticRule
from ._sattline_semantic_rules import FRAMEWORK_RULES_BY_KIND
from .framework import Issue, register_issue_metadata_materializer

_EXTRA_RULES_BY_KIND: dict[str, SemanticRule] = {
    "comment_code": SemanticRule(
        id="semantic.commented-code",
        source="comment-code",
        description="Commented-out code fragments make active logic harder to review and can drift away from real behavior.",
        name="Commented-out code",
        example="(* RunCommand = 1;   <- old logic kept as a comment, no longer active *)\nOutput = RawInput;",
        explanation="Commented-out code obscures intent and often preserves stale logic that no longer matches the compiled path.",
        suggestion="Delete dead commented code, or replace it with a short comment that explains the active design choice.",
    ),
    "mms.duplicate_tag": SemanticRule(
        id="semantic.mms-duplicate-tag",
        source="mms-interface",
        description="Multiple MMS mappings reuse the same external tag.",
        name="Duplicate MMS tag",
        example='SUBMODULES\n   MmsA Invocation\n      ( 0.0, 0.0, 0.0, 0.4, 0.4 ) : MmsMapper (MmsTag => "CONTROL.ACTIVE");\n   MmsB Invocation\n      ( 0.5, 0.0, 0.0, 0.4, 0.4 ) : MmsMapper (MmsTag => "CONTROL.ACTIVE");',
        explanation="Duplicate external MMS tags make ownership ambiguous and can route updates to the wrong consumer.",
        suggestion="Give each MMS signal a unique external tag, or consolidate the mappings behind one canonical owner.",
    ),
    "mms.datatype_mismatch": SemanticRule(
        id="semantic.mms-datatype-mismatch",
        source="mms-interface",
        description="The two ends of one MMS connection use different datatypes.",
        name="MMS datatype mismatch",
        example="SUBMODULES\n   MmsA Invocation\n      ( 0.0, 0.0, 0.0, 0.4, 0.4 ) : MmsMapper (MmsData => RawCounter);\n   (* RawCounter is integer but the MMS tag expects real *)",
        explanation="Datatype mismatches at the MMS boundary can truncate values or break external contracts.",
        suggestion="Align the connected datatypes, or add an explicit compatible conversion before the MMS boundary.",
    ),
    "mms.dead_tag": SemanticRule(
        id="semantic.mms-dead-tag",
        source="mms-interface",
        description="Configured MMS tags are not used by the analyzed code path.",
        name="Dead MMS tag",
        example='SUBMODULES\n   MmsA Invocation\n      ( 0.0, 0.0, 0.0, 0.4, 0.4 ) : MmsMapper (MmsTag => "LEVEL.SENSOR");\n   (* LEVEL.SENSOR is configured but never referenced by the code path *)',
        explanation="Dead MMS tags increase interface noise and can hide stale integrations.",
        suggestion="Remove the unused tag, or reconnect the code path that is expected to publish or consume it.",
    ),
    "module.cyclomatic_complexity": SemanticRule(
        id="semantic.cyclomatic-complexity.module",
        source="cyclomatic-complexity",
        description="Program or module control flow exceeds the configured cyclomatic complexity threshold.",
        name="High module complexity",
        example="ModuleCode\n   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :\n      IF A AND B OR C THEN\n         IF D THEN ... ENDIF;\n      ENDIF;   (* many nested branches push complexity past the limit *)",
        explanation="High block-level complexity makes scan behavior harder to review and increases the chance of hidden edge cases.",
        suggestion="Split the logic into smaller equation blocks or helper modules so each unit has one clear control purpose.",
    ),
    "equation.cyclomatic_complexity": SemanticRule(
        id="semantic.cyclomatic-complexity.equation-block",
        source="cyclomatic-complexity",
        description="Equation block control flow exceeds the configured cyclomatic complexity threshold.",
        name="High equation block complexity",
        example="ModuleCode\n   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :\n      IF A THEN\n         IF B THEN\n            IF C THEN ... ENDIF;\n         ENDIF;\n      ENDIF;   (* too many nested branches for one equation block *)",
        explanation="Complex equation blocks are harder to review than smaller, single-purpose blocks.",
        suggestion="Split the equation block into smaller blocks or helper modules so each unit has one clear control purpose.",
    ),
    "step.cyclomatic_complexity": SemanticRule(
        id="semantic.cyclomatic-complexity.step",
        source="cyclomatic-complexity",
        description="SFC step logic exceeds the configured cyclomatic complexity threshold.",
        name="High step complexity",
        example="SEQSTEP Run\n   ACTIVECODE\n      IF A THEN\n         IF B THEN\n            Cmd = 1;\n         ENDIF;\n      ENDIF;   (* too many nested branches for one step *)",
        explanation="Complex active step logic is harder to reason about than explicit step decomposition.",
        suggestion="Split the step into smaller states or move side conditions into clearer transitions.",
    ),
    "module.version_drift": SemanticRule(
        id="semantic.module-version-drift",
        source="version-drift",
        description="Repeated module types with the same name have drifted structurally beyond expected date-code differences.",
        name="Version drift",
        example="(* two 'Mixer' module types, one dated 2026-01-01 and one dated 2026-06-01 *)\n(* in the same project with the same ModuleTypeDef name *)",
        explanation="Version drift across repeated module types makes rollout and troubleshooting harder because the same named unit no longer behaves consistently.",
        suggestion="Realign the variants, or rename the intentionally different module so the divergence is explicit.",
    ),
    "icf.program_mismatch": SemanticRule(
        id="semantic.icf-program-mismatch",
        source="icf",
        description="An .icf entry references a different program than the .icf file it belongs to.",
        name="ICF program mismatch",
        example="(* in UnitA.icf *)\nOPR_ID=F::Program:UnitB.Clean.T.OPR_ID   (* should reference Program:UnitA *)",
        explanation="An .icf file is validated against the program named by the file stem; an entry pointing at another program will be resolved against the wrong target.",
        suggestion="Correct the Program:Path value so it matches the program the .icf file is for.",
    ),
    "icf.unresolved_path": SemanticRule(
        id="semantic.icf-unresolved-path",
        source="icf",
        description="An .icf entry points at a path that cannot be resolved in the target program.",
        name="ICF unresolved path",
        example="STATE_NO=F::Program:UnitA.OpStart.MissingSignal.STATE_NO   (* path does not exist *)",
        explanation="A reference that cannot be resolved will never bind the configured external value, so the mapping is silently inactive.",
        suggestion="Point the entry at a module/variable path that exists in the referenced program.",
    ),
    "icf.invalid_field_path": SemanticRule(
        id="semantic.icf-invalid-field-path",
        source="icf",
        description="An .icf entry targets a field path or datatype that does not match the resolved variable.",
        name="ICF invalid field path",
        example="VALUE=F::Program:UnitA.Record.Nested.Nope.VALUE   (* Nope is not a field of Record *)",
        explanation="A field or datatype mismatch means the configured value cannot be applied to the declared variable.",
        suggestion="Fix the field path or align the mapped datatype with the variable declaration.",
    ),
    "icf.reference_case_mismatch": SemanticRule(
        id="semantic.icf-reference-case-mismatch",
        source="icf",
        description="An .icf reference uses a different letter case than the resolved target name.",
        name="ICF reference case mismatch",
        example="VALUE=F::Program:UnitA.logValue.VALUE   (* declared name is LogValue *)",
        explanation="Case drift makes the mapping fragile and harder to audit against the declared name.",
        suggestion="Match the reference case to the declared module/variable name.",
    ),
    "icf.unit_tag_mismatch": SemanticRule(
        id="semantic.icf-unit-tag-mismatch",
        source="icf",
        description="An .icf unit tag does not match the resolved unit structure.",
        name="ICF unit tag mismatch",
        example="(* in [Unit UnitB] *)\nVALUE=F::Program:UnitA.Clean.T.VALUE   (* tag points at UnitA instead of UnitB *)",
        explanation="A unit tag that disagrees with the target unit can route the value to the wrong place.",
        suggestion="Align the unit tag with the unit declared in the referenced program.",
    ),
    "icf.group_tag_mismatch": SemanticRule(
        id="semantic.icf-group-tag-mismatch",
        source="icf",
        description="An .icf group tag suffix does not match the expected group-key rule.",
        name="ICF group tag mismatch",
        example="(* configured group suffix is JournalData_DCStoMES *)\nTAG=F::Program:UnitA.JournalA.Group.JournalData_Wrong  (* wrong suffix *)",
        explanation="Group tag suffixes carry semantic meaning; a wrong suffix breaks grouping.",
        suggestion="Correct the group tag suffix to match the configured group-key rule.",
    ),
    "icf.missing_journal_field": SemanticRule(
        id="semantic.icf-missing-journal-field",
        source="icf",
        description="An .icf journal entry is missing required parameter fields.",
        name="ICF missing journal field",
        example="(* [Journal Clean] requires CR_ID and OPR_ID *)\nCR_ID=F::Program:UnitA.Clean.T.CR_ID   (* OPR_ID entry is missing *)",
        explanation="Journal entries without the required fields will not record complete audit information.",
        suggestion="Add the missing journal parameter fields to the entry.",
    ),
    "icf.unit_structure_drift": SemanticRule(
        id="semantic.icf-unit-structure-drift",
        source="icf",
        description="An .icf unit structure has drifted from the expected layout.",
        name="ICF unit structure drift",
        example="(* the UnitA section changed from SingleUnit to MultiUnit layout *)\n(* existing .icf entries no longer match the new structure *)",
        explanation="Structural drift makes the configuration inconsistent with the engineering layout.",
        suggestion="Realign the unit structure with the expected layout.",
    ),
    "icf.value_prefix_inconsistency": SemanticRule(
        id="semantic.icf-value-prefix-inconsistency",
        source="icf",
        description="An .icf value mixes letters from different prefix groups.",
        name="ICF value prefix inconsistency",
        example="VALUE=AB::Program:UnitA.Value.VALUE   (* mixes group A and B prefixes in one value *)",
        explanation="Mixed value-prefix letters can cause the value to be misclassified or routed incorrectly.",
        suggestion="Use a single consistent value-prefix letter for the value.",
    ),
    "icf.program_load_failed": SemanticRule(
        id="semantic.icf-program-load-failed",
        source="icf",
        description="The program referenced by an .icf file could not be loaded for validation.",
        name="ICF program load failed",
        example="(* UnitB.icf references Program:UnitB which failed to load *)\n(* its entries cannot be validated at all *)",
        explanation="Without the referenced program the .icf entries cannot be validated, so the check is incomplete.",
        suggestion="Make the referenced program loadable, or remove the .icf file that points at it.",
    ),
    "icf.issue": SemanticRule(
        id="semantic.icf-issue",
        source="icf",
        description="An ICF configuration entry failed validation.",
        name="ICF entry invalid",
        example="VALUE=F::Program:UnitA.Clean.T.VALUE   (* entry violates a validation rule *)",
        explanation="A configuration entry does not satisfy the ICF validation rules.",
        suggestion="Review and correct the failing .icf entry.",
    ),
    "picture_display_paths.above_base": SemanticRule(
        id="semantic.picture-display-above-base",
        source="picture-display-paths",
        description="A PictureDisplay path ascends above the base picture of the declaring module.",
        name="PictureDisplay path above base picture",
        example="(* a button path like '-------*Test' climbs past the declaring module's root *)",
        explanation="A path that escapes above the base picture cannot be resolved inside the program tree and usually means the path is wrong or the display is misplaced.",
        suggestion="Fix the path so it stays inside the declaring module tree.",
    ),
}

_ALL_ISSUE_RULES_BY_KIND: dict[str, SemanticRule] = {
    **FRAMEWORK_RULES_BY_KIND,
    **_EXTRA_RULES_BY_KIND,
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
    return all(hasattr(issue, field_name) for field_name in ("rule_id", "explanation", "suggestion"))


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
        explanation=getattr(issue, "explanation", None) or rule.explanation or rule.description,
        suggestion=getattr(issue, "suggestion", None) or rule.suggestion,
    )


register_issue_metadata_materializer(materialize_issue_metadata)


__all__ = [
    "get_issue_rules_for_source",
    "materialize_issue_metadata",
]
