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
            description=(
                "Runs all the checks in one pass and shows every problem in one combined list.\n"
                "\n"
                "Finds:\n"
                "- Variables that are declared but never used.\n"
                "- Parameter mappings that point to parameters that do not exist.\n"
                "- Code that can never run.\n"
                "- Names that break the engineering rules, for example a step that does not start with "
                "'ST_'."
            ),
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
            description=(
                "Checks that variables and data type fields are declared, written, and read in a sensible "
                "way.\n"
                "\n"
                "Finds:\n"
                "- Unused declarations, for example a local 'Spare: integer;' that is never used.\n"
                "- Read-only non-Const variables, for example 'ReadOnly: integer := 5;' that is read but "
                "never changed.\n"
                "- Writes that are never read, for example 'Counter = 1;' when Counter is never read "
                "afterwards.\n"
                "- Unused or never-read data type fields, for example a RECORD field 'UnusedField' that no "
                "code touches.\n"
                "- Values set to True on some paths but never set back to False, for example 'AlarmFlag = "
                "True;' with no later False write.\n"
                "- Values only shown on a screen and never used in logic.\n"
                "- Names that differ only by letter case in the same module, for example 'flow' and 'Flow'."
            ),
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
            description=(
                "Checks that PictureDisplay paths (ComButProc_, ToggleWindow, and picture-display rows) "
                "point to modules that exist.\n"
                "\n"
                "Finds:\n"
                "- A module that does not exist, for example '+MissingPanel' when no such module exists "
                "under 'Root'.\n"
                "- A name that matches more than one module.\n"
                "- A program that is not loaded, for example 'OtherProg:+Panel' with OtherProg missing.\n"
                "- A wildcard such as '*X' with no matching module.\n"
                "- A path that goes above the BasePicture.\n"
                "- Unimplemented .emf/.wmf asset references."
            ),
            analyzer_attr="analyze_picture_display_paths",
            context_kwargs=("graph", "analyzed_target_is_library"),
        ),
        AnalyzerSpecTemplate(
            key="mms-interface",
            name="MMS interface mappings",
            description=(
                "Builds a list of MMSWriteVar/MMSReadVar/MMSReadVarCyc/MMSReadWrite connections "
                "(including .icf entries) and checks the tags used to talk to other systems.\n"
                "\n"
                "Finds:\n"
                "- The same tag used more than once, for example two connections both using 'MV_1001'.\n"
                "- A tag connected to different data types, for example an integer on one side and a real "
                "on the other.\n"
                "- The same tag written in different ways, for example 'MV-1001' versus 'MV_1001'.\n"
                "- Tags whose source is never written, for example a tag mapped to 'OtherVal' that is never "
                "assigned."
            ),
            analyzer_attr="analyze_mms_interface_variables",
            context_kwargs=("debug", "config", "analysis_context"),
            requires=("variables",),
            semantic_rule_source="mms-interface",
        ),
        AnalyzerSpecTemplate(
            key="sfc",
            name="SFC checks",
            description=(
                "Checks SFC sequences for places where code could conflict, can never run, or has "
                "transition problems.\n"
                "\n"
                "Finds:\n"
                "- Parallel branches that write the same variable, for example two SFCParallel branches "
                "both writing 'SharedOutput'.\n"
                "- Steps or transitions that can never run, for example a SEQSTEP placed after a "
                "SEQBREAK.\n"
                "- Transitions that always fire or never fire.\n"
                "- Transitions in one branch with the same condition.\n"
                "- Steps that should not run at the same time but can.\n"
                "- Missing start or end code that lets an old value carry over between steps."
            ),
            analyzer_attr="analyze_sfc",
            requires=("variables",),
            context_kwargs=("analysis_context", "mutually_exclusive_steps", "step_contracts"),
            semantic_mapping_kind="framework",
            semantic_rule_source="sfc",
        ),
        AnalyzerSpecTemplate(
            key="comment-code",
            name="Commented-out code",
            description=(
                "Detects commented-out code inside SattLine comments.\n"
                "\n"
                "Finds:\n"
                "- Comments that still contain working code, for example "
                "'(* IF Running THEN Running = False; ENDIF; *)'.\n"
                "- Files that cannot be read."
            ),
            analyzer_attr="analyze_comment_code",
            category="correctness",
            direct_context=True,
            semantic_rule_source="comment-code",
        ),
        AnalyzerSpecTemplate(
            key="shadowing",
            name="Variable shadowing",
            description=(
                "Finds local declarations that hide a name already declared further out, which makes "
                "references unclear.\n"
                "\n"
                "Only declarations from the main program are considered; library types are ignored.\n"
                "\n"
                "Example: a child moduletype declares local 'Setting' while the parent declares 'setting', "
                "so 'Mirror = Setting;' may point to the wrong one."
            ),
            analyzer_attr="analyze_shadowing",
            context_kwargs=("debug", "unavailable_libraries"),
            semantic_mapping_kind="variable",
            semantic_rule_source="variables",
        ),
        AnalyzerSpecTemplate(
            key="spec-compliance",
            name="Engineering spec compliance",
            description=(
                "Checks code against the engineering rules.\n"
                "\n"
                "Finds:\n"
                "- Code in the BasePicture that should be inside a frame module.\n"
                "- Steps that do not start with 'ST_' or transitions that do not start with 'TR_', for "
                "example 'SEQSTEP step_mix'.\n"
                "- Transitions without a name.\n"
                "- OPMessage instances with UseSignature=True.\n"
                "- MES_BatchControl instances with the wrong name or wrong Max_TRY/Repeat_TRY values."
            ),
            analyzer_attr="analyze_spec_compliance",
            context_kwargs=("debug", "unavailable_libraries", "analyzed_target_is_library"),
            semantic_mapping_kind="spec",
            semantic_rule_source="spec-compliance",
        ),
        AnalyzerSpecTemplate(
            key="alarm-integrity",
            name="Alarm integrity",
            description=(
                "Checks alarm tags, conditions, priorities, and whether alarms can turn off, across "
                "modules.\n"
                "\n"
                "Finds:\n"
                "- The same alarm tag used twice, for example the same tag in two alarm sources.\n"
                "- The same condition used by several alarms.\n"
                "- The same tag or condition with different priorities or severities, for example "
                "priorities 1 and 3.\n"
                "- Alarms that are only ever set True and never set False, for example 'AlarmTrip = True;' "
                "with no False write."
            ),
            analyzer_attr="analyze_alarm_integrity",
            context_kwargs=("debug", "unavailable_libraries", "analyzed_target_is_library"),
            semantic_mapping_kind="framework",
            semantic_rule_source="alarm-integrity",
        ),
        AnalyzerSpecTemplate(
            key="interface-contracts",
            name="Interface contracts",
            description=(
                "Checks that moduletype instance mappings match what the moduletype declares.\n"
                "\n"
                "Finds:\n"
                "- Mappings to parameters that do not exist, for example 'Child : ChildType "
                "(BogusParam => 1)'.\n"
                "- Required parameters that are not mapped.\n"
                "- Data types that do not match across the boundary, for example an integer mapped to a "
                "boolean parameter, or a missing required field such as 'Inner.Value'.\n"
                "- String mappings with mismatched types, for example an identstring parameter mapped from "
                "a string variable."
            ),
            analyzer_attr="analyze_interface_contracts",
            context_kwargs=("debug", "unavailable_libraries", "analyzed_target_is_library", "analysis_context"),
            requires=("variables",),
        ),
        AnalyzerSpecTemplate(
            key="powerup",
            name="Power-up",
            description=(
                "Combines unsafe startup defaults into one power-up report.\n"
                "\n"
                "Finds Boolean variables set to True at startup whose name contains 'enable' or 'bypass', "
                "for example 'EnablePump: boolean := True;' or 'SafetyBypass: boolean := True;'."
            ),
            analyzer_attr="analyze_powerup",
            context_kwargs=("debug", "unavailable_libraries", "analyzed_target_is_library"),
            composed_analyzer_keys=("unsafe-defaults",),
        ),
        AnalyzerSpecTemplate(
            key="naming-consistency",
            name="Naming consistency",
            description=(
                "Finds declarations that do not follow the configured naming style for variables, modules, "
                "and instances.\n"
                "\n"
                "With the default 'infer' mode the tool picks the most common style for each kind of name "
                "and flags the odd ones out. Explicit styles (pascal, camel, snake, upper_snake, lower, "
                "upper) and lists of allowed names are configurable.\n"
                "\n"
                "Example: with Pascal as the dominant style, 'tank_level: integer' is flagged while "
                "'FlowRate' and 'PumpSpeed' are accepted."
            ),
            analyzer_attr="analyze_naming_consistency",
            category="style",
            context_kwargs=("rules", "analyzed_target_is_library"),
        ),
        AnalyzerSpecTemplate(
            key="cyclomatic-complexity",
            name="Cyclomatic complexity",
            description=(
                "Reports programs, module types, nested modules, and SFC steps that have too many decision "
                "points (default limit 10 for modules, 6 for SFC steps).\n"
                "\n"
                "Each IF/ELSIF branch, AND/OR connector, ternary branch, and SFC alternative or parallel "
                "branch adds one.\n"
                "\n"
                "Example: an equation block with 10 'IF CondN THEN ...' blocks reaches 11 and is reported."
            ),
            analyzer_attr="analyze_cyclomatic_complexity",
            category="style",
            context_kwargs=("analyzed_target_is_library",),
        ),
        AnalyzerSpecTemplate(
            key="parameter-drift",
            name="Parameter drift",
            description=(
                "Finds moduletype instances whose actual parameter values differ across the analyzed "
                "target.\n"
                "\n"
                "Instances are grouped by moduletype and parameter. When two or more instances end up "
                "with two or more different values, each drifting instance is reported.\n"
                "\n"
                "Example: ValveA with 'Timeout => 10' and ValveB with 'Timeout => 15' on the same "
                "DoseValve moduletype."
            ),
            analyzer_attr="analyze_parameter_drift",
            category="heuristic",
            context_kwargs=("unavailable_libraries",),
        ),
        AnalyzerSpecTemplate(
            key="signal-lifecycle",
            name="Signal lifecycle",
            description=(
                "Tracks when signals are read and written in each module.\n"
                "\n"
                "Finds:\n"
                "- Signals read before any value is set, for example 'OutputSignal = InputSignal;' when "
                "InputSignal is never set earlier.\n"
                "- Signals written but never read, for example 'NeverConsumed = False;' with no later read."
            ),
            analyzer_attr="analyze_signal_lifecycle",
            context_kwargs=("analyzed_target_is_library",),
            semantic_mapping_kind="framework",
            semantic_rule_source="signal-lifecycle",
        ),
        AnalyzerSpecTemplate(
            key="loop-stability",
            name="Loop stability",
            description=(
                "Finds two different values set on the same variable in one module.\n"
                "\n"
                "The same variable is set to two or more different literal values on the same path.\n"
                "\n"
                "Example: 'Setpoint = 10;' followed by 'Setpoint = 20;' in the same equation block."
            ),
            analyzer_attr="analyze_loop_stability",
            context_kwargs=("analyzed_target_is_library",),
            semantic_mapping_kind="framework",
            semantic_rule_source="loop-stability",
        ),
        AnalyzerSpecTemplate(
            key="fault-handling",
            name="Fault handling",
            description=(
                "Checks fault and alarm booleans to see if a raised fault is ever cleared or handled in "
                "the same module.\n"
                "\n"
                "Finds:\n"
                "- Faults set True but never set False or acknowledged, for example 'HighFault = True;' "
                "with no False write.\n"
                "- Faults set True but never read by any code, for example the same variable is never used "
                "afterwards."
            ),
            analyzer_attr="analyze_fault_handling",
            context_kwargs=("analyzed_target_is_library",),
            semantic_mapping_kind="framework",
            semantic_rule_source="fault-handling",
        ),
        AnalyzerSpecTemplate(
            key="numeric-constraints",
            name="Numeric constraints",
            description=(
                "Checks literal assignments against the Min_/Max_ limits declared for the target "
                "variable.\n"
                "\n"
                "Limits are taken from sibling variables named 'Min_<name>' or 'Max_<name>'. Assignments "
                "outside the range are reported.\n"
                "\n"
                "Example: with 'Min_Output = 0' and 'Max_Output = 10', 'Output = 12;' is flagged."
            ),
            analyzer_attr="analyze_numeric_constraints",
            context_kwargs=("analyzed_target_is_library",),
            semantic_mapping_kind="framework",
            semantic_rule_source="numeric-constraints",
        ),
        AnalyzerSpecTemplate(
            key="data-dependency",
            name="Data dependency",
            description=(
                "Reports long chains of assignments and code that uses a value before it is set.\n"
                "\n"
                "Finds:\n"
                "- A chain of three or more assignments, for example 'Mid = Input; Output = Mid;'.\n"
                "- A value used before it is set in the same module, for example 'Output = Source; "
                "Source = 3;'."
            ),
            analyzer_attr="analyze_data_dependency",
            context_kwargs=("unavailable_libraries", "analyzed_target_is_library"),
            semantic_rule_source="data-dependency",
        ),
        AnalyzerSpecTemplate(
            key="config-drift",
            name="Config drift",
            description=(
                "Finds moduletype instances whose configuration settings drift across the analyzed "
                "target.\n"
                "\n"
                "When two or more instances of the same moduletype set a configuration parameter to "
                "different values, the drifting parameter is reported for the group.\n"
                "\n"
                "Example: ValveA with 'Timeout => 10' and ValveB with 'Timeout => 15' on the same "
                "DoseValve moduletype."
            ),
            analyzer_attr="analyze_config_drift",
            context_kwargs=("unavailable_libraries",),
            semantic_mapping_kind="framework",
            semantic_rule_source="config-drift",
        ),
        AnalyzerSpecTemplate(
            key="scan-loop-resource-usage",
            name="Scan-loop resource usage",
            description=(
                "Finds builtin calls that are not safe to run every scan inside continuously running "
                "code: every equation block and every SFC step's active code.\n"
                "\n"
                "Calls in one-time start or end code are not flagged. String, time, status, and system "
                "builtins are common offenders.\n"
                "\n"
                "Example: 'AssignSystemString(SysVarId, Value, Status);' inside an equation block."
            ),
            analyzer_attr="analyze_scan_loop_resource_usage",
            context_kwargs=("analyzed_target_is_library",),
        ),
        AnalyzerSpecTemplate(
            key="resource-usage",
            name="Resource usage",
            description=(
                "Tracks resource handles that are opened (OpenDevice/OpenReadFile/OpenWriteFile) and "
                "closed (CloseDevice/CloseFile) in each module.\n"
                "\n"
                "Finds:\n"
                "- Closing a handle that was never opened, for example 'CloseFile(FileRef, ...)' with no "
                "prior open.\n"
                "- Opening a handle twice before closing it, for example opening 'FileRef' twice without a "
                "close.\n"
                "- Opening a handle and never closing it, for example 'OpenReadFile(FileRef, ...)' with no "
                "CloseFile.\n"
                "- Also reports scan-loop resource hazards."
            ),
            analyzer_attr="analyze_resource_usage",
            context_kwargs=("unavailable_libraries", "analyzed_target_is_library"),
            semantic_rule_source="resource-usage",
        ),
        AnalyzerSpecTemplate(
            key="scan-concurrency",
            name="Scan concurrency",
            description=(
                "Finds parallel SFC branches that write the same variable without a rule for which one "
                "wins.\n"
                "\n"
                "A write/write conflict across two SFCParallel branches is reported as a parallel write "
                "race.\n"
                "\n"
                "Example: 'BranchLeft' and 'BranchRight' both setting 'SharedOutput' in their active code."
            ),
            analyzer_attr="analyze_scan_concurrency",
            context_kwargs=("config", "analyzed_target_is_library"),
            composed_analyzer_keys=("same-cycle",),
            composed_issue_kind_names=("sfc_parallel_write_race",),
        ),
        AnalyzerSpecTemplate(
            key="scan-shared-access",
            name="Scan shared access",
            description=(
                "Finds non-STATE variables that are read in one scan point and written in another within "
                "the same scan.\n"
                "\n"
                "Equation blocks and step active-code phases are separate scan points. Reading and "
                "writing in the same point does not trigger it.\n"
                "\n"
                "Example: 'Output = SharedValue;' in ReadEq and 'SharedValue = 2;' in WriteEq, with "
                "SharedValue not declared State."
            ),
            analyzer_attr="analyze_scan_shared_access",
            context_kwargs=("config", "analyzed_target_is_library"),
            composed_analyzer_keys=("same-cycle",),
            composed_issue_kind_names=("same_cycle_non_state_multi_site_hazard",),
        ),
        AnalyzerSpecTemplate(
            key="same-cycle",
            name="Same-cycle hazards",
            description=(
                "Finds shared-variable problems that happen in the same scan across modules and parallel "
                "SFC branches.\n"
                "\n"
                "Finds:\n"
                "- A variable read in one module and written in another in one scan, for example module "
                "Reader does 'Output = SharedValue;' while module Writer does 'SharedValue = 0;'.\n"
                "- Parallel branches where one reads and another writes the same variable.\n"
                "- Parallel branches that both write the same variable, a write race.\n"
                "- Non-STATE variables used at more than one continuous scan point."
            ),
            analyzer_attr="analyze_same_cycle",
            context_kwargs=("analysis_context", "debug", "unavailable_libraries", "analyzed_target_is_library"),
            supports_live_diagnostics=True,
            semantic_mapping_kind="framework",
            semantic_rule_source="same-cycle",
        ),
        AnalyzerSpecTemplate(
            key="timing",
            name="Timing",
            description=(
                "Finds timing problems in the scan cycle: using :OLD after a value was written in the "
                "same scan, reading without :NEW after a write, writing to :OLD, and calls that are not "
                "safe to run every scan.\n"
                "\n"
                "Combines dataflow timing checks with scan-loop resource usage.\n"
                "\n"
                "Examples: 'PrevAccum = Accum:Old;' right after 'Accum = Accum + Smoothed;', or "
                "'MaxLim(1.0, 2.0, 0.1, Flag:Old);' passing :OLD as an output."
            ),
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
            description=(
                "Finds modules with the same name that have drifted apart, beyond just a different date "
                "code.\n"
                "\n"
                "Modules with the same name (ignoring letter case) are compared. When two or more "
                "versions differ, drift in module parameters, local variables, submodule structure, or "
                "module code is reported.\n"
                "\n"
                "Example: two 'Mixer' modules whose code differs only in 'Output = 1;' versus 'Output = "
                "2;'."
            ),
            analyzer_attr="analyze_version_drift",
            category="heuristic",
            context_kwargs=("debug",),
            semantic_rule_source="version-drift",
        ),
        AnalyzerSpecTemplate(
            key="safety-paths",
            name="Safety paths",
            description=(
                "Tracks safety-critical signals (paths containing emergency, shutdown, or estop) and "
                "reports ones that are written but never read.\n"
                "\n"
                "Example: 'EmergencyShutdown = InCommand;' written inside GuardType but the path is never "
                "read anywhere."
            ),
            analyzer_attr="analyze_safety_paths",
            context_kwargs=("debug", "unavailable_libraries", "analyzed_target_is_library", "analysis_context"),
            requires=("variables",),
            semantic_mapping_kind="framework",
            semantic_rule_source="safety-paths",
        ),
        AnalyzerSpecTemplate(
            key="taint-paths",
            name="Taint paths",
            description=(
                "Tracks external MES, operator, or sensor inputs as they flow into safety-critical "
                "outputs (emergency, shutdown, estop, interlock, trip) across modules.\n"
                "\n"
                "Only paths that cross more than one module are reported. Wiring inside a single module "
                "is not flagged.\n"
                "\n"
                "Example: operator input 'Root.OperatorCommand' reaching 'Root.Guard.EmergencyShutdown' "
                "through a moduletype mapping."
            ),
            analyzer_attr="analyze_taint_paths",
            context_kwargs=("debug", "unavailable_libraries", "analyzed_target_is_library", "analysis_context"),
            requires=("variables",),
            semantic_mapping_kind="framework",
            semantic_rule_source="taint-paths",
        ),
        AnalyzerSpecTemplate(
            key="unsafe-defaults",
            name="Unsafe defaults",
            description=(
                "Flags boolean variables that start as True and whose name contains 'enable' or "
                "'bypass'.\n"
                "\n"
                "Finds:\n"
                "- 'Enable' names that can start equipment or logic on power-up, for example 'EnablePump: "
                "boolean := True;'.\n"
                "- 'Bypass' names that can turn off safety checks on power-up, for example 'SafetyBypass: "
                "boolean := True;'."
            ),
            analyzer_attr="analyze_unsafe_defaults",
            context_kwargs=("analyzed_target_is_library",),
            semantic_mapping_kind="framework",
            semantic_rule_source="unsafe-defaults",
        ),
        AnalyzerSpecTemplate(
            key="dataflow",
            name="Lightweight dataflow",
            description=(
                "Follows the code path to find values read before they are set, writes that are "
                "overwritten before they are read, conditions that are always true or false, code that "
                "can never run, and comparisons where something is compared to itself.\n"
                "\n"
                "Also checks :OLD/:NEW use on State variables. :OLD is read-only, and both markers are "
                "only allowed on State variables.\n"
                "\n"
                "Examples: 'Output = Uninitialized;' (read before set), 'Flag AND NOT Flag' (always "
                "false), or 'Flag = True; Flag = Condition;' (first write is overwritten)."
            ),
            analyzer_attr="analyze_dataflow",
            context_kwargs=("unavailable_libraries", "analyzed_target_is_library", "shared_artifacts"),
            semantic_mapping_kind="framework",
            semantic_rule_source="dataflow",
        ),
        AnalyzerSpecTemplate(
            key="state-inference",
            name="State inference",
            description=(
                "Works out the stable boolean, number, and string values on each path and reports "
                "conditions that can never be true.\n"
                "\n"
                "Finds:\n"
                "- Conditions that are always true or always false, for example with 'Count: integer := "
                "5;', 'Count < 0' can never be true.\n"
                "- Branches that can never run, for example the IF branch of that condition.\n"
                "- A summary of the values it worked out."
            ),
            analyzer_attr="analyze_state_inference",
            context_kwargs=("unavailable_libraries", "analyzed_target_is_library"),
        ),
    )


__all__ = ["AnalyzerSpecTemplate", "default_spec_templates"]
