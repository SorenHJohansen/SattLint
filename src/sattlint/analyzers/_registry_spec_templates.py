"""Declarative analyzer spec templates for the registry builder."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

type AnalyzerCategory = Literal["correctness", "heuristic", "style", "development"]


@dataclass(frozen=True)
class AnalyzerSpecTemplate:
    key: str
    name: str
    description: str
    analyzer_attr: str
    category: AnalyzerCategory = "correctness"
    requires: tuple[str, ...] = ()
    context_kwargs: tuple[str, ...] = ()
    enabled: bool = True
    supports_live_diagnostics: bool = False
    direct_context: bool = False
    semantic_mapping_kind: str | None = None
    semantic_rule_source: str | None = None
    composed_analyzer_keys: tuple[str, ...] = ()
    composed_issue_kind_names: tuple[str, ...] = ()


def default_spec_templates(semantic_layer_analyzer_key: str) -> tuple[AnalyzerSpecTemplate, ...]:
    return (
        AnalyzerSpecTemplate(
            key=semantic_layer_analyzer_key,
            name="SattLine semantics",
            description="""Runs the full domain-aware semantic rule set over the program and its libraries in one pass
and reports every finding in a single deduplicated report.

Finds:
- Variable lifecycle issues (unused, read-only, never-read, shadowing)
- Interface-contract and parameter-mapping problems
- Module-structure and control-flow hazards
- Engineering-spec compliance violations

Examples: 'Output = Uninitialized;' (read before write), parallel SFC branches writing the same
variable, or parameter mappings to undeclared targets.""",
            analyzer_attr="analyze_sattline_semantics",
            context_kwargs=(
                "analysis_context",
                "debug",
                "unavailable_libraries",
                "analyzed_target_is_library",
                "sfc_mutually_exclusive_steps",
                "sfc_step_contracts",
                "config",
            ),
        ),
        AnalyzerSpecTemplate(
            key="variables",
            name="Variable issues",
            description="""Flags variables that are unused, read-only, never read after a write, or involved in type
mismatches, plus deeper lifecycle and structure issues.

Finds:
- Unused declarations and datatype fields
- Read-only non-Const variables and writes that are never read
- Implicit latching and reset contamination
- UI-only variables and duplicated datatypes
- Case-insensitive name collisions

Examples: a RECORD 'SensorType' with field 'UnusedField' that no code ever touches, or
'ReadOnly: integer := 5;' that is only ever read and never written.""",
            analyzer_attr="analyze_variables",
            context_kwargs=(
                "analysis_context",
                "debug",
                "unavailable_libraries",
                "analyzed_target_is_library",
                "include_dependency_moduletype_usage",
                "selected_issue_kinds",
                "config",
            ),
            supports_live_diagnostics=True,
            semantic_mapping_kind="variable",
            semantic_rule_source="variables",
        ),
        AnalyzerSpecTemplate(
            key="picture-display-paths",
            name="PictureDisplay paths",
            description="""Resolves constant and inferred PictureDisplay module paths (ComButProc_, ToggleWindow, and
picture-display rows) against the loaded module tree and reports paths that cannot be resolved.

Finds:
- Missing named children and ambiguous matches
- Missing program units and wildcards with no descendants
- Paths that step above the BasePicture
- Unimplemented .emf/.wmf asset references

Examples: a path '+MissingPanel' whose module does not exist under 'Root', or a variable-driven path
like 'Paths.OperationPath' that resolves to a missing module.""",
            analyzer_attr="analyze_picture_display_paths",
            context_kwargs=("graph", "analyzed_target_is_library"),
        ),
        AnalyzerSpecTemplate(
            key="mms-interface",
            name="MMS interface mappings",
            description="""Builds an inventory of MMSWriteVar/MMSReadVar/MMSReadVarCyc/MMSReadWrite interface mappings
(including .icf entries) and validates the external tag contract.

Finds:
- Duplicate external tags
- Conflicting datatypes for the same tag
- Naming drift within a tag family
- Outgoing tags whose source variable is never written

