"""Semantic rule declarations (variable/framework/spec/rule registries)."""

from __future__ import annotations

from ..reporting.variables_report import IssueKind
from ._sattline_semantic_models import SemanticRule
from ._sattline_semantic_rules_more_data import (
    DATAFLOW_RULES,
    SPEC_RULE_DESCRIPTIONS,
    SPEC_RULE_EXAMPLES,
    SPEC_RULE_NAMES,
)

VARIABLE_RULES: dict[IssueKind, SemanticRule] = {
    IssueKind.UNUSED: SemanticRule(
        id="semantic.unused-variable",
        source="variables",
        description="Declared variables that are never read or written.",
        name="Unused variable",
        example="LOCALVARIABLES\n   Spare: integer := 0;  (* declared but never used *)",
    ),
    IssueKind.UNUSED_DATATYPE_FIELD: SemanticRule(
        id="semantic.unused-datatype-field",
        source="variables",
        description="Datatype fields that are never used across the analyzed target.",
        name="Unused datatype field",
        example="TYPEDEFINITIONS\n   SensorType = RECORD DateCode_ 1\n      UsedField: real := 0.0;\n      SpareField: real := 0.0;  (* never accessed *)",
    ),
    IssueKind.FIELD_READ_ONLY: SemanticRule(
        id="semantic.read-only-datatype-field",
        source="variables",
        description="Datatype fields that are read but never written for a specific variable instance.",
        name="Field never written",
        example=(
            "TYPEDEFINITIONS\n"
            "   ConfigType = RECORD DateCode_ 1\n"
            "      Mode: integer := 0;\n"
            "   ENDDEF (*ConfigType*);\n"
            "ModuleCode\n"
            "   Active = Config.Mode + 1;  (* Mode is read but never written *)"
        ),
    ),
    IssueKind.READ_ONLY_NON_CONST: SemanticRule(
        id="semantic.read-only-non-const",
        source="variables",
        description="Writable declarations that are only ever read.",
        name="Read-only non-const",
        example="LOCALVARIABLES\n   SensorInput: integer := 0;  (* writable but never assigned *)\nModuleCode\n   DisplayValue = SensorInput + 1;",
    ),
    IssueKind.PROCEDURE_STATUS: SemanticRule(
        id="semantic.procedure-status-handling",
        source="variables",
        description="Procedure status outputs should be checked in control logic instead of being ignored or shown only in UI.",
        name="Procedure status ignored",
        example="RunHomingProcedure(HomingStatus);  (* HomingStatus is a status output *)\n(* HomingStatus is only shown on the display, never checked in logic *)",
    ),
    IssueKind.FIELD_NEVER_READ: SemanticRule(
        id="semantic.never-read-datatype-field",
        source="variables",
        description="Datatype fields that are written but never subsequently read for a specific variable instance.",
        name="Field never read",
        example="TYPEDEFINITIONS\n   ConfigType = RECORD DateCode_ 1\n      Mode: integer := 0;\n   ENDDEF (*ConfigType*);\nModuleCode\n   Config.Mode = 2;  (* written but never read *)",
    ),
    IssueKind.NEVER_READ: SemanticRule(
        id="semantic.never-read-write",
        source="variables",
        description="Variables that are written but never subsequently read.",
        name="Written but never read",
        example="LOCALVARIABLES\n   Result: integer := 0;\nModuleCode\n   Result = RawInput * 2;  (* written, then never read *)",
    ),
    IssueKind.WRITE_WITHOUT_EFFECT: SemanticRule(
        id="semantic.write-without-effect",
        source="variables",
        description="Variables whose written values are read internally but never reach a root-visible output.",
        name="Write without effect",
        example="LOCALVARIABLES\n   Scaled: integer := 0;\nModuleCode\n   Scaled = RawInput * 2;  (* Scaled is written ... *)\n   Temp = Scaled + 1;      (* ... only feeds another local value *)",
    ),
    IssueKind.GLOBAL_SCOPE_MINIMIZATION: SemanticRule(
        id="semantic.global-scope-minimization",
        source="variables",
        description="Root globals whose access never escapes a single module subtree and can be localized.",
        name="Global can be localized",
        example="GLOBALVARIABLES\n   SharedCount: integer := 0;\nModuleCode\n   (* SharedCount is only touched inside PumpModule *)",
    ),
    IssueKind.HIDDEN_GLOBAL_COUPLING: SemanticRule(
        id="semantic.hidden-global-coupling",
        source="variables",
        description="Root globals that act as implicit interfaces across multiple module paths.",
        name="Hidden global coupling",
        example="GLOBALVARIABLES\n   EngineOil: integer := 0;\nModuleCode\n   (* EngineOil is written in EngineModule and read in DisplayModule\n      without any explicit interface between them *)",
    ),
    IssueKind.HIGH_FAN_IN_OUT: SemanticRule(
        id="semantic.high-fan-in-out-variable",
        source="variables",
        description="Root globals that are read or written by many distinct module paths and become highly shared coordination points.",
        name="High fan-in/out global",
        example="GLOBALVARIABLES\n   RunningState: integer := 0;\n   (* RunningState is read or written by more than ten module paths *)",
    ),
    IssueKind.UNKNOWN_PARAMETER_TARGET: SemanticRule(
        id="semantic.unknown-parameter-target",
        source="variables",
        description="Parameter mappings that target undeclared module parameters.",
        name="Unknown parameter target",
        example="SUBMODULES\n   Boiler Invocation\n      ( 0.0, 0.0, 0.0, 0.3, 0.3 ) : BoilerType (\n      NotDeclared => RawInput);  (* BoilerType has no parameter NotDeclared *)",
    ),
    IssueKind.STRING_MAPPING_MISMATCH: SemanticRule(
        id="semantic.string-mapping-mismatch",
        source="variables",
        description="Parameter mappings whose string-like datatypes are incompatible.",
        name="String mapping mismatch",
        example="SUBMODULES\n   Recipe Invocation\n      ( 0.0, 0.0, 0.0, 0.3, 0.3 ) : RecipeType (\n      BatchName => RawString);  (* RawString is string, BatchName expects identstring *)",
    ),
    IssueKind.DATATYPE_DUPLICATION: SemanticRule(
        id="semantic.duplicated-datatype-layout",
        source="variables",
        description="Complex datatypes that appear duplicated by structure.",
        name="Duplicated datatype",
        example="TYPEDEFINITIONS\n   ValveData = RECORD DateCode_ 1\n      Open: boolean := False;\n      Position: integer := 0;\n   ENDDEF (*ValveData*);\n   ValveDataClone = RECORD DateCode_ 1  (* same layout under a second name *)\n      Open: boolean := False;\n      Position: integer := 0;\n   ENDDEF (*ValveDataClone*);",
    ),
    IssueKind.MIN_MAX_MAPPING_MISMATCH: SemanticRule(
        id="semantic.min-max-mapping-mismatch",
        source="variables",
        description="Min_/Max_ parameter mappings that do not line up by base name.",
        name="Min/Max mapping mismatch",
        example="SUBMODULES\n   PIDCtrl Invocation\n      ( 0.0, 0.0, 0.0, 0.3, 0.3 ) : PIDType (\n      MaxValue => MaxValue,\n      MinValue => MinLimit);  (* base names MaxValue and MinLimit differ *)",
    ),
    IssueKind.SHADOWING: SemanticRule(
        id="semantic.shadowing",
        source="variables",
        description="Local declarations that shadow outer or global names.",
        name="Variable shadowing",
        example="GLOBALVARIABLES\n   Level: real := 0.0;\nBasePicture One\nLOCALVARIABLES\n   Level: real := 0.0;   (* hides the global Level inside this module *)\nModuleCode\n   Level = RawInput;     (* writes the local, not the global *)",
    ),
    IssueKind.UNSAFE_BOOLEAN_DEFAULT: SemanticRule(
        id="semantic.unsafe-default-true",
        source="variables",
        description="Boolean defaults that enable logic or bypass safeguards from startup.",
        name="Unsafe boolean default",
        example="LOCALVARIABLES\n   SafetyBypass: boolean := True;   (* safety bypass active from startup *)",
    ),
    IssueKind.READ_BEFORE_WRITE: SemanticRule(
        id="semantic.read-before-write",
        source="variables",
        description="A local value consumed before any known write in the same scope can depend on undefined startup state or scan order.",
        name="Read before write",
        example="LOCALVARIABLES\n   Temp: integer;   (* no init value *)\nModuleCode\n   Result = Temp + 1;   (* Temp is read before any write in this scope *)\n   Temp = RawInput;",
    ),
    IssueKind.RESET_CONTAMINATION: SemanticRule(
        id="semantic.reset-contamination",
        source="variables",
        description="Reset-state writes that are missing or incomplete across sequence flow.",
        name="Reset contamination",
        example="SEQUENCE MainSeq (SeqControl, SeqTimer) COORD 0.0, 0.0 OBJSIZE 1.0, 1.0\n   SEQINITSTEP Init\n   SEQTRANSITION TrRun WAIT_FOR StartCmd\n   SEQSTEP Run\n      ACTIVECODE\n         Output = Level;    (* Output written in Run step *)\n   SEQTRANSITION TrReset WAIT_FOR StopCmd\n   (* no step clears Output when ResetCmd arrives *)",
    ),
    IssueKind.IMPLICIT_LATCH: SemanticRule(
        id="semantic.implicit-latch",
        source="variables",
        description="Boolean values that are set on some branches or steps without a matching False write on the complementary path.",
        name="Implicit latch",
        example="IF StartCmd == True THEN\n   Running = True;     (* set only on this branch *)\nENDIF;\n(* no Running = False write on the other path *)",
    ),
    IssueKind.MAGIC_NUMBER: SemanticRule(
        id="semantic.magic-number",
        source="variables",
        description="Raw numeric literals used directly in assignments instead of a named constant.",
        name="Magic number",
        example="ModuleCode\n   Scaled = RawInput * 0.95 + 100.0;  (* 0.95 and 100.0 have no named meaning *)\n   HoursElapsed = ElapsedSeconds / 3600;",
    ),
    IssueKind.RECORD_COMPONENT_ORDER_DEPENDENCE: SemanticRule(
        id="semantic.record-component-order-dependence",
        source="variables",
        description="Record component reads or writes whose meaning depends on field declaration order.",
        name="Record order dependence",
        example="TYPEDEFINITIONS\n   Payload = RECORD DateCode_ 1\n      First: integer := 0;\n      Second: integer := 0;\n   ENDDEF (*Payload*);\nModuleCode\n   Data.Second = Data.First;  (* the meaning depends on the declared field order *)",
    ),
}

