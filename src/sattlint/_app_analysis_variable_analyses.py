from __future__ import annotations

from .analyzers.variables import IssueKind

VariableAnalysisSelection = set[IssueKind] | None
VariableAnalysisMap = dict[str, tuple[str, VariableAnalysisSelection]]

VARIABLE_ANALYSES: VariableAnalysisMap = {
    "1": ("All variable analyses (high confidence)", None),
    "2": ("Unused variables", {IssueKind.UNUSED}),
    "3": ("Unused fields in datatypes", {IssueKind.UNUSED_DATATYPE_FIELD}),
    "4": ("Read-only but not CONST", {IssueKind.READ_ONLY_NON_CONST}),
    "5": ("Written but never read", {IssueKind.NEVER_READ}),
    "6": ("Unknown parameter mapping targets", {IssueKind.UNKNOWN_PARAMETER_TARGET}),
    "7": ("String mapping type mismatches", {IssueKind.STRING_MAPPING_MISMATCH}),
    "8": ("Duplicated complex datatypes", {IssueKind.DATATYPE_DUPLICATION}),
    "9": ("Min/Max mapping name mismatches", {IssueKind.MIN_MAX_MAPPING_MISMATCH}),
    "10": ("Magic numbers", {IssueKind.MAGIC_NUMBER}),
    "11": ("Missing required parameter connections", {IssueKind.REQUIRED_PARAMETER_CONNECTION}),
    "12": ("Sorting-sensitive datatypes", {IssueKind.RECORD_COMPONENT_ORDER_DEPENDENCE}),
    "13": ("Reset contamination", {IssueKind.RESET_CONTAMINATION}),
    "14": ("Variable shadowing", {IssueKind.SHADOWING}),
    "15": ("UI/display-only variables", {IssueKind.UI_ONLY}),
    "16": ("Procedure status handling", {IssueKind.PROCEDURE_STATUS}),
    "17": ("Write-without-effect variables", {IssueKind.WRITE_WITHOUT_EFFECT}),
    "18": ("Cross-module contract mismatches", {IssueKind.CONTRACT_MISMATCH}),
    "19": ("Implicit latching", {IssueKind.IMPLICIT_LATCH}),
    "20": ("Global scope minimization", {IssueKind.GLOBAL_SCOPE_MINIMIZATION}),
    "21": ("Hidden global coupling", {IssueKind.HIDDEN_GLOBAL_COUPLING}),
    "22": ("High fan-in or fan-out variables", {IssueKind.HIGH_FAN_IN_OUT}),
    "23": ("Overlapping layout elements", {IssueKind.LAYOUT_OVERLAP}),
    "24": ("Naming-to-behavior mismatches", {IssueKind.NAMING_ROLE_MISMATCH}),
    "25": ("Name collisions", {IssueKind.NAME_COLLISION}),
}

HIGH_CONFIDENCE_VARIABLE_ANALYSIS_KEYS: tuple[str, ...] = (
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "10",
    "11",
    "12",
    "13",
    "14",
    "23",
    "25",
)

LOW_CONFIDENCE_VARIABLE_ANALYSIS_KEYS: tuple[str, ...] = (
    "24",
    "15",
    "16",
    "17",
    "18",
    "19",
    "20",
    "21",
    "22",
)
