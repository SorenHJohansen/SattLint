from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

from . import analysis_catalog as analysis_catalog_module
from ._app_analysis_catalog_shared import (
    ENTRY_COMMENTED_OUT_CODE,
    ENTRY_DATATYPE_USAGE,
    ENTRY_MODULE_LOCAL_VARIABLES,
    ENTRY_VARIABLE_USAGE_TRACE,
)
from .analyzers.rule_profiles import get_issue_rules_for_source

if TYPE_CHECKING:
    from .analyzers.framework import AnalyzerSpec


@dataclass(frozen=True)
class AnalyzerIssueLeafSpec:
    issue_kind: str
    label: str
    detection: str
    how: str


_VARIABLE_DETAILS: dict[str, tuple[str, str]] = {
    "1": (
        "Runs the maintained high-confidence variable checks in one selection.",
        "Queues the maintained high-confidence variable suite and runs the variables analyzer once.",
    ),
    "2": (
        "Variables declared but never read or written anywhere in the analyzed target.",
        "Tracks per-variable read and write flags and reports declarations with neither flag set.",
    ),
    "3": (
        "Datatype fields that are never accessed across any module instance.",
        "Aggregates field-level reads and writes by datatype and reports fields with no recorded access.",
    ),
    "4": (
        "Variables that are only read, never written, and are not declared CONST.",
        "Compares the usage tracker state against declaration qualifiers and flags non-CONST read-only values.",
    ),
    "5": (
        "Variables that receive writes but never contribute to later reads.",
        "Reports variables whose usage tracker shows writes but no reads after traversal completes.",
    ),
    "6": (
        "Parameter mappings whose target name does not exist on the resolved moduletype.",
        "Resolves the target moduletype interface and checks each mapping target name against the declared parameters.",
    ),
    "7": (
        "String-like mappings whose source and destination datatypes are incompatible.",
        "Applies the mapping compatibility checks with string-specific datatype handling.",
    ),
    "8": (
        "Complex datatypes that normalize to the same structure.",
        "Normalizes complex datatype layouts and groups identical signatures together.",
    ),
    "9": (
        "Min_/Max_ parameter mappings whose paired base names do not line up.",
        "Pairs Min_/Max_ mapping names by base signal name and reports missing or mismatched partners.",
    ),
    "10": (
        "Numeric literals in non-trivial logic that should likely be named constants.",
        "Scans expressions for numeric literals and filters out trivial constant cases before reporting.",
    ),
    "11": (
        "Instances that leave internally-read moduletype parameters unmapped.",
        "Finds parameters that are read inside the moduletype and reports instances with no mapping for them.",
    ),
    "12": (
        "Record layouts whose meaning depends on field order instead of field names.",
        "Normalizes record component order and reports layouts whose semantics depend on declaration order.",
    ),
    "13": (
        "Reset paths that let stale state leak because required reset writes are missing.",
        "Walks sequence flow and reset handling to find variables that keep stale values across resets.",
    ),
    "14": (
        "Local declarations that hide an outer or global declaration of the same name.",
        "Maintains a scope stack during traversal and checks each new declaration against ancestor scopes.",
    ),
    "15": (
        "Variables only consumed by UI or display wiring, not by control logic.",
        "Separates UI reads from non-UI reads and flags variables that only feed display surfaces.",
    ),
    "16": (
        "Procedure status outputs that are written but never checked in logic.",
        "Recognizes procedure status bindings and checks whether the status value is consumed outside UI-only paths.",
    ),
    "17": (
        "Writes that do not reach any visible output, parameter, or downstream effect.",
        "Builds an effect-flow graph from writes to sinks and reports writes that never reach a reachable sink.",
    ),
    "18": (
        "Mappings whose connected datatypes do not satisfy the cross-module contract.",
        "Compares source and target datatype information at the parameter mapping boundary.",
    ),
    "19": (
        "Boolean values set on one path without a matching clear on the complementary path.",
        "Examines branch and step writes to boolean values and reports paths that can leave a latched value behind.",
    ),
    "20": (
        "Globals whose access never escapes one module subtree and could be localized.",
        "Maps each global variable to the module subtrees that access it and reports single-subtree globals.",
    ),
    "21": (
        "Globals touched by multiple unrelated subtrees, creating hidden coupling.",
        "Counts distinct accessing subtrees per global and reports cross-subtree shared-state hotspots.",
    ),
    "22": (
        "Globals read or written by many distinct module paths.",
        "Counts distinct readers and writers per global and compares them to the configured fan-in or fan-out threshold.",
    ),
    "23": (
        "Sibling layout or graphics elements whose rectangles overlap.",
        "Compares sibling layout bounds and reports intersections in the same layout scope.",
    ),
    "24": (
        "Variable names whose implied role conflicts with their observed read or write behavior.",
        "Matches naming-role patterns against the observed usage profile collected during traversal.",
    ),
}