SFC_RULES: dict[str, SemanticRule] = {
    "sfc_unreachable_sequence_node": SemanticRule(
        id="semantic.unreachable-sequence-node",
        source="sfc",
        description="Sequence nodes that cannot execute because an earlier node terminates the branch.",
        name="Unreachable sequence node",
        example="SEQTRANSITION TrError WAIT_FOR Fault\n   SEQSTEP Stop          (* terminates the branch *)\n   SEQSTEP NeverReached  (* cannot run: the branch already stopped *)",
    ),
    "sfc_unreachable_transition": SemanticRule(
        id="semantic.unreachable-transition",
        source="sfc",
        description="Transitions that can never fire because an earlier node structurally terminates the branch.",
        name="Unreachable transition",
        example="SEQSTEP Stopping\n   SEQTRANSITION TrAfterStop WAIT_FOR True  (* never reached: branch already stopped *)",
    ),
    "sfc_duplicate_transition_guard": SemanticRule(
        id="semantic.duplicate-transition-guard",
        source="sfc",
        description="Transitions in the same sequence branch that normalize to the same guard logic.",
        name="Duplicate transition guard",
        example="SEQTRANSITION TrA WAIT_FOR Ready == True\n   SEQSTEP StepA\nSEQTRANSITION TrB WAIT_FOR Ready == True  (* same guard as TrA *)",
    ),
}

