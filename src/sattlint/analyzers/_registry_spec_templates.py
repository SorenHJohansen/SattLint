"""Declarative analyzer spec templates for the registry builder."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

type AnalyzerCategory = Literal["correctness", "heuristic", "style"]
type AnalyzerScope = Literal["per-target", "per-run"]


@dataclass(frozen=True)
class AnalyzerSpecTemplate:
    key: str
    name: str
    description: str
    analyzer_attr: str
    category: AnalyzerCategory = "correctness"
    scope: AnalyzerScope = "per-target"
    context_kwargs: tuple[str, ...] = ()
    enabled: bool = True
    direct_context: bool = False


def default_spec_templates() -> tuple[AnalyzerSpecTemplate, ...]:
    return (
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
                "- Read-only but not CONST - only read, never written, and not "
                "marked CONST.\n"
                "\n"
                "- Written but never read - written but never read.\n"
                "\n"
                "- Write without effect - written and read, but the value never "
                "reaches an output.\n"
                "  Example: 'Scaled = RawInput * 2;' then 'Temp = Scaled + 1;' - "
                "Scaled only feeds another local value.\n"
                "\n"
                "- Implicit latch - a flag is set on one path, never cleared on "
                "another.\n"
                "  Example: 'IF StartCmd THEN Running = True; ENDIF;' with no "
                "'Running = False' on the other path.\n"
                "\n"
                "- Reset contamination - a value written during normal operation "
                "is not reset on reset paths.\n"
                "  Example: a step writes 'Output', but no step clears it when "
                "ResetCmd arrives.\n"
                "\n"
                "- Read before write - a variable is read before it is written "
                "or initialized in the same scope.\n"
                "  Example: 'Output = InputSignal;' when InputSignal has no init "
                "value and is never written first.\n"
                "\n"
                "- Procedure status ignored - a procedure status output is never "
                "checked.\n"
                "  Example: 'RunHomingProcedure(HomingStatus);' and HomingStatus "
                "is never checked in logic.\n"
                "\n"
                "- Shadowing - a local variable hides a variable with the same "
                "name in an outer scope.\n"
                "  Example: a child module declares local 'Level' while a global "
                "'Level' already exists.\n"
                "\n"
                "- Unsafe default - a bypass or enable flag starts as True.\n"
                "  Example: 'SafetyBypass: boolean := True;'\n"
                "\n"
                "- Global can be localized - a global is only used in one module.\n"
                "  Example: 'SharedCount' is only touched inside PumpModule.\n"
                "\n"
                "- Hidden global coupling - modules share a global without an "
                "interface.\n"
                "  Example: 'EngineOil' is written in EngineModule and read in "
                "DisplayModule.\n"
                "\n"
                "- High fan-in/out - too many modules read or write the same "
                "root-level variable.\n"
                "  Example: 'RunningState' is read or written by more than ten "
                "modules.\n"
                "\n"
                "- Duplicated datatype - two datatypes have the same structure.\n"
                "  Example: two RECORDs with the same fields but different "
                "names.\n"
                "\n"
                "- Min/Max mapping mismatch - Min_/Max_ mappings do not match by "
                "name.\n"
                "  Example: 'MaxValue => MaxValue' is fine, but 'MinValue => "
                "MinLimit' points to a different name.\n"
                "\n"
                "- Unknown parameter target - a mapping points to a parameter "
                "that does not exist.\n"
                "  Example: 'NotDeclared => RawInput' but the type has no "
                "'NotDeclared' parameter.\n"
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
                "- Record order dependence - the meaning of a record read depends "
                "on the declared field order.\n"
                "\n"
                "Datatype-field findings move to the dedicated opt-in 'datatype-fields' analyzer."
            ),
            analyzer_attr="analyze_variables",
            context_kwargs=(
                "analysis_context",
                "debug",
                "unavailable_libraries",
                "analyzed_target_is_library",
                "include_dependency_moduletype_usage",
                "config",
            ),
        ),
        AnalyzerSpecTemplate(
            key="datatype-fields",
            name="Datatype field usage",
            description=(
                "Checks three things about RECORD fields: unused, read-only, and "
                "never-read fields.\n"
                "\n"
                "Finds:\n"
                "\n"
                "- A field no code ever touches.\n"
                "  Example: 'UnusedField' with no code path.\n"
                "\n"
                "- A field that is only read, never written.\n"
                "  Example: a received record whose 'Status' field is never "
                "written.\n"
                "\n"
                "- A field that is only written, never read back.\n"
                "  Example: dead output logic.\n"
                "\n"
                "This analyzer always loads the files that use the datatype, so "
                "it is slower than a plain 'variables' run. Because of that it "
                "is opt-in."
            ),
            analyzer_attr="analyze_datatype_fields",
            context_kwargs=(
                "analysis_context",
                "debug",
                "unavailable_libraries",
                "analyzed_target_is_library",
                "config",
            ),
        ),
        AnalyzerSpecTemplate(
            key="picture-display-paths",
            name="PictureDisplay paths",
            description=(
                "Checks that the paths used by PictureDisplay buttons point to a "
                "real screen or module.\n"
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
                "- MMS datatype mismatch - the two ends of one MMS connection "
                "use different datatypes.\n"
                "  Example: the SattLine variable is integer but the external "
                "tag is real.\n"
                "\n"
                "- Dead MMS tag - an outgoing tag is never written by the "
                "program.\n"
                "  Example: tag 'LEVEL.SENSOR' is configured but never referenced "
                "in the code."
            ),
            analyzer_attr="analyze_mms_interface_variables",
            context_kwargs=("debug", "config", "analysis_context"),
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
                "- ICF value prefix inconsistency - the file uses different single-letter "
                "prefixes on different lines.\n"
                "  Example: one line uses 'A::Program:...' and another uses "
                "'B::Program:...'.\n"
                "\n"
                "- ICF program load failed - the referenced program could not be "
                "loaded.\n"
                "  Example: an .icf file references a program that cannot be "
                "read."
            ),
            analyzer_attr="analyze_icf_configuration",
            category="correctness",
            scope="per-run",
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
                "- Unreachable sequence node - a step can never run.\n"
                "  Example: a step placed after a step that already ended the "
                "branch.\n"
                "\n"
                "- Unreachable transition - a transition can never fire.\n"
                "  Example: a transition placed after a step that already ended "
                "the branch.\n"
                "\n"
                "- Duplicate transition guard - two transitions have the same "
                "condition.\n"
                "  Example: TrA and TrB both wait for 'Ready == True'."
            ),
            analyzer_attr="analyze_sfc",
            context_kwargs=("analysis_context",),
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
                "  Example: '(* IF Running THEN Running = False; ENDIF; *)'."
            ),
            analyzer_attr="analyze_comment_code",
            category="correctness",
            direct_context=True,
        ),
        AnalyzerSpecTemplate(
            key="spec-compliance",
            name="Engineering spec compliance",
            description=(
                "Checks the code against the engineering style rules.\n"
                "\n"
                "Finds:\n"
                "\n"
                "- Transition has no name - a transition has no name.\n"
                "  Example: 'SEQTRANSITION WAIT_FOR Done'.\n"
                "\n"
                "- Wrong sequence step prefix - a step name does not start with "
                "the configured prefix (default 'ST_').\n"
                "  Example: 'SEQSTEP step_mix'.\n"
                "\n"
                "- Wrong transition prefix - a transition name does not start "
                "with the configured prefix (default 'TR_').\n"
                "  Example: 'SEQTRANSITION MyTrans'.\n"
                "\n"
                "- Wrong sequence name prefix - a sequence name does not start "
                "with the configured prefix.\n"
                "\n"
                "- Wrong equation block name prefix - an equation block name "
                "does not start with the configured prefix."
            ),
            analyzer_attr="analyze_spec_compliance",
            context_kwargs=("debug", "unavailable_libraries", "analyzed_target_is_library", "config"),
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
                "- Alarm never cleared - an alarm flag is set but never reset.\n"
                "  Example: 'TempHigh = True;' with no later 'TempHigh = "
                "False;'."
            ),
            analyzer_attr="analyze_alarm_integrity",
            context_kwargs=("debug", "unavailable_libraries", "analyzed_target_is_library"),
        ),
        AnalyzerSpecTemplate(
            key="cyclomatic-complexity",
            name="Cyclomatic complexity",
            description=(
                "Counts how many different paths the logic can take.\n"
                "\n"
                "Finds:\n"
                "\n"
                "- High module complexity - a program or module has too many "
                "paths.\n"
                "  Example: a program with 11 paths when the limit is 10.\n"
                "\n"
                "- High step complexity - an SFC step has too many paths.\n"
                "  Example: a step with many nested IF branches.\n"
                "\n"
                "- High equation block complexity - an equation block has too "
                "many paths.\n"
                "  Example: an equation block with 12 paths when the limit is 10."
            ),
            analyzer_attr="analyze_cyclomatic_complexity",
            category="style",
            context_kwargs=("analyzed_target_is_library", "config"),
        ),
        AnalyzerSpecTemplate(
            key="same-cycle",
            name="Same-cycle hazards",
            description=(
                "Checks that the same variable is not read and written at the "
                "same time in one scan cycle.\n"
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
                "- Parallel write race - two parallel branches write the same "
                "variable.\n"
                "  Example: two PARALLELSEQ branches both write 'SharedOutput'."
            ),
            analyzer_attr="analyze_same_cycle",
            context_kwargs=("analysis_context", "debug", "unavailable_libraries", "analyzed_target_is_library"),
        ),
        AnalyzerSpecTemplate(
            key="version-drift",
            name="Version drift",
            description=(
                "Checks that two module types with the same name are really the "
                "same version.\n"
                "\n"
                "Finds:\n"
                "\n"
                "- Version drift - two module types have the same name but "
                "different DateCodes.\n"
                "  Example: two 'Mixer' module types, one dated 2026-01-01 and "
                "one dated 2026-06-01."
            ),
            analyzer_attr="analyze_version_drift",
            category="correctness",
            context_kwargs=("debug",),
        ),
        AnalyzerSpecTemplate(
            key="dataflow",
            name="Dataflow",
            description=(
                "Follows the values of variables through the code step by step.\n"
                "\n"
                "Finds:\n"
                "\n"
                "- Dead overwrite - a write is replaced before its value is ever "
                "read.\n"
                "  Example: 'Flag = True; Flag = Condition;'.\n"
                "\n"
                "- Conflicting constants - the same variable gets two different "
                "constant values in one path.\n"
                "  Example: 'Setpoint = 10;' then 'Setpoint = 20;'.\n"
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
                "- Stale :OLD read - :OLD is read after the value was written in "
                "this scan, so it still means the previous scan.\n"
                "  Example: 'Counter = Counter + 1; IF Counter:Old == 0'.\n"
                "\n"
                "- Implicit :NEW read - a State value is read after a write, but "
                ":NEW is missing.\n"
                "  Example: a transition waits for 'Level == 5' after an "
                "ENTERCODE wrote 'Level = 5;'.\n"
                "\n"
                "- Non-state multi-site access - a non-State variable is read "
                "and written in more than one place in one scan.\n"
                "  Example: 'Temp' is read and written in two equation blocks in "
                "the same scan."
            ),
            analyzer_attr="analyze_dataflow",
            context_kwargs=("unavailable_libraries", "analyzed_target_is_library", "shared_artifacts"),
        ),
    )


__all__ = ["AnalyzerSpecTemplate", "default_spec_templates"]
