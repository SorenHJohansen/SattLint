"""Declarative analyzer spec templates for the registry builder."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

type AnalyzerCategory = Literal["correctness", "heuristic", "style"]


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
                "Combines all issue kinds into one analyzer. It runs the other "
                "SattLine checks, collects their issues, and removes duplicates by "
                "rule, file, and data.\n"
                "\n"
                "Finds:\n"
                "\n"
                "- Duplicate sibling name - two sibling modules have the same name.\n"
                "  Example: two 'Boiler1' invocations under the same parent.\n"
                "\n"
                "- Unexpected submodule type - a submodule is not a real module.\n"
                "  Example: a TextLabel inside a SUBMODULES block.\n"
                "\n"
                "You normally do not run this analyzer yourself. It is the surface "
                "used by the LSP server."
            ),
            analyzer_attr="analyze_sattline_semantics",
            context_kwargs=(
                "analysis_context",
                "debug",
                "unavailable_libraries",
                "analyzed_target_is_library",
                "config",
            ),
        ),
        AnalyzerSpecTemplate(
            key="variables",
            name="Variable issues",
            description=(
                "Checks every variable, datatype field, and input/output mapping "
                "in the project.\n"
                "\n"
                "Finds:\n"
                "\n"
                "- Unused variable - declared but never read or written.\n"
                "\n"
                "- Unused datatype field - a field of a record is never read or "
                "written.\n"
                "\n"
                "- Field never written - a field is only read, never set.\n"
                "\n"
                "- Read-only non-const - a variable is only read but is not CONST.\n"
                "  Example: 'SensorInput' is only read in an equation, never "
                "written.\n"
                "\n"
                "- Field never read - a field is set but never read.\n"
                "\n"
                "- Written but never read - a variable is set but never read.\n"
                "\n"
                "- Write without effect - a value never reaches an output.\n"
                "  Example: 'Scaled = RawInput * 2;' then 'Temp = Scaled + 1;' - "
                "Scaled only feeds another local value.\n"
                "\n"
                "- UI-only variable - only used by the operator interface.\n"
                "  Example: 'DisplayValue = RawInput;' and DisplayValue is only "
                "shown on a faceplate.\n"
                "\n"
                "- Implicit latch - a flag is set on one path but never cleared on "
                "another.\n"
                "  Example: 'IF StartCmd THEN Running = True; ENDIF;' with no "
                "'Running = False' on the other path.\n"
                "\n"
                "- Reset contamination - reset values are missing in a sequence.\n"
                "  Example: a step writes 'Output' but no step clears it when "
                "ResetCmd arrives.\n"
                "\n"
                "- Naming role mismatch - the name (Cmd, Status, Alarm) does not "
                "match the use.\n"
                "  Example: 'CmdRegister' is only read, never written.\n"
                "\n"
                "- Procedure status ignored - a procedure status output is not "
                "checked.\n"
                "  Example: 'RunHomingProcedure(HomingStatus);' and HomingStatus "
                "is never checked in logic.\n"
                "\n"
                "- Global can be localized - a global is only used in one module.\n"
                "  Example: 'SharedCount' is only touched inside PumpModule.\n"
                "\n"
                "- Hidden global coupling - modules share a global without an "
                "interface.\n"
                "  Example: 'EngineOil' is written in EngineModule and read in "
                "DisplayModule, with no interface between them.\n"
                "\n"
                "- High fan-in/out global - too many modules read or write the "
                "same global.\n"
                "  Example: 'RunningState' is read or written by more than ten "
                "module paths.\n"
                "\n"
                "- Duplicated datatype - two datatypes have the same structure.\n"
                "  Example: two RECORDs with the same fields but different "
                "names.\n"
                "\n"
                "- Name collision - two names differ only by letter case.\n"
                "  Example: 'PumpSpeed' and 'pumpspeed' in the same scope.\n"
                "\n"
                "- Layout overlap - modules or objects cover the same area.\n"
                "  Example: two modules placed on top of each other on a "
                "picture.\n"
                "\n"
                "- Min/Max mapping mismatch - Min_/Max_ mappings do not match by "
                "name.\n"
                "  Example: 'MaxValue => MaxValue' but 'MinValue => MinLimit'.\n"
                "\n"
                "- Unknown parameter target - a mapping points to a parameter "
                "that does not exist.\n"
                "  Example: 'NotDeclared => RawInput' but the type has no "
                "'NotDeclared' parameter.\n"
                "\n"
                "- Required parameter not connected - a needed parameter is not "
                "connected.\n"
                "  Example: a ValveType instance maps no value to its required "
                "'OpenCmd' parameter.\n"
                "\n"
                "- Contract mismatch - connected parameters have different "
                "types.\n"
                "  Example: 'SetPoint => RawCounter' where RawCounter is integer "
                "but SetPoint expects real.\n"
                "\n"
                "- String mapping mismatch - two string-like types do not match.\n"
                "  Example: 'BatchName => RawString' where RawString is string "
                "but BatchName expects identstring.\n"
                "\n"
                "- Magic number - a number is used without a name.\n"
                "  Example: 'Scaled = RawInput * 0.95 + 100.0;' - 0.95 and 100.0 "
                "have no meaning.\n"
                "\n"
                "- Record order dependence - the order of record fields is "
                "used.\n"
                "  Example: the meaning of a record read depends on the declared "
                "field order."
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
                "Checks the folder paths used by PictureDisplay switches "
                "(ComButProc_, ToggleWindow, picture display rows).\n"
                "\n"
                "Finds:\n"
                "\n"
                "- Unresolved display path - a path points to a screen or module "
                "that cannot be found in the project.\n"
                "  Example: a button that opens '+MissingPanel' when no module "
                "with that name exists."
            ),
            analyzer_attr="analyze_picture_display_paths",
            context_kwargs=("graph", "analyzed_target_is_library"),
        ),
        AnalyzerSpecTemplate(
            key="mms-interface",
            name="MMS interface mappings",
            description=(
                "Checks the MMS connections (read and write blocks) between the "
                "program and external systems.\n"
                "\n"
                "Finds:\n"
                "\n"
                "- Duplicate MMS tag - the same external tag is used more than "
                "once.\n"
                "  Example: two write blocks both send to tag 'MV_1001'.\n"
                "\n"
                "- MMS datatype mismatch - the same tag is used with different "
                "data types.\n"
                "  Example: 'MmsData => RawCounter' where RawCounter is integer "
                "but the tag expects real.\n"
                "\n"
                "- MMS naming drift - the same tag family is written in different "
                "ways.\n"
                "  Example: the local signal 'pumpSpeed' does not follow the "
                "external tag 'PUMP.SPEED'.\n"
                "\n"
                "- Dead MMS tag - an outgoing tag is never written by the "
                "program.\n"
                "  Example: tag 'LEVEL.SENSOR' is configured but never referenced "
                "in the code."
            ),
            analyzer_attr="analyze_mms_interface_variables",
            context_kwargs=("debug", "config", "analysis_context"),
            requires=("variables",),
            semantic_rule_source="mms-interface",
        ),
        AnalyzerSpecTemplate(
            key="icf",
            name="ICF configuration",
            description=(
                "Checks every .icf connection file in the project. Each entry links "
                "an external value to a path inside a program.\n"
                "\n"
                "Finds:\n"
                "\n"
                "- ICF program mismatch - the entry points to the wrong program.\n"
                "  Example: in UnitA.icf an entry references 'Program:UnitB'.\n"
                "\n"
                "- ICF unresolved path - the path does not exist in the program.\n"
                "  Example: an entry points to 'OpStart.MissingSignal.STATE_NO' "
                "which does not exist.\n"
                "\n"
                "- ICF invalid field path - the field path does not exist.\n"
                "  Example: 'Record.Nested.Nope' where 'Nope' is not a field of "
                "Record.\n"
                "\n"
                "- ICF reference case mismatch - the name uses the wrong letter "
                "case.\n"
                "  Example: a reference 'logValue' but the declared name is "
                "'LogValue'.\n"
                "\n"
                "- ICF unit tag mismatch - the unit tag does not match the "
                "unit.\n"
                "  Example: in [Unit UnitB] an entry points at 'Program:UnitA'.\n"
                "\n"
                "- ICF group tag mismatch - the group suffix is wrong.\n"
                "  Example: a group tag uses 'JournalData_Wrong' instead of "
                "'JournalData_DCStoMES'.\n"
                "\n"
                "- ICF missing journal field - a needed report field is missing.\n"
                "  Example: a journal entry has CR_ID but no OPR_ID.\n"
                "\n"
                "- ICF unit structure drift - the unit layout has changed.\n"
                "  Example: a unit changed from SingleUnit to MultiUnit layout.\n"
                "\n"
                "- ICF value prefix inconsistency - the value mixes prefix "
                "groups.\n"
                "  Example: 'AB::Program:...' mixes group A and B prefixes.\n"
                "\n"
                "- ICF program load failed - the referenced program could not be "
                "loaded.\n"
                "  Example: an .icf file references a program that cannot be "
                "read."
            ),
            analyzer_attr="analyze_icf_configuration",
            category="correctness",
            context_kwargs=("config", "debug"),
        ),
        AnalyzerSpecTemplate(
            key="sfc",
            name="SFC checks",
            description=(
                "Checks all SFC sequences (step diagrams).\n"
                "\n"
                "Finds:\n"
                "\n"
                "- Parallel write race - parallel branches write the same "
                "variable.\n"
                "  Example: two PARALLELSEQ branches both write "
                "'SharedOutput'.\n"
                "\n"
                "- Unreachable sequence node - a step can never run.\n"
                "  Example: a step placed after a branch that already stopped.\n"
                "\n"
                "- Unreachable transition - a transition can never fire.\n"
                "  Example: a transition placed after a branch that already "
                "stopped.\n"
                "\n"
                "- Transition always true - the transition condition is always "
                "true.\n"
                "  Example: 'WAIT_FOR Level <= Level'.\n"
                "\n"
                "- Transition always false - the transition condition is always "
                "false.\n"
                "  Example: 'WAIT_FOR Level < Level'.\n"
                "\n"
                "- Duplicate transition guard - two transitions have the same "
                "condition.\n"
                "  Example: TrA and TrB both wait for 'Ready == True'.\n"
                "\n"
                "- Illegal state combination - two steps that must not run "
                "together can be active at the same time.\n"
                "  Example: 'Extend' and 'Retract' can both become active.\n"
                "\n"
                "- Missing step enter write - a step does not set the values it "
                "must set when entering.\n"
                "  Example: a step reads 'StepValue' but no ENTERCODE "
                "initializes it.\n"
                "\n"
                "- Missing step exit write - a step does not clear the values it "
                "must clear when leaving.\n"
                "  Example: a step never clears a 'Mutex' variable in EXITCODE.\n"
                "\n"
                "- Step state leakage - a step reads values left behind by an "
                "earlier step.\n"
                "  Example: a step reads 'StepValue' with the value the 'Prime' "
                "step left behind."
            ),
            analyzer_attr="analyze_sfc",
            requires=("variables",),
            context_kwargs=("analysis_context",),
            semantic_mapping_kind="framework",
            semantic_rule_source="sfc",
        ),
        AnalyzerSpecTemplate(
            key="comment-code",
            name="Commented-out code",
            description=(
                "Reads the source files and looks for SattLine code hidden inside "
                "comments.\n"
                "\n"
                "Finds:\n"
                "\n"
                "- Commented-out code - a comment contains real code.\n"
                "  Example: '(* IF Running THEN Running = False; ENDIF; *)'.\n"
                "\n"
                "- Comment-code read error - a file could not be read."
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
                "Checks that a local variable does not hide (shadow) a variable "
                "with the same name in an outer scope.\n"
                "\n"
                "Finds:\n"
                "\n"
                "- Variable shadowing - a local name hides an outer or global "
                "name.\n"
                "  Example: a child module declares local 'Level' while a global "
                "'Level' already exists."
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
                "Checks the code against the engineering style rules.\n"
                "\n"
                "Finds:\n"
                "\n"
                "- Code outside a frame module - code is written outside a frame "
                "module.\n"
                "  Example: 'Output = RawInput;' written directly in a "
                "BasePicture.\n"
                "\n"
                "- Wrong sequence step prefix - a step name does not start with "
                "'ST_'.\n"
                "  Example: 'SEQSTEP step_mix'.\n"
                "\n"
                "- Transition has no name - a transition has no name.\n"
                "  Example: 'SEQTRANSITION WAIT_FOR Done'.\n"
                "\n"
                "- Wrong transition prefix - a transition name does not start "
                "with 'TR_'.\n"
                "  Example: 'SEQTRANSITION MyTrans'.\n"
                "\n"
                "- OPMessage UseSignature enabled - OPMessage turns on "
                "UseSignature.\n"
                "  Example: 'OPMessage (UseSignature => True)'.\n"
                "\n"
                "- Wrong MES_BatchControl name - an MES_BatchControl instance has "
                "the wrong name.\n"
                "  Example: an instance named 'MESBC'.\n"
                "\n"
                "- Wrong MES_BatchControl Max_TRY - Max_TRY is not the required "
                "value.\n"
                "  Example: 'MES_BatchControl (Max_TRY => 0)'.\n"
                "\n"
                "- Wrong MES_BatchControl Repeat_TRY - Repeat_TRY is not the "
                "required value.\n"
                "  Example: 'MES_BatchControl (Repeat_TRY => 0)'."
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
                "Checks the alarm blocks and the alarm flag writes.\n"
                "\n"
                "Finds:\n"
                "\n"
                "- Duplicate alarm tag - the same alarm tag is used by two "
                "alarms.\n"
                "  Example: Alarm1 and Alarm2 both use tag 'TEMP_HIGH'.\n"
                "\n"
                "- Duplicate alarm condition - two alarms use the same "
                "condition.\n"
                "  Example: Alarm2 reuses the exact condition of Alarm1.\n"
                "\n"
                "- Conflicting alarm priority - the same alarm has different "
                "priorities.\n"
                "  Example: two alarms with tag 'PRESS_HIGH', one with priority "
                "1 and one with priority 2.\n"
                "\n"
                "- Alarm never cleared - an alarm flag is set but never reset.\n"
                "  Example: 'TempHigh = True;' with no later 'TempHigh = "
                "False;'."
            ),
            analyzer_attr="analyze_alarm_integrity",
            context_kwargs=("debug", "unavailable_libraries", "analyzed_target_is_library"),
            semantic_mapping_kind="framework",
            semantic_rule_source="alarm-integrity",
        ),
        AnalyzerSpecTemplate(
            key="naming-consistency",
            name="Naming consistency",
            description=(
                "Checks that all declaration names use the same style "
                "(like FlowRate or tank_level).\n"
                "\n"
                "Finds:\n"
                "\n"
                "- Inconsistent naming style - one name does not match the most "
                "common style used for that kind of symbol.\n"
                "  Example: most variables are PascalCase (FlowRate) but one is "
                "snake_case (tank_level)."
            ),
            analyzer_attr="analyze_naming_consistency",
            category="style",
            context_kwargs=("rules", "analyzed_target_is_library"),
        ),
        AnalyzerSpecTemplate(
            key="cyclomatic-complexity",
            name="Cyclomatic complexity",
            description=(
                "Measures how many different paths (if, or, and, branches) exist in "
                "the logic.\n"
                "\n"
                "Finds:\n"
                "\n"
                "- High module complexity - a program or module has too many "
                "paths.\n"
                "  Example: a program with 11 paths when the limit is 10.\n"
                "\n"
                "- High step complexity - an SFC step has too many paths.\n"
                "  Example: a step with many nested IF branches."
            ),
            analyzer_attr="analyze_cyclomatic_complexity",
            category="style",
            context_kwargs=("analyzed_target_is_library",),
        ),
        AnalyzerSpecTemplate(
            key="parameter-drift",
            name="Parameter drift",
            description=(
                "Checks that instances of the same module type use the same "
                "parameter values.\n"
                "\n"
                "Finds:\n"
                "\n"
                "- Parameter drift - two instances of the same type resolve "
                "different literal values for the same parameter.\n"
                "  Example: PumpA uses MaxSpeed 1500 and PumpB uses MaxSpeed "
                "3500."
            ),
            analyzer_attr="analyze_parameter_drift",
            category="correctness",
            context_kwargs=("unavailable_libraries",),
        ),
        AnalyzerSpecTemplate(
            key="signal-lifecycle",
            name="Signal lifecycle",
            description=(
                "Checks that a signal is written before it is read in the same "
                "scan.\n"
                "\n"
                "Finds:\n"
                "\n"
                "- Signal read before write - a signal is read before any known "
                "write.\n"
                "  Example: 'Output = InputSignal;' when InputSignal has no init "
                "value and is never written first."
            ),
            analyzer_attr="analyze_signal_lifecycle",
            context_kwargs=("analyzed_target_is_library",),
            semantic_mapping_kind="framework",
            semantic_rule_source="signal-lifecycle",
        ),
        AnalyzerSpecTemplate(
            key="loop-stability",
            name="Conflicting setpoints",
            description=(
                "Checks that a control setpoint is not given two different values in "
                "the same logic block.\n"
                "\n"
                "Finds:\n"
                "\n"
                "- Conflicting setpoint - one variable gets two different "
                "setpoint values in the same scope.\n"
                "  Example: 'Setpoint = 10;' then 'Setpoint = 20;'."
            ),
            analyzer_attr="analyze_loop_stability",
            context_kwargs=("analyzed_target_is_library",),
            semantic_mapping_kind="framework",
            semantic_rule_source="loop-stability",
        ),
        AnalyzerSpecTemplate(
            key="numeric-constraints",
            name="Numeric constraints",
            description=(
                "Checks that assigned values stay inside the Min_/Max_ limits of "
                "the variable.\n"
                "\n"
                "Finds:\n"
                "\n"
                "- Limit violation - a value is outside the visible [Min, Max] "
                "range.\n"
                "  Example: Min_Output=0, Max_Output=10, then 'Output = 12;'."
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
                "Tracks where values come from, from start values to outputs.\n"
                "\n"
                "Finds:\n"
                "\n"
                "- Dependency path - a value moves through a long chain of "
                "variables (3 or more).\n"
                "  Example: 'A = B + 1; B = C + 1;' - A depends on C "
                "transitively.\n"
                "\n"
                "- Initialization order - a value is read before it is written.\n"
                "  Example: 'Result = Temp + 1;' when Temp is written later in "
                "the same block."
            ),
            analyzer_attr="analyze_data_dependency",
            context_kwargs=("unavailable_libraries", "analyzed_target_is_library"),
            semantic_rule_source="data-dependency",
        ),
        AnalyzerSpecTemplate(
            key="same-cycle",
            name="Same-cycle hazards",
            description=(
                "Checks that the same variable is not read and written at the same "
                "time in one scan cycle.\n"
                "\n"
                "Finds:\n"
                "\n"
                "- Same-cycle shared access - a shared variable is read and "
                "written in the same scan by different modules.\n"
                "  Example: module Reader does 'Output = SharedValue;' while "
                "module Writer does 'SharedValue = 0;'.\n"
                "\n"
                "- Parallel read/write hazard - one parallel branch reads and "
                "another writes the same variable.\n"
                "  Example: a Writer branch does 'Shared = 1;' while a Reader "
                "branch does 'Temp = Shared;'.\n"
                "\n"
                "- Non-state multi-site access - a non-State variable is used at "
                "more than one place in the scan.\n"
                "  Example: 'Temp' is read and written in two equation blocks in "
                "the same scan."
            ),
            analyzer_attr="analyze_same_cycle",
            context_kwargs=("analysis_context", "debug", "unavailable_libraries", "analyzed_target_is_library"),
            supports_live_diagnostics=True,
            semantic_mapping_kind="framework",
            semantic_rule_source="same-cycle",
        ),
        AnalyzerSpecTemplate(
            key="version-drift",
            name="Version drift",
            description=(
                "Checks that modules with the same name are really the same version.\n"
                "\n"
                "Finds:\n"
                "\n"
                "- Version drift - two modules with the same name have different "
                "internal structure.\n"
                "  Example: two 'Mixer' modules identical except 'Output = 1;' "
                "vs 'Output = 2;'."
            ),
            analyzer_attr="analyze_version_drift",
            category="correctness",
            context_kwargs=("debug",),
            semantic_rule_source="version-drift",
        ),
        AnalyzerSpecTemplate(
            key="unsafe-defaults",
            name="Unsafe defaults",
            description=(
                "Checks that no safety-relevant flag starts its life as True.\n"
                "\n"
                "Finds:\n"
                "\n"
                "- Unsafe boolean default - a bypass or enable flag defaults to "
                "True at startup.\n"
                "  Example: 'SafetyBypass: boolean := True;'."
            ),
            analyzer_attr="analyze_unsafe_defaults",
            context_kwargs=("analyzed_target_is_library",),
            semantic_mapping_kind="framework",
            semantic_rule_source="unsafe-defaults",
        ),
        AnalyzerSpecTemplate(
            key="dataflow",
            name="Dataflow",
            description=(
                "Follows the values of variables through the code step by step.\n"
                "\n"
                "Finds:\n"
                "\n"
                "- Dead overwrite - a write is replaced before it is ever read.\n"
                "  Example: 'Flag = True; Flag = Condition;'.\n"
                "\n"
                "- Condition always true - a condition is always true.\n"
                "  Example: 'IF RawInput >= 0 OR RawInput < 0'.\n"
                "\n"
                "- Condition always false - a condition is always false.\n"
                "  Example: 'IF RawInput < RawInput'.\n"
                "\n"
                "- Unreachable branch - a branch can never run.\n"
                "  Example: 'IF Level > 100 AND Level < 50'.\n"
                "\n"
                "- Self-compare condition - a variable is compared with itself.\n"
                "  Example: 'IF RawInput == RawInput'.\n"
                "\n"
                "- Stale :OLD read - :OLD is read although the value was written "
                "in this scan.\n"
                "  Example: 'Counter = Counter + 1; IF Counter:Old == 0'.\n"
                "\n"
                "- Implicit :NEW read - a State value is read without :NEW after "
                "a write.\n"
                "  Example: a transition waits for 'Level == 5' after an "
                "ENTERCODE wrote 'Level = 5;'.\n"
                "\n"
                "- :OLD misuse - :OLD is used as a write target.\n"
                "  Example: 'Counter:Old = 0;'.\n"
                "\n"
                "- Invalid state access - :OLD or :NEW is used on a variable that "
                "is not State.\n"
                "  Example: 'Counter:Old' where Counter is a plain variable."
            ),
            analyzer_attr="analyze_dataflow",
            context_kwargs=("unavailable_libraries", "analyzed_target_is_library", "shared_artifacts"),
            semantic_mapping_kind="framework",
            semantic_rule_source="dataflow",
        ),
    )


__all__ = ["AnalyzerSpecTemplate", "default_spec_templates"]