_STATIC_ENTRY_DETAILS: dict[str, tuple[str, str]] = {
    ENTRY_DATATYPE_USAGE: (
        "Reads, writes, and mappings touching one selected datatype or field path.",
        "Reuses the datatype usage reporter to aggregate field-level reads, writes, and parameter-mapping references for the chosen symbol.",
    ),
    ENTRY_VARIABLE_USAGE_TRACE: (
        "Every resolved read, write, and reference for one selected variable or field.",
        "Runs the variable usage tracer for the selected name and prints the resolved reference sites across the target.",
    ),
    ENTRY_MODULE_LOCAL_VARIABLES: (
        "Local-variable and field usage inside one resolved module path.",
        "Resolves one module path and reports the collected local-variable and field usage for that scope.",
    ),
    "structure.compare-module-variants": (
        "Module families that share a name but differ structurally.",
        "Groups matching module names and compares their structure, parameters, and child layout.",
    ),
    "structure.find-module-instances": (
        "Every instance path matching the requested module name.",
        "Traverses the resolved module tree and lists the instance paths matching the requested module name.",
    ),
    "structure.inspect-module-tree": (
        "The resolved module hierarchy for the current target.",
        "Walks the loaded target structure and renders the module hierarchy for inspection.",
    ),
    "structure.validate-graphics-rules": (
        "Configured graphics-rule violations across the loaded modules.",
        "Runs the configured graphics rule checks against the loaded module tree and graphics metadata.",
    ),
    "interfaces.mms-interface-variables": (
        "MMS mappings plus any related interface findings on the loaded target.",
        "Builds the MMS and ICF inventory, then reports interface hits and MMS-specific findings.",
    ),
    "interfaces.validate-icf-paths": (
        "ICF entries that do not resolve against the selected program AST.",
        "Loads each configured ICF file, resolves the target program AST, and validates every entry against it.",
    ),
    "interfaces.format-icf-files": (
        "Configured ICF files that need canonical spacing and grouping normalization.",
        "Parses the configured ICF files and rewrites their Unit, Journal, Operation, and Group spacing to the formatter standard.",
    ),
    ENTRY_COMMENTED_OUT_CODE: (
        "Comment blocks that look like inactive code or file-read failures during scanning.",
        "Reads source files from the current target, finds code-like comment blocks, and reports any scan read errors.",
    ),
}