Examples: two MMSWriteVar instances both mapping 'MV_1001', one backed by an integer and one by a
real source, or an outgoing tag whose source is never written.""",
            analyzer_attr="analyze_mms_interface_variables",
            context_kwargs=("debug", "config"),
            semantic_rule_source="mms-interface",
        ),
        AnalyzerSpecTemplate(
            key="sfc",
            name="SFC checks",
            description="""Checks SFC sequences for parallel-branch write races, structurally unreachable nodes and
transitions, transitions whose guards are always true or false, and duplicate guards.

Finds:
- Parallel SFC branches writing the same variable or field
- Steps or transitions placed after a terminating node that can never run
- Transitions with always-true or always-false guards
- Configured mutually exclusive steps that can run at the same time
- Missing enter/exit step-contract writes that leak stale state between steps

Examples: two SFCParallel branches both writing 'SharedOutput', or a SEQSTEP placed after a SEQBREAK
that can never run.""",
            analyzer_attr="analyze_sfc",
            requires=("variables",),
            context_kwargs=("analysis_context", "mutually_exclusive_steps", "step_contracts"),
            semantic_mapping_kind="framework",
            semantic_rule_source="sfc",
        ),
        AnalyzerSpecTemplate(
            key="comment-code",
            name="Commented-out code",
            description="""Detects commented-out code fragments inside SattLine comments and reports their location with
the code indicators found (assignment, call, control, comparison).

Finds:
- Comment content that is valid SattLine code
- Read errors when a source file cannot be read

Example: '(* IF Running THEN Running = False; ENDIF; *)' - commented-out logic that makes active
code harder to review.""",
            analyzer_attr="analyze_comment_code",
            category="correctness",
            direct_context=True,
            semantic_rule_source="comment-code",
        ),
        AnalyzerSpecTemplate(
            key="shadowing",
            name="Variable shadowing",
            description="""Finds local declarations that hide an outer or global name, case-insensitively, making
references ambiguous and risking accidental scope capture.

Only root-origin declarations are considered; external library typedefs are ignored.

Example: a child moduletype declaring local 'Setting' while the parent declares 'setting', so
'Mirror = Setting;' refers to the wrong declaration.""",
            analyzer_attr="analyze_shadowing",
            context_kwargs=("debug", "unavailable_libraries"),
            semantic_mapping_kind="variable",
            semantic_rule_source="variables",
        ),
        AnalyzerSpecTemplate(
            key="spec-compliance",
            name="Engineering spec compliance",
            description="""Checks AST-visible constructs against the application engineering specification.

Finds:
- BasePicture code outside frame modules
- SFC steps not starting with 'ST_' and transitions not starting with 'TR_'
- Unnamed transitions
- OPMessage instances with UseSignature=True
- MES_BatchControl instances with a wrong name or wrong Max_TRY/Repeat_TRY values

Examples: 'SEQSTEP step_mix' (should start with 'ST_'), or 'OPMessage (UseSignature => True)'.""",
            analyzer_attr="analyze_spec_compliance",
            context_kwargs=("debug", "unavailable_libraries"),
            semantic_mapping_kind="spec",
            semantic_rule_source="spec-compliance",
        ),
        AnalyzerSpecTemplate(
            key="loop-output-refactor",
            name="Loop output refactor",
            description="""Detects dependency cycles among equation blocks and SFC step enter/active/exit blocks within
one module, where blocks write variables that are read by each other.

Each reported loop delays at least one dependency by a full scan until the participating blocks are
reordered or refactored.

Example: 'EquationBlock Input: A = B;' and 'EquationBlock Feedback: B = A;' form a two-block cycle.""",
            analyzer_attr="analyze_loop_output_refactor",
            semantic_rule_source="loop-output-refactor",
        ),
        AnalyzerSpecTemplate(
            key="alarm-integrity",
            name="Alarm integrity",
            description="""Cross-module alarm-source checks on tag, condition, priority, and latch behavior.