SAME_CYCLE_RULES: dict[str, SemanticRule] = {
    "same_cycle_parallel_read_write_hazard": SemanticRule(
        id="semantic.parallel-read-write-hazard",
        source="same-cycle",
        description="Parallel SFC branches that both read and write the same variable within one scan.",
        name="Parallel read/write hazard",
        example="PARALLELSEQ\n   SEQSTEP Writer\n      ACTIVECODE\n         Shared = 1;\n   PARALLELBRANCH\n   SEQSTEP Reader\n      ACTIVECODE\n         Temp = Shared;\nENDPARALLEL",
    ),
    "sfc_parallel_write_race": SemanticRule(
        id="semantic.parallel-write-race",
        source="same-cycle",
        description="Parallel SFC branches that write to the same variable or field.",
        name="Parallel write race",
        example="PARALLELSEQ\n   SEQSTEP Left\n      ACTIVECODE\n         SharedOutput = 1;\n   PARALLELBRANCH\n   SEQSTEP Right\n      ACTIVECODE\n         SharedOutput = 2;\nENDPARALLEL",
    ),
    "same_cycle_shared_access_hazard": SemanticRule(
        id="semantic.same-cycle-shared-access",
        source="same-cycle",
        description="Shared variables that are read and written across multiple module paths within the same scan.",
        name="Same-cycle shared access",
        example="GLOBALVARIABLES\n   SharedMode: integer := 0;\nModuleCode\n   (* SharedMode is written in module A and read in module B in one scan cycle *)",
    ),
}