# Manual leaf-spec presentation overrides. Supported issue kinds are derived from
# central rule metadata so analyzer catalog ownership stays aligned with analyzer rules.
_ANALYZER_ISSUE_SPECS: dict[str, tuple[AnalyzerIssueLeafSpec, ...]] = {
    "dataflow": (
        AnalyzerIssueLeafSpec(
            "dataflow.read_before_write",
            "Read before write",
            "Reads that can occur before any definite assignment on the current execution path.",
            "Tracks per-variable initialization state through control flow and reports reads seen while the state is still unknown.",
        ),
        AnalyzerIssueLeafSpec(
            "dataflow.dead_overwrite",
            "Dead overwrite",
            "Writes whose value is overwritten before any read can observe the first write.",
            "Tracks pending writes per symbol and reports the earlier write when a second write arrives before any read consumes it.",
        ),
        AnalyzerIssueLeafSpec(
            "dataflow.condition_always_true",
            "Condition always true",
            "Conditions that simplify to TRUE at a specific program point.",
            "Simplifies boolean expressions against the current dataflow state and reports guards that collapse to TRUE.",
        ),
        AnalyzerIssueLeafSpec(
            "dataflow.condition_always_false",
            "Condition always false",
            "Conditions that simplify to FALSE at a specific program point.",
            "Simplifies boolean expressions against the current dataflow state and reports guards that collapse to FALSE.",
        ),
        AnalyzerIssueLeafSpec(
            "dataflow.unreachable_branch",
            "Unreachable branch",
            "Branches that cannot execute because the known control-flow facts make the guard impossible.",
            "Checks branch guards against the current dataflow state and reports guards that are provably false.",
        ),
        AnalyzerIssueLeafSpec(
            "dataflow.unreachable_sequence_node",
            "Unreachable sequence node (dataflow)",
            "Sequence nodes that cannot execute after an earlier node always terminates the path.",
            "Tracks dataflow reachability through sequence nodes and reports nodes that follow an unconditional terminator.",
        ),
        AnalyzerIssueLeafSpec(
            "dataflow.self_compare_condition",
            "Self-compare condition",
            "Conditions that compare a symbol to itself and therefore collapse to a constant result.",
            "Normalizes both sides of a comparison and reports comparisons that resolve to the same symbol with no intervening write.",
        ),
        AnalyzerIssueLeafSpec(
            "dataflow.scan_cycle_stale_read",
            "Scan-cycle stale read",
            "State :OLD reads that still rely on the previous-scan snapshot after a same-scan write.",
            "Tracks same-scan writes to state variables and reports :OLD reads that now refer to stale state.",
        ),
        AnalyzerIssueLeafSpec(
            "dataflow.scan_cycle_implicit_new",
            "Implicit same-scan dependency",
            "Implicit same-scan reads that likely meant to use :NEW after a prior write.",
            "Tracks state writes within the current scan and reports later implicit reads with ambiguous temporal intent.",
        ),
        AnalyzerIssueLeafSpec(
            "dataflow.scan_cycle_temporal_misuse",
            "Temporal state misuse",
            ":OLD references used in invalid write-target or out-parameter positions.",
            "Checks temporal suffix usage sites and reports :OLD occurrences in write or REF-like positions.",
        ),
        AnalyzerIssueLeafSpec(
            "dataflow.invalid_state_access",
            "Invalid state access",
            ":OLD or :NEW access on variables that are not declared STATE.",
            "Validates temporal suffix access against declaration qualifiers and reports non-STATE uses.",
        ),
    ),
    "sfc": (
        AnalyzerIssueLeafSpec(
            "sfc_parallel_write_race",
            "Parallel branch write race",
            "Parallel SFC branches that write the same variable or field.",
            "Collects branch-local write targets inside each SFCParallel and reports variables written in more than one branch.",
        ),
        AnalyzerIssueLeafSpec(
            "sfc_unreachable_sequence_node",
            "Unreachable sequence node (SFC)",
            "Sequence nodes that cannot execute because an earlier SFC node always terminates the branch.",
            "Walks SFC sequences structurally and reports nodes that follow an unconditional terminator.",
        ),
        AnalyzerIssueLeafSpec(
            "sfc_unreachable_transition",
            "Unreachable transition",
            "Transitions that can never fire because the branch is already structurally terminated.",
            "Uses the same structural walk as unreachable sequence nodes and applies it to transition positions.",
        ),
        AnalyzerIssueLeafSpec(
            "sfc_transition_always_true",
            "Transition always true",
            "Transitions whose guard simplifies to TRUE and always fire when reached.",
            "Simplifies each transition guard and reports guards that collapse to TRUE.",
        ),
        AnalyzerIssueLeafSpec(
            "sfc_transition_always_false",
            "Transition always false",
            "Transitions whose guard simplifies to FALSE and can never fire.",
            "Simplifies each transition guard and reports guards that collapse to FALSE.",
        ),
        AnalyzerIssueLeafSpec(
            "sfc_duplicate_transition_guard",
            "Duplicate transition guard",
            "Sibling transitions in the same branch that normalize to the same guard logic.",
            "Normalizes sibling transition guards and reports duplicate expressions.",
        ),
        AnalyzerIssueLeafSpec(
            "sfc_illegal_state_combination",
            "Illegal state combination",
            "Configured mutually-exclusive SFC steps that can still become active together.",
            "Checks the SFC structure against the configured mutually-exclusive step sets and reports reachable conflicts.",
        ),
        AnalyzerIssueLeafSpec(
            "sfc_missing_step_enter_contract",
            "Missing step enter contract",
            "Configured steps that do not initialize required state in their enter block.",
            "Loads configured step-enter contracts and reports required writes missing from the enter block.",
        ),
        AnalyzerIssueLeafSpec(
            "sfc_missing_step_exit_contract",
            "Missing step exit contract",
            "Configured steps that do not clean up required state in their exit block.",
            "Loads configured step-exit contracts and reports required writes missing from the exit block.",
        ),
        AnalyzerIssueLeafSpec(
            "sfc_step_state_leakage",
            "Step state leakage",
            "Step transitions that can inherit stale state because required enter writes are missing.",
            "Tracks prior-step writes and reports variables that remain live when a later step does not initialize them.",
        ),
    ),
    "same-cycle": (
        AnalyzerIssueLeafSpec(
            "same_cycle_parallel_read_write_hazard",
            "Parallel read/write hazard",
            "Parallel SFC branches that both read and write the same variable within one scan.",
            "Collects branch-local read and write targets inside each SFCParallel and reports variables read in one branch while another branch writes them in the same scan.",
        ),
        AnalyzerIssueLeafSpec(
            "same_cycle_non_state_multi_site_hazard",
            "Non-state multi-site hazard",
            "Non-STATE variables that are read and written across multiple continuous scan sites within the same scan.",
            "Groups same-scan reads and writes by continuous execution site and reports non-STATE variables whose behavior depends on values flowing across multiple continuously executed sites.",
        ),
        AnalyzerIssueLeafSpec(
            "same_cycle_shared_access_hazard",
            "Same-scan shared access hazard",
            "Shared variables that are read and written across multiple module paths within the same scan.",
            "Collects same-scan read and write events across module paths and reports shared variables whose behavior depends on intra-scan ordering.",
        ),
    ),
    "alarm-integrity": (
        AnalyzerIssueLeafSpec(
            "alarm.duplicate_tag",
            "Duplicate alarm tag",
            "Alarm sources reusing the same tag across the analyzed target.",
            "Collects alarm tag values, normalizes them, and reports tags emitted by more than one source.",
        ),
        AnalyzerIssueLeafSpec(
            "alarm.duplicate_condition",
            "Duplicate alarm condition",
            "Alarm sources reusing the same condition expression without clear deduplication.",
            "Normalizes alarm condition expressions and reports equivalent conditions across sources.",
        ),
        AnalyzerIssueLeafSpec(
            "alarm.conflicting_priority",
            "Conflicting alarm priority",
            "The same alarm tag or condition configured with conflicting priorities or severities.",
            "Groups alarms by normalized tag or condition and compares their configured priority values.",
        ),
        AnalyzerIssueLeafSpec(
            "alarm.never_cleared",
            "Never-cleared alarm",
            "Alarm booleans forced TRUE without any matching clear back to FALSE.",
            "Tracks boolean alarm writes and reports alarm paths that never record a clear write.",
        ),
    ),
    "signal-lifecycle": (
        AnalyzerIssueLeafSpec(
            "signal_lifecycle.read_before_write",
            "Signal read before write",
            "Signals consumed before any definite write in the current scope.",
            "Tracks per-scope signal writes and reports reads that occur before a known write is seen.",
        ),
        AnalyzerIssueLeafSpec(
            "signal_lifecycle.unconsumed_write",
            "Unconsumed signal write",
            "Signals written in a scope but never consumed later in that same scope.",
            "Tracks writes and later reads per signal in scope and reports writes with no downstream read.",
        ),
    ),
    "fault-handling": (
        AnalyzerIssueLeafSpec(
            "fault_handling.missing_recovery",
            "Fault missing recovery",
            "Fault paths that are raised but never explicitly cleared or acknowledged in scope.",
            "Tracks fault-like boolean writes and reports scopes that set a fault without any matching recovery path.",
        ),
        AnalyzerIssueLeafSpec(
            "fault_handling.unhandled_fault",
            "Unhandled fault",
            "Fault paths that are raised but never consumed by reachable handling logic.",
            "Checks whether a raised fault variable is ever read by reachable logic in the same scope.",
        ),
    ),
    "mms-interface": (
        AnalyzerIssueLeafSpec(
            "mms.duplicate_tag",
            "Duplicate MMS tag",
            "MMS tags used more than once across the analyzed target.",
            "Builds the interface inventory and groups mappings by normalized external tag.",
        ),
        AnalyzerIssueLeafSpec(
            "mms.datatype_mismatch",
            "MMS datatype mismatch",
            "MMS tags whose connected source datatypes conflict.",
            "Groups interface mappings by external tag and compares the resolved source datatypes.",
        ),
        AnalyzerIssueLeafSpec(
            "mms.naming_drift",
            "MMS naming drift",
            "MMS tag families that appear with inconsistent external spellings.",
            "Normalizes tag-family keys and reports families whose concrete tag spellings drift.",
        ),
        AnalyzerIssueLeafSpec(
            "mms.dead_tag",
            "Dead MMS tag",
            "Outgoing MMS tags whose mapped source variable is never written.",
            "Builds the MMS inventory and reports outgoing mappings with no observed writes on the source variable.",
        ),
    ),
    "spec-compliance": (
        AnalyzerIssueLeafSpec(
            "spec.basepicture_direct_code",
            "BasePicture direct code",
            "BasePicture code placed outside the allowed frame-module boundary.",
            "Checks AST-visible BasePicture code locations against the engineering spec rule.",
        ),
        AnalyzerIssueLeafSpec(
            "spec.sequence_step_prefix",
            "Sequence step prefix",
            "Sequence step names that do not use the required prefix.",
            "Compares each sequence step name to the configured engineering spec naming rule.",
        ),
        AnalyzerIssueLeafSpec(
            "spec.transition_name_missing",
            "Transition name missing",
            "Transitions that do not declare a name.",
            "Walks transition declarations and reports unnamed transitions.",
        ),
        AnalyzerIssueLeafSpec(
            "spec.transition_prefix",
            "Transition prefix",
            "Transition names that do not use the required prefix.",
            "Compares transition names against the configured prefix rule.",
        ),
        AnalyzerIssueLeafSpec(
            "spec.opmessage_use_signature",
            "OPMessage UseSignature",
            "OPMessage instances that enable UseSignature when the spec forbids it.",
            "Resolves OPMessage parameter values and reports instances with UseSignature enabled.",
        ),
        AnalyzerIssueLeafSpec(
            "spec.mes_batch_control_name",
            "MES_BatchControl name",
            "MES_BatchControl instances that do not use the required instance name.",
            "Checks each MES_BatchControl instance name against the engineering spec rule.",
        ),
        AnalyzerIssueLeafSpec(
            "spec.mes_batch_control_max_try",
            "MES_BatchControl Max_TRY",
            "MES_BatchControl Max_TRY values that do not resolve to the required value.",
            "Resolves the configured Max_TRY parameter and compares it to the engineering spec requirement.",
        ),
        AnalyzerIssueLeafSpec(
            "spec.mes_batch_control_repeat_try",
            "MES_BatchControl Repeat_TRY",
            "MES_BatchControl Repeat_TRY values that do not resolve to the required value.",
            "Resolves the configured Repeat_TRY parameter and compares it to the engineering spec requirement.",
        ),
    ),
    "data-dependency": (
        AnalyzerIssueLeafSpec(
            "data_dependency.path",
            "Dependency path",
            "Deterministic dependency chains between upstream reads and downstream writes.",
            "Builds dependency facts for assignments and emits the transitive path findings.",
        ),
        AnalyzerIssueLeafSpec(
            "data_dependency.initialization_order",
            "Initialization-order hazard",
            "Writes that depend on another local value before that value is initialized.",
            "Compares dependency order within a scope and reports writes that read a later-initialized value.",
        ),
    ),
    "resource-usage": (
        AnalyzerIssueLeafSpec(
            "resource_usage.release_without_acquire",
            "Release without acquire",
            "Resource handles released without a matching prior acquire.",
            "Tracks resource-handle lifecycles and reports release sites that have no recorded owner.",
        ),
        AnalyzerIssueLeafSpec(
            "resource_usage.acquire_without_release",
            "Acquire without release",
            "Resource handles acquired again before the previous acquisition is released.",
            "Tracks resource-handle state across control flow and reports reacquires without an intervening release.",
        ),
        AnalyzerIssueLeafSpec(
            "resource_usage.leaked_resource",
            "Leaked resource",
            "Resource handles that go out of scope without any release.",
            "Tracks the handle lifecycle to scope exit and reports resources still owned at the end.",
        ),
    ),
    "cyclomatic-complexity": (
        AnalyzerIssueLeafSpec(
            "module.cyclomatic_complexity",
            "Module cyclomatic complexity",
            "Program or module control-flow complexity above the configured module threshold.",
            "Counts module-level control-flow decisions and compares the result to the module threshold.",
        ),
        AnalyzerIssueLeafSpec(
            "step.cyclomatic_complexity",
            "Step cyclomatic complexity",
            "SFC step control-flow complexity above the configured step threshold.",
            "Counts decision points inside each SFC step and compares the result to the step threshold.",
        ),
    ),
    "comment-code": (
        AnalyzerIssueLeafSpec(
            "comment_code",
            "Code-like comments",
            "Comment blocks that look like inactive code fragments.",
            "Reads the source files for the selected target and applies the comment-code heuristics to each comment block.",
        ),
        AnalyzerIssueLeafSpec(
            "comment_code_read_error",
            "Comment scan read error",
            "Source files the comment-code scanner could not read successfully.",
            "Captures file read failures during comment scanning and reports them as dedicated findings.",
        ),
    ),
}