Finds:
- Alarm tags configured more than once
- Conditions reused by several alarm sources
- Conflicting priorities or severities for the same tag or condition
- Alarm variables that are only ever forced True and never cleared

Examples: 'AlarmTrip = True;' with no False write anywhere (latch risk), or the same tag configured
with priorities 1 and 3.""",
            analyzer_attr="analyze_alarm_integrity",
            context_kwargs=("debug", "unavailable_libraries"),
            semantic_mapping_kind="framework",
            semantic_rule_source="alarm-integrity",
        ),
        AnalyzerSpecTemplate(
            key="initial-values",
            name="Initial value validation",
            description="""Detects recipe (recpar) and engineering (engpar) parameter modules whose required value
parameter has no resolvable startup value.

A parameter is satisfied only by a literal mapping, a mapping to an initialized variable, or a
moduletype default.

Example: RecParReal with 'Value: real;' left unmapped and undefaulted while Min_/Max_ are
configured.""",
            analyzer_attr="analyze_initial_values",
            context_kwargs=("debug", "unavailable_libraries"),
            semantic_mapping_kind="framework",
            semantic_rule_source="initial-values",
        ),
        AnalyzerSpecTemplate(
            key="interface-contracts",
            name="Interface contracts",
            description="""Validates moduletype instance parameter mappings against the declared moduletype contract.

Finds:
- Mappings to undeclared parameters
- Required parameters left unmapped
- Incompatible datatypes across the module boundary (including anytype required fields and dynamic
  array elements)
- String-like datatype mismatches

Examples: 'Child : ChildType (BogusParam => 1)' with no such parameter, or mapping an integer
variable to a boolean parameter.""",
            analyzer_attr="analyze_interface_contracts",
            context_kwargs=("debug", "unavailable_libraries", "analyzed_target_is_library"),
        ),
        AnalyzerSpecTemplate(
            key="powerup",
            name="Power-up",
            description="""Combines startup-value gaps and unsafe startup defaults into one power-up report.

Finds:
- Recipe/engineering parameters without a resolvable initial value
- Boolean variables defaulting to True whose names contain 'enable' or 'bypass'