ALARM_RULES: dict[str, SemanticRule] = {
    "alarm.duplicate_tag": SemanticRule(
        id="semantic.duplicate-alarm-tag",
        source="alarm-integrity",
        description="Alarm sources should not reuse the same tag across the analyzed target.",
        name="Duplicate alarm tag",
        example='SUBMODULES\n   Alarm1 Invocation\n      ( 0.0, 0.0, 0.0, 0.4, 0.4 ) : EventDetector1 (Tag => "TEMP_HIGH");\n   Alarm2 Invocation  (* same tag as Alarm1 *)\n      ( 0.5, 0.0, 0.0, 0.4, 0.4 ) : EventDetector1 (Tag => "TEMP_HIGH");',
    ),
    "alarm.duplicate_condition": SemanticRule(
        id="semantic.duplicate-alarm-condition",
        source="alarm-integrity",
        description="Alarm sources should not reuse the same condition without deliberate deduplication.",
        name="Duplicate alarm condition",
        example='SUBMODULES\n   Alarm1 Invocation\n      ( 0.0, 0.0, 0.0, 0.4, 0.4 ) : EventDetector1 (Tag => "TEMP_HIGH", Condition => TempHigh);\n   Alarm2 Invocation\n      ( 0.5, 0.0, 0.0, 0.4, 0.4 ) : EventDetector1 (Tag => "TEMP_LOW", Condition => TempHigh);\n   (* Alarm2 reuses the exact condition of Alarm1 *)',
    ),
    "alarm.never_cleared": SemanticRule(
        id="semantic.never-cleared-alarm",
        source="alarm-integrity",
        description="Alarm variables that are only forced true and never explicitly cleared can latch unexpectedly.",
        name="Alarm never cleared",
        example="ModuleCode\n   TempHigh = True;   (* alarm condition forced true ... *)\n   (* ... but nothing ever writes TempHigh = False to clear it *)",
    ),
}

TRACE_RULES: dict[str, SemanticRule] = {
    "duplicate_sibling_name": SemanticRule(
        id="semantic.duplicate-sibling-name",
        source="tracing",
        description="Sibling modules with the same case-insensitive name.",
        name="Duplicate sibling name",
        example="SUBMODULES\n   Boiler1 Invocation\n      ( 0.0, 0.0, 0.0, 0.4, 0.4 ) : BoilerType\n   Boiler1 Invocation  (* same name twice under the same parent *)\n      ( 0.5, 0.0, 0.0, 0.4, 0.4 ) : BoilerType",
    ),
    "unexpected_submodule_type": SemanticRule(
        id="semantic.unexpected-submodule-type",
        source="tracing",
        description="Unexpected non-module nodes under the submodule tree.",
        name="Unexpected submodule type",
        example="SUBMODULES\n   PumpA Invocation\n      ( 0.0, 0.0, 0.0, 0.4, 0.4 ) : PumpType\n   TextLabel Annot  (* annotation node is not a valid submodule here *)",
    ),
}


__all__ = [
    "ALARM_RULES",
    "DATAFLOW_RULES",
    "SFC_RULES",
    "SPEC_RULE_DESCRIPTIONS",
    "SPEC_RULE_EXAMPLES",
    "SPEC_RULE_NAMES",
    "TRACE_RULES",
    "VARIABLE_RULES",
]