_ANALYZER_ISSUE_SOURCES: tuple[str, ...] = tuple(_ANALYZER_ISSUE_SPECS)


def _humanize_issue_kind_label(issue_kind: str) -> str:
    tail = issue_kind.split(".")[-1]
    return tail.replace("_", " ").replace("-", " ").title()


def _ensure_terminal_punctuation(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return ""
    if stripped.endswith((".", "!", "?")):
        return stripped
    return f"{stripped}."


def _summarize_labels(labels: tuple[str, ...], *, limit: int = 3) -> str:
    cleaned = tuple(label.strip() for label in labels if label.strip())
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    if len(cleaned) <= limit:
        head = ", ".join(cleaned[:-1])
        return f"{head}, and {cleaned[-1]}"
    head = ", ".join(cleaned[:limit])
    remaining = len(cleaned) - limit
    return f"{head}, and {remaining} more"


def _fallback_issue_leaf_spec(
    issue_kind: str, source: str, description: str, explanation: str | None
) -> AnalyzerIssueLeafSpec:
    label = _humanize_issue_kind_label(issue_kind)
    how = (explanation or "").strip() or f"Runs the {source} analyzer and reports only the {label.lower()} findings."
    return AnalyzerIssueLeafSpec(
        issue_kind=issue_kind,
        label=label,
        detection=description.strip() or f"Findings reported as {issue_kind}.",
        how=how,
    )


def _build_manual_issue_leaf_specs_by_kind() -> dict[str, AnalyzerIssueLeafSpec]:
    return {spec.issue_kind: spec for specs in _ANALYZER_ISSUE_SPECS.values() for spec in specs}


def _build_rule_derived_analyzer_issue_specs() -> dict[str, tuple[AnalyzerIssueLeafSpec, ...]]:
    manual_specs_by_kind = _build_manual_issue_leaf_specs_by_kind()
    derived: dict[str, tuple[AnalyzerIssueLeafSpec, ...]] = {}

    for analyzer_key in _ANALYZER_ISSUE_SOURCES:
        rule_entries = get_issue_rules_for_source(analyzer_key)
        if not rule_entries:
            derived[analyzer_key] = _ANALYZER_ISSUE_SPECS.get(analyzer_key, ())
            continue

        derived[analyzer_key] = tuple(
            manual_specs_by_kind.get(issue_kind)
            or _fallback_issue_leaf_spec(issue_kind, rule.source, rule.description, rule.explanation)
            for issue_kind, rule in rule_entries
        )

    return derived


_DERIVED_ANALYZER_ISSUE_SPECS: dict[str, tuple[AnalyzerIssueLeafSpec, ...]] = _build_rule_derived_analyzer_issue_specs()
_DERIVED_ANALYZER_ISSUE_SPECS_BY_KIND: dict[str, AnalyzerIssueLeafSpec] = {
    spec.issue_kind: spec for specs in _DERIVED_ANALYZER_ISSUE_SPECS.values() for spec in specs
}


def _default_analyzer_detection(analyzer_key: str, description: str) -> str:
    del analyzer_key
    if description.strip():
        return _ensure_terminal_punctuation(description)
    return "No detection notes available."


@lru_cache(maxsize=1)
def _default_analyzer_specs_by_key() -> dict[str, AnalyzerSpec]:
    return {spec.key: spec for spec in analysis_catalog_module.get_selectable_analyzers()}


def _default_analyzer_spec_for_key(analyzer_key: str) -> AnalyzerSpec | None:
    return _default_analyzer_specs_by_key().get(analyzer_key)


def _analyzer_display_name(analyzer_key: str) -> str:
    spec = _default_analyzer_spec_for_key(analyzer_key)
    if spec is not None:
        return spec.name
    return analyzer_key.replace("-", " ").title()


def _issue_display_label(issue_kind: str) -> str:
    spec = _DERIVED_ANALYZER_ISSUE_SPECS_BY_KIND.get(issue_kind)
    if spec is not None:
        return spec.label
    return _humanize_issue_kind_label(issue_kind)


def _default_analyzer_how(analyzer_key: str, description: str) -> str:
    analyzer_spec = _default_analyzer_spec_for_key(analyzer_key)
    if analyzer_spec is not None and analyzer_spec.composed_analyzer_keys:
        component_names = tuple(_analyzer_display_name(key) for key in analyzer_spec.composed_analyzer_keys)
        if analyzer_spec.composed_issue_kind_names:
            issue_labels = tuple(_issue_display_label(kind) for kind in analyzer_spec.composed_issue_kind_names)
            return (
                f"Runs {_summarize_labels(component_names)} and reports only "
                f"{_summarize_labels(issue_labels, limit=4)} findings."
            )
        return f"Runs {_summarize_labels(component_names)} and collates their findings into one report."

    specs = analyzer_issue_leaf_specs(analyzer_key)
    if specs:
        labels = tuple(spec.label for spec in specs)
        return f"Runs the analyzer and reports the maintained rule set, including {_summarize_labels(labels)} findings."
    if description.strip():
        return f"Runs the selected analysis and renders its report: {description}"
    return "No implementation notes available."


def analyzer_issue_leaf_specs(key: str) -> tuple[AnalyzerIssueLeafSpec, ...]:
    return _DERIVED_ANALYZER_ISSUE_SPECS.get(key, ())


def analyzer_has_issue_leaf_specs(key: str) -> bool:
    return key in _DERIVED_ANALYZER_ISSUE_SPECS


def analyzer_issue_exclusive_group_id(key: str) -> str | None:
    if analyzer_has_issue_leaf_specs(key):
        return f"exclusive.analyzer.{key}"
    return None


def planner_entry_detection(entry_id: str, analyzer_key: str | None, description: str) -> str:
    if entry_id.startswith("variables.issue."):
        return _VARIABLE_DETAILS.get(entry_id.removeprefix("variables.issue."), ("", ""))[0]
    if entry_id == "variables.high-confidence-suite":
        return _VARIABLE_DETAILS["1"][0]
    if entry_id in _STATIC_ENTRY_DETAILS:
        return _STATIC_ENTRY_DETAILS[entry_id][0]
    if entry_id.startswith("catalog.issue."):
        issue_kind = entry_id.removeprefix("catalog.issue.")
        spec = _DERIVED_ANALYZER_ISSUE_SPECS_BY_KIND.get(issue_kind)
        if spec is not None:
            return spec.detection
    if analyzer_key is not None:
        return _default_analyzer_detection(analyzer_key, description)
    return description or "No detection notes available."


def planner_entry_how(entry_id: str, analyzer_key: str | None, description: str) -> str:
    if entry_id.startswith("variables.issue."):
        return _VARIABLE_DETAILS.get(entry_id.removeprefix("variables.issue."), ("", ""))[1]
    if entry_id == "variables.high-confidence-suite":
        return _VARIABLE_DETAILS["1"][1]
    if entry_id in _STATIC_ENTRY_DETAILS:
        return _STATIC_ENTRY_DETAILS[entry_id][1]
    if entry_id.startswith("catalog.issue."):
        issue_kind = entry_id.removeprefix("catalog.issue.")
        spec = _DERIVED_ANALYZER_ISSUE_SPECS_BY_KIND.get(issue_kind)
        if spec is not None:
            return spec.how
    if analyzer_key is not None:
        return _default_analyzer_how(analyzer_key, description)
    if description:
        return f"Runs the selected analysis and renders its report: {description}"
    return "No implementation notes available."