Examples: 'EnablePump: boolean := True;' (can activate equipment from startup) or 'SafetyBypass:
boolean := True;' (can bypass safety checks from startup).""",
            analyzer_attr="analyze_powerup",
            context_kwargs=("debug", "unavailable_libraries"),
            composed_analyzer_keys=("initial-values", "unsafe-defaults"),
        ),
        AnalyzerSpecTemplate(
            key="naming-consistency",
            name="Naming consistency",
            description="""Detects declarations that break the configured naming style for variables, modules, and
instances.

With the default 'infer' mode the analyzer picks the most common style per symbol kind and flags
outliers. Explicit styles (pascal, camel, snake, upper_snake, lower, upper) and per-target
allowlists are configurable.

Example: with Pascal inferred as the dominant style, 'tank_level: integer' is flagged while
'FlowRate' and 'PumpSpeed' are accepted.""",
            analyzer_attr="analyze_naming_consistency",
            category="style",
            context_kwargs=("rules",),
        ),
        AnalyzerSpecTemplate(
            key="cyclomatic-complexity",
            name="Cyclomatic complexity",
            description="""Reports programs, module types, nested modules, and SFC steps whose control-flow complexity
exceeds thresholds (default 10 for modules, 6 for SFC steps).

Each IF/ELSIF branch, AND/OR connector, ternary branch, and SFC alternative/parallel branch adds to
the count.

Example: an equation block with 10 'IF CondN THEN ...' blocks reaches complexity 11 and is
reported.""",
            analyzer_attr="analyze_cyclomatic_complexity",
            category="style",
        ),
        AnalyzerSpecTemplate(
            key="parameter-drift",
            name="Parameter drift",
            description="""Detects moduletype instances that resolve to differing literal parameter values across the
analyzed target.

Instances are grouped by moduletype and parameter; when two or more instances resolve to two or
more distinct literal values, each drifting instance is reported.

Example: ValveA with 'Timeout => 10' and ValveB with 'Timeout => 15' on the same DoseValve
moduletype.""",
            analyzer_attr="analyze_parameter_drift",
            category="heuristic",
            context_kwargs=("unavailable_libraries",),
        ),
        AnalyzerSpecTemplate(
            key="signal-lifecycle",
            name="Signal lifecycle",
            description="""Tracks signal reads and writes within each module scope.

Finds:
- Signals consumed before any definite write in the scope
- Signals written but never consumed later in that same scope

Examples: 'OutputSignal = InputSignal;' before InputSignal is ever written, or 'NeverConsumed =
False;' with no later read.""",
            analyzer_attr="analyze_signal_lifecycle",
            semantic_mapping_kind="framework",
            semantic_rule_source="signal-lifecycle",
        ),
        AnalyzerSpecTemplate(
            key="loop-stability",
            name="Loop stability",
            description="""Detects contradictory literal setpoint assignments within a single scope that can destabilize
scan-loop behavior.

Finds the same variable assigned two or more distinct literal values on the same path.

Example: 'Setpoint = 10;' followed by 'Setpoint = 20;' in the same equation block.""",
            analyzer_attr="analyze_loop_stability",
            semantic_mapping_kind="framework",
            semantic_rule_source="loop-stability",
        ),
        AnalyzerSpecTemplate(
            key="fault-handling",
            name="Fault handling",
            description="""Checks fault and alarm boolean paths for raise/recovery balance within each scope.

Finds:
- Paths raised (written True) but never explicitly cleared or acknowledged
- Paths raised but never consumed by reachable logic

Example: 'HighFault = True;' with no False write and no later read.""",
            analyzer_attr="analyze_fault_handling",
            semantic_mapping_kind="framework",
            semantic_rule_source="fault-handling",
        ),
        AnalyzerSpecTemplate(
            key="numeric-constraints",
            name="Numeric constraints",
            description="""Validates literal assignments against the visible Min_/Max_ bounds declared for the target
variable.

Bounds are inferred from sibling variables named 'Min_<name>' or 'Max_<name>'; an assignment
resolving outside the range is reported.

Example: with 'Min_Output = 0' and 'Max_Output = 10', 'Output = 12;' is flagged.""",
            analyzer_attr="analyze_numeric_constraints",
            semantic_mapping_kind="framework",
            semantic_rule_source="numeric-constraints",
        ),
        AnalyzerSpecTemplate(
            key="data-dependency",
            name="Data dependency",
            description="""Reports transitive assignment chains and initialization-order hazards.

Finds:
- A dependency path when a write's value depends on a chain of three or more symbols
- An initialization-order hazard when a write reads a same-scope local before it is initialized

Examples: 'Mid = Input; Output = Mid;' (chain) and 'Output = Source; Source = 3;' (read before
init).""",
            analyzer_attr="analyze_data_dependency",
            context_kwargs=("unavailable_libraries", "analyzed_target_is_library"),
            semantic_rule_source="data-dependency",
        ),
        AnalyzerSpecTemplate(
            key="config-drift",
            name="Config drift",
            description="""Detects moduletype instances whose mapped configuration parameter signatures drift across the
analyzed target.

When two or more instances of the same moduletype map a configuration parameter to different
values, the drifting parameter is reported for the group.

Example: ValveA with 'Timeout => 10' and ValveB with 'Timeout => 15' on the same DoseValve
moduletype.""",
            analyzer_attr="analyze_config_drift",
            context_kwargs=("unavailable_libraries",),
            semantic_mapping_kind="framework",
            semantic_rule_source="config-drift",
        ),
        AnalyzerSpecTemplate(
            key="scan-loop-resource-usage",
            name="Scan-loop resource usage",
            description="""Finds builtin calls that are not precision-scan-safe inside continuously executed scan-cycle
contexts: every equation block and every SFC step's active code.

Calls in one-shot enter/exit code are not flagged. String, time, status, and system-category
builtins are typical offenders.

Example: 'AssignSystemString(SysVarId, Value, Status);' inside an equation block.""",
            analyzer_attr="analyze_scan_loop_resource_usage",
        ),
        AnalyzerSpecTemplate(
            key="resource-usage",
            name="Resource usage",
            description="""Tracks the lifecycle of locally owned resource handles opened via OpenDevice/OpenReadFile/
OpenWriteFile and closed via CloseDevice/CloseFile.

Finds:
- Releases without a matching acquire
- Re-acquires before the previous acquire is released
- Handles that are never released in the scope
- Forwards scan-loop resource hazards

Examples: 'CloseFile(FileRef, ...)' with no prior open, or opening 'FileRef' twice without a close
in between.""",
            analyzer_attr="analyze_resource_usage",
            context_kwargs=("unavailable_libraries", "analyzed_target_is_library"),
            semantic_rule_source="resource-usage",
        ),
        AnalyzerSpecTemplate(
            key="scan-concurrency",
            name="Scan concurrency",
            description="""Detects parallel SFC branches that write the same variable or field without arbitration.

A write/write conflict across two SFCParallel branches is reported as a parallel write race.

Example: 'BranchLeft' and 'BranchRight' both assigning 'SharedOutput' in their active code.""",
            analyzer_attr="analyze_scan_concurrency",
            context_kwargs=("config",),
            composed_analyzer_keys=("same-cycle",),
            composed_issue_kind_names=("sfc_parallel_write_race",),
        ),
        AnalyzerSpecTemplate(
            key="scan-shared-access",
            name="Scan shared access",
            description="""Detects non-STATE variables that are read in one continuous scan site and written in another
within the same scan.

Equation blocks and step active-code phases are distinct scan sites; accesses within a single site
do not trigger it.

Example: 'Output = SharedValue;' in ReadEq and 'SharedValue = 2;' in WriteEq, with SharedValue not
declared State.""",
            analyzer_attr="analyze_scan_shared_access",
            context_kwargs=("config",),
            composed_analyzer_keys=("same-cycle",),
            composed_issue_kind_names=("same_cycle_non_state_multi_site_hazard",),
        ),
        AnalyzerSpecTemplate(
            key="same-cycle",
            name="Same-cycle hazards",
            description="""Detects same-scan shared-variable hazards across modules and parallel SFC branches.

Finds:
- Shared variables read in one module and written in another within one scan
- Parallel branches where one reads and another writes the same variable
- Parallel branches that both write the same variable (write race)
- Non-STATE variables accessed across multiple continuous scan sites

Example: module Reader does 'Output = SharedValue;' while module Writer does 'SharedValue = 0;'.""",
            analyzer_attr="analyze_same_cycle",
            context_kwargs=("analysis_context", "debug", "unavailable_libraries", "analyzed_target_is_library"),
            supports_live_diagnostics=True,
            semantic_mapping_kind="framework",
            semantic_rule_source="same-cycle",
        ),
        AnalyzerSpecTemplate(
            key="timing",
            name="Timing",
            description="""Detects scan-cycle temporal hazards: :OLD reads after a same-scan write, implicit reads that
should use :NEW, :OLD used as a write target or out-parameter, and non-precision-scan-safe calls
in scan-cycle code.

Composes dataflow temporal checks with scan-loop resource usage.

Examples: 'PrevAccum = Accum:Old;' right after 'Accum = Accum + Smoothed;', or
'MaxLim(1.0, 2.0, 0.1, Flag:Old);' passing :OLD as an out-parameter.""",
            analyzer_attr="analyze_timing",
            context_kwargs=("unavailable_libraries", "analyzed_target_is_library"),
            composed_analyzer_keys=("dataflow", "scan-loop-resource-usage"),
            composed_issue_kind_names=(
                "dataflow.scan_cycle_stale_read",
                "dataflow.scan_cycle_implicit_new",
                "dataflow.scan_cycle_temporal_misuse",
                "scan_cycle.resource_usage",
            ),
        ),
        AnalyzerSpecTemplate(
            key="version-drift",
            name="Version drift",
            description="""Detects repeated module names that have drifted structurally beyond date-code-only differences.

Modules with the same case-insensitive name are fingerprinted; when two or more structural variants
exist, drift in module parameters, local variables, submodule structure, or module code is reported.

Example: two 'Mixer' modules whose code differs only in 'Output = 1;' vs 'Output = 2;'.""",
            analyzer_attr="analyze_version_drift",
            category="heuristic",
            context_kwargs=("debug",),
            semantic_rule_source="version-drift",
        ),
        AnalyzerSpecTemplate(
            key="safety-paths",
            name="Safety paths",
            description="""Traces safety-critical signals (paths containing emergency, shutdown, or estop) across the
target and reports ones that are written but never consumed by any reader.

Example: 'EmergencyShutdown = InCommand;' written inside GuardType but the path is never read
anywhere.""",
            analyzer_attr="analyze_safety_paths",
            context_kwargs=("debug", "unavailable_libraries", "analyzed_target_is_library"),
            semantic_mapping_kind="framework",
            semantic_rule_source="safety-paths",
        ),
        AnalyzerSpecTemplate(
            key="taint-paths",
            name="Taint paths",
            description="""Traces external MES, operator, or sensor inputs into safety-critical sinks (emergency, shutdown,
estop, interlock, trip) across module boundaries.

Only flows that span multiple modules are reported; single-module internal wiring is not flagged.

Example: operator input 'Root.OperatorCommand' reaching 'Root.Guard.EmergencyShutdown' via a
moduletype mapping.""",
            analyzer_attr="analyze_taint_paths",
            context_kwargs=("debug", "unavailable_libraries", "analyzed_target_is_library"),
            semantic_mapping_kind="framework",
            semantic_rule_source="taint-paths",
        ),
        AnalyzerSpecTemplate(
            key="unsafe-defaults",
            name="Unsafe defaults",
            description="""Flags boolean variables that default to True and whose name contains 'enable' or 'bypass'.

Finds:
- 'Enable' names that can activate equipment or logic from startup
- 'Bypass' names that can bypass safety checks from startup

Examples: 'EnablePump: boolean := True;' or 'SafetyBypass: boolean := True;'.""",
            analyzer_attr="analyze_unsafe_defaults",
            semantic_mapping_kind="framework",
            semantic_rule_source="unsafe-defaults",
        ),
        AnalyzerSpecTemplate(
            key="dataflow",
            name="Lightweight dataflow",
            description="""Symbolic dataflow analysis across branches: read-before-write, dead overwrites, conditions that
are always true or false, unreachable branches and sequence nodes, and self-comparisons that
collapse to a constant.

Also checks State :OLD/:NEW access validity: :OLD is read-only and both qualifiers are only legal
on State variables.

Examples: 'Output = Uninitialized;' (read before write), 'Flag AND NOT Flag' (always false), or
'Flag = True; Flag = Condition;' (dead overwrite).""",
            analyzer_attr="analyze_dataflow",
            context_kwargs=("unavailable_libraries", "analyzed_target_is_library", "shared_artifacts"),
            semantic_mapping_kind="framework",
            semantic_rule_source="dataflow",
        ),
        AnalyzerSpecTemplate(
            key="state-inference",
            name="State inference",
            description="""Infers stable boolean, numeric, and string state along each path and reports contradictory
control flow that makes branches impossible.

Finds:
- Always-true and always-false conditions
- Unreachable branches
- A structured summary of the inferred state

Example: with 'Count: integer := 5;', 'IF Count < 0 THEN ... ENDIF' is reported as always false
with its branch unreachable.""",
            analyzer_attr="analyze_state_inference",
            context_kwargs=("unavailable_libraries", "analyzed_target_is_library"),
        ),
    )


__all__ = ["AnalyzerSpecTemplate", "default_spec_templates"]
