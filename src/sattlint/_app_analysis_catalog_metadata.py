from __future__ import annotations

from dataclasses import dataclass

from ._app_analysis_catalog_shared import (
    ENTRY_COMMENTED_OUT_CODE,
    ENTRY_DATATYPE_USAGE,
    ENTRY_MODULE_LOCAL_VARIABLES,
    ENTRY_VARIABLE_USAGE_TRACE,
)


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

_ANALYZER_DETAILS: dict[str, tuple[str, str]] = {
    "alarm-integrity": (
        "Duplicate alarm tags, duplicate conditions, conflicting priorities, and never-cleared alarm writes.",
        "Traverses alarm candidates, normalizes tag, condition, and priority signatures, and tracks boolean clear paths.",
    ),
    "config-drift": (
        "Instances of the same moduletype whose visible configuration signatures diverge.",
        "Groups instances by moduletype and compares their resolved configuration parameter signatures.",
    ),
    "cyclomatic-complexity": (
        "Module or step control-flow complexity above the configured thresholds.",
        "Counts control-flow decisions at module and step level and compares them to the configured thresholds.",
    ),
    "data-dependency": (
        "Deterministic dependency chains and initialization-order hazards.",
        "Builds dependency facts for reads and writes, then emits transitive path and initialization-order findings.",
    ),
    "dataflow": (
        "Constant conditions, dead overwrites, uninitialized reads, and unreachable dataflow paths.",
        "Runs the lightweight dataflow analyzer and evaluates per-variable state, pending writes, and branch reachability.",
    ),
    "fault-handling": (
        "Fault paths that are raised without recovery or without any reachable consumer.",
        "Tracks fault-like booleans within each scope and checks for matching clear and read paths.",
    ),
    "initial-values": (
        "Required startup values that are missing from recipe or engineering parameter modules.",
        "Walks parameter modules and reports required defaults that never resolve to a startup value.",
    ),
    "loop-output-refactor": (
        "Dependency cycles across sorted equation blocks and active SFC step code.",
        "Constructs cross-block dependency edges and reports feedback cycles that force implicit delay behavior.",
    ),
    "loop-stability": (
        "Contradictory literal setpoint writes within one scope.",
        "Scans setpoint assignments within a scope and compares literal writes for contradictions.",
    ),
    "mms-interface": (
        "Duplicate MMS tags, datatype mismatches, naming drift, and dead outgoing tags.",
        "Builds the MMS and ICF inventory, then derives issue findings from the collected interface data.",
    ),
    "numeric-constraints": (
        "Literal assignments outside the resolved Min_ or Max_ bounds for a target variable.",
        "Resolves Min_ and Max_ style bounds and compares literal assignments against those limits.",
    ),
    "powerup": (
        "Startup gaps from missing required defaults and unsafe startup booleans.",
        "Runs the initial-values and unsafe-defaults analyzers together and collates their startup findings.",
    ),
    "resource-usage": (
        "Acquires without release, releases without acquire, and leaked resources.",
        "Tracks resource-handle acquisition and release lifecycles across the analyzed control flow.",
    ),
    "safety-paths": (
        "Safety-related signals that are written but never consumed across reachable paths.",
        "Performs cross-module tracing from safety signal writes to reachable consumers.",
    ),
    "scan-concurrency": (
        "Parallel SFC branches that write the same variable without arbitration.",
        "Runs the SFC analyzer with the parallel-write-race subset and reports only those findings.",
    ),
    "scan-loop-resource-usage": (
        "Non precision-scan-safe builtin calls inside equation blocks and active-step code.",
        "Scans equation blocks and active-step code for builtins that are not safe in continuous scan execution.",
    ),
    "sfc": (
        "Parallel-write races plus structural or contract issues in SFC sequences and transitions.",
        "Walks SFC structures, normalizes transitions and contracts, and reports the selected structural or guard issues.",
    ),
    "signal-lifecycle": (
        "Signals read before write or written without any later consumption in scope.",
        "Tracks per-scope writes and reads for signals and reports read-before-write and unconsumed-write paths.",
    ),
    "spec-compliance": (
        "Violations of the configured engineering specification rules.",
        "Runs the project-specific engineering spec checks against AST-visible program structure.",
    ),
    "taint-paths": (
        "External inputs that propagate into safety-critical sinks.",
        "Marks external inputs as tainted and traces their propagation into critical sink variables.",
    ),
    "timing": (
        "Scan-cycle temporal hazards combined with scan-loop resource misuse.",
        "Combines the timing-related dataflow checks with scan-loop resource-usage findings into one report.",
    ),
    "unsafe-defaults": (
        "Boolean input defaults that start TRUE and can enable logic unsafely.",
        "Scans variable declarations for boolean VAR_INPUT or VAR_IN_OUT defaults set to TRUE.",
    ),
    "version-drift": (
        "Modules sharing a name that have drifted structurally beyond datecode-only changes.",
        "Compares repeated module structures and reports divergence beyond datecode-only changes.",
    ),
}

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


def analyzer_issue_leaf_specs(key: str) -> tuple[AnalyzerIssueLeafSpec, ...]:
    return _ANALYZER_ISSUE_SPECS.get(key, ())


def analyzer_has_issue_leaf_specs(key: str) -> bool:
    return key in _ANALYZER_ISSUE_SPECS


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
        for specs in _ANALYZER_ISSUE_SPECS.values():
            for spec in specs:
                if spec.issue_kind == issue_kind:
                    return spec.detection
    if analyzer_key is not None and analyzer_key in _ANALYZER_DETAILS:
        return _ANALYZER_DETAILS[analyzer_key][0]
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
        for specs in _ANALYZER_ISSUE_SPECS.values():
            for spec in specs:
                if spec.issue_kind == issue_kind:
                    return spec.how
    if analyzer_key is not None and analyzer_key in _ANALYZER_DETAILS:
        return _ANALYZER_DETAILS[analyzer_key][1]
    if description:
        return f"Runs the selected analysis and renders its report: {description}"
    return "No implementation notes available."
