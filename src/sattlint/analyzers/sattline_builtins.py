# sattline_builtins.py
from dataclasses import dataclass
from typing import Literal
"""
Abbreviations in this list

PS       allowed in precision scangroup

Type of direction
in       input of a variable, a literal value or an expression
in var   input of a variable
out      output of a variable
inout    in- and output of a variable

Sorting
RS       labelled for reading and sorting
WS       labelled for writing and sorting
RS/WS    labelled for reading, writing and sorting
NoS      labelled for no sorting

Ownership
RO       labelled for reading and ownership
WO       labelled for writing and ownership
RO/WO    labelled for reading, writing and ownership
NoO      labelled as no ownership
"""
@dataclass
class Parameter:
    name: str
    datatype: str
    direction: Literal["in", "in var", "out", "inout"]
    sorting: Literal["RS", "WS", "RS/WS", "NoS"]
    ownership: Literal["RO", "WO", "RO/WO", "NoO"]

@dataclass
class BuiltinFunction:
    name: str
    type: Literal["Function", "Procedure"]
    return_type: str | None
    parameters: list[Parameter]
    precision_scangroup: bool  # (PS) flag

# Define all built-ins
SATTLINE_BUILTINS: dict[str, BuiltinFunction] = {
    "abs": BuiltinFunction(
        name="abs",
        type="Function",
        return_type="AnyType",
        parameters=[
            Parameter(name="Argument", datatype="AnyType", direction="in", sorting="RS", ownership="RO")
        ],
        precision_scangroup=True
    ),
    "acof1": BuiltinFunction(
        name="acof1",
        type="Function",
        return_type="Boolean",
        parameters=[
            Parameter(name="Acof", datatype="AcofType", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="OO", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="OC", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="O", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="C", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Time", datatype="Duration", direction="in var", sorting="RS", ownership="RO")
        ],
        precision_scangroup=True
    ),
    "acof2": BuiltinFunction(
        name="acof2",
        type="Function",
        return_type="Boolean",
        parameters=[
            Parameter(name="Acof", datatype="AcofType", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="OO", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="O", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="C", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Time", datatype="Duration", direction="in var", sorting="RS", ownership="RO")
        ],
        precision_scangroup=True
    ),
    "acof3": BuiltinFunction(
        name="acof3",
        type="Function",
        return_type="Boolean",
        parameters=[
            Parameter(name="Acof", datatype="AcofType", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="OO", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="O", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Time", datatype="Duration", direction="in var", sorting="RS", ownership="RO")
        ],
        precision_scangroup=True
    ),
    "acof4": BuiltinFunction(
        name="acof4",
        type="Function",
        return_type="Boolean",
        parameters=[
            Parameter(name="Acof", datatype="AcofType", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="OO", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="OH", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="O", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="C", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Time", datatype="Duration", direction="in var", sorting="RS", ownership="RO")
        ],
        precision_scangroup=True
    ),
    "acof5": BuiltinFunction(
        name="acof5",
        type="Function",
        return_type="Boolean",
        parameters=[
            Parameter(name="Acof", datatype="AcofType", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="OO", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="C", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Time", datatype="Duration", direction="in var", sorting="RS", ownership="RO")
        ],
        precision_scangroup=True
    ),
    "acof8": BuiltinFunction(
        name="acof8",
        type="Function",
        return_type="Boolean",
        parameters=[
            Parameter(name="Acof", datatype="AcofType", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="OO", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="OC", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="O", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Time", datatype="Duration", direction="in var", sorting="RS", ownership="RO")
        ],
        precision_scangroup=True
    ),
    "acof9": BuiltinFunction(
        name="acof9",
        type="Function",
        return_type="Boolean",
        parameters=[
            Parameter(name="Acof", datatype="AcofType", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="OO", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="OC", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="C", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Time", datatype="Duration", direction="in var", sorting="RS", ownership="RO")
        ],
        precision_scangroup=True
    ),
    "adddurations": BuiltinFunction(
        name="adddurations",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Duration", datatype="Duration", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Duration", datatype="Duration", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="DurationSum", datatype="Duration", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=True
    ),
    "addtimeandduration": BuiltinFunction(
        name="addtimeandduration",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Time", datatype="Time", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Duration", datatype="Duration", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Time", datatype="Time", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=True
    ),
    "arctan": BuiltinFunction(
        name="arctan",
        type="Function",
        return_type="Real",
        parameters=[
            Parameter(name="Argument", datatype="Real", direction="in", sorting="RS", ownership="RO")
        ],
        precision_scangroup=True
    ),
    "asciirecordtostring": BuiltinFunction(
        name="asciirecordtostring",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="IntegerRecord", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="NoOfCharacters", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="NoOfCharsPerInteger", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="String", datatype="String", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "assignsystemboolean": BuiltinFunction(
        name="assignsystemboolean",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="SysVarId", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="SystemVarBoolVal", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "assignsysteminteger": BuiltinFunction(
        name="assignsysteminteger",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="SysVarId", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="SystemVarIntVal", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "assignsystemreal": BuiltinFunction(
        name="assignsystemreal",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="SysVarId", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="SystemVarRealVal", datatype="Real", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "assignsystemstring": BuiltinFunction(
        name="assignsystemstring",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="SysVarId", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="SystemVarStringVal", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "bcdtointeger": BuiltinFunction(
        name="bcdtointeger",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="BCD", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Int", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=True
    ),
    "boolean16tointeger": BuiltinFunction(
        name="boolean16tointeger",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="BooleanRecord", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Int", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=True
    ),
    "boolean32tointeger": BuiltinFunction(
        name="boolean32tointeger",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="BooleanRecord", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Int", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=True
    ),
    "checksum": BuiltinFunction(
        name="checksum",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Data", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="StartPos", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="StopPos", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Type", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Result", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "clearqueue": BuiltinFunction(
        name="clearqueue",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Queue", datatype="QueueObject", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "clearstring": BuiltinFunction(
        name="clearstring",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="String", datatype="String", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "closedevice": BuiltinFunction(
        name="closedevice",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="DeviceRef", datatype="tObject", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "closefile": BuiltinFunction(
        name="closefile",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="FileRef", datatype="tObject", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "comlidial": BuiltinFunction(
        name="comlidial",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="ComliMaster", datatype="tObject", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="TelePhoneNo", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "comlihangup": BuiltinFunction(
        name="comlihangup",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="ComliMaster", datatype="tObject", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "concatenate": BuiltinFunction(
        name="concatenate",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="String1", datatype="String", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="String2", datatype="String", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Result", datatype="String", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "copyduration": BuiltinFunction(
        name="copyduration",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Source", datatype="Duration", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Destination", datatype="Duration", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=True
    ),
    "copystring": BuiltinFunction(
        name="copystring",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Source", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Destination", datatype="String", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=True
    ),
    "copystringnosort": BuiltinFunction(
        name="copystringnosort",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Source", datatype="String", direction="in var", sorting="NoS", ownership="RO"),
            Parameter(name="Destination", datatype="String", direction="out", sorting="NoS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=True
    ),
    "copytime": BuiltinFunction(
        name="copytime",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Source", datatype="Time", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Destination", datatype="Time", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=True
    ),
    "copyvariable": BuiltinFunction(
        name="copyvariable",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Source", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Destination", datatype="AnyType", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=True
    ),
    "copyvarnosort": BuiltinFunction(
        name="copyvarnosort",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Source", datatype="AnyType", direction="in var", sorting="NoS", ownership="RO"),
            Parameter(name="Destination", datatype="AnyType", direction="out", sorting="NoS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=True
    ),
    "cos": BuiltinFunction(
        name="cos",
        type="Function",
        return_type="Real",
        parameters=[
            Parameter(name="Argument", datatype="Real", direction="in", sorting="RS", ownership="RO")
        ],
        precision_scangroup=True
    ),
    "createarray": BuiltinFunction(
        name="createarray",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Array", datatype="ArrayObject", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="FirstIndex", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="LastIndex", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="ArrayElement", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "createdevice": BuiltinFunction(
        name="createdevice",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Device", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "createqueue": BuiltinFunction(
        name="createqueue",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Queue", datatype="QueueObject", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Size", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="QueueElement", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "createwritefile": BuiltinFunction(
        name="createwritefile",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="FileRef", datatype="tObject", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="FileName", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "currentqueuesize": BuiltinFunction(
        name="currentqueuesize",
        type="Function",
        return_type="Integer",
        parameters=[
            Parameter(name="Queue", datatype="QueueObject", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "currentuser": BuiltinFunction(
        name="currentuser",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="UserName", datatype="String", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="UserClassName", datatype="String", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "cutstring": BuiltinFunction(
        name="cutstring",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="String", datatype="String", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Length", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "definestaticrouting": BuiltinFunction(
        name="definestaticrouting",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="RedundantRoutingInfo", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="RemoteSystem", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="LocalPort", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="PortInNextSystem", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "deletearray": BuiltinFunction(
        name="deletearray",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Array", datatype="ArrayObject", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "deleteeditfile": BuiltinFunction(
        name="deleteeditfile",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="FileName", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "deletefile": BuiltinFunction(
        name="deletefile",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="FileName", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "deletequeue": BuiltinFunction(
        name="deletequeue",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Queue", datatype="QueueObject", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "deletewindow": BuiltinFunction(
        name="deletewindow",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="ModulePath", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="SelectClass", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "durationgreaterthan": BuiltinFunction(
        name="durationgreaterthan",
        type="Function",
        return_type="Boolean",
        parameters=[
            Parameter(name="Duration", datatype="Duration", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Duration", datatype="Duration", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=True
    ),
    "durationtodurrec": BuiltinFunction(
        name="durationtodurrec",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Duration", datatype="Duration", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="DurationRecord", datatype="DurationRecord", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=True
    ),
    "durationtostring": BuiltinFunction(
        name="durationtostring",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Duration", datatype="Duration", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="DurationString", datatype="String", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "durrectoduration": BuiltinFunction(
        name="durrectoduration",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="DurationRecord", datatype="DurationRecord", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Duration", datatype="Duration", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=True
    ),
    "elapsed": BuiltinFunction(
        name="elapsed",
        type="Function",
        return_type="Integer",
        parameters=[
            Parameter(name="Timer", datatype="Timer", direction="in var", sorting="RS", ownership="RO")
        ],
        precision_scangroup=True
    ),
    "equal": BuiltinFunction(
        name="equal",
        type="Function",
        return_type="Boolean",
        parameters=[
            Parameter(name="Variable", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Variable", datatype="AnyType", direction="in var", sorting="RS", ownership="RO")
        ],
        precision_scangroup=True
    ),
    "equalstrings": BuiltinFunction(
        name="equalstrings",
        type="Function",
        return_type="Boolean",
        parameters=[
            Parameter(name="String1", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="String2", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="CaseSensitive", datatype="Boolean", direction="in", sorting="RS", ownership="RO")
        ],
        precision_scangroup=True
    ),
    "equalvariables": BuiltinFunction(
        name="equalvariables",
        type="Function",
        return_type="Boolean",
        parameters=[
            Parameter(name="Variable", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Variable", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=True
    ),
    "exp": BuiltinFunction(
        name="exp",
        type="Function",
        return_type="Real",
        parameters=[
            Parameter(name="Argument", datatype="Real", direction="in", sorting="RS", ownership="RO")
        ],
        precision_scangroup=True
    ),
    "extractstring": BuiltinFunction(
        name="extractstring",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="String", datatype="String", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="String2", datatype="String", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Length", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "fdurationtostring": BuiltinFunction(
        name="fdurationtostring",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Duration", datatype="Duration", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="DurationFormat", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="DurationString", datatype="String", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "fileexists": BuiltinFunction(
        name="fileexists",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="FileName", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "getarray": BuiltinFunction(
        name="getarray",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Array", datatype="ArrayObject", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Index", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="ArrayElement", datatype="AnyType", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "getascii": BuiltinFunction(
        name="getascii",
        type="Function",
        return_type="Integer",
        parameters=[
            Parameter(name="Str", datatype="String", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "getfirstqueue": BuiltinFunction(
        name="getfirstqueue",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Queue", datatype="QueueObject", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="QueueElement", datatype="AnyType", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "getlastqueue": BuiltinFunction(
        name="getlastqueue",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Queue", datatype="QueueObject", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="QueueElement", datatype="AnyType", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "getrecordcompnosort": BuiltinFunction(
        name="getrecordcompnosort",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Rec", datatype="AnyType", direction="in var", sorting="NoS", ownership="RO"),
            Parameter(name="ComponentIndex", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="ResultRec", datatype="AnyType", direction="out", sorting="NoS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="NoS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "getrecordcomponent": BuiltinFunction(
        name="getrecordcomponent",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Rec", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="ComponentIndex", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="ResultRec", datatype="AnyType", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "getremotefile": BuiltinFunction(
        name="getremotefile",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="RemoteSystemIdentity", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="RemoteFileName", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="LocalFileName", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "getremotesinglefile": BuiltinFunction(
        name="getremotesinglefile",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="RemoteSystemIdentity", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="RemoteFileName", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="LocalFileName", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "getstringpos": BuiltinFunction(
        name="getstringpos",
        type="Function",
        return_type="Integer",
        parameters=[
            Parameter(name="String", datatype="String", direction="inout", sorting="NoS", ownership="NoO")
        ],
        precision_scangroup=False
    ),
    "getsystemtype": BuiltinFunction(
        name="getsystemtype",
        type="Function",
        return_type="Integer",
        parameters=[],
        precision_scangroup=False
    ),
    "gettime": BuiltinFunction(
        name="gettime",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Time", datatype="Time", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=True
    ),
    "getuserfullname": BuiltinFunction(
        name="getuserfullname",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="UserName", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="FullName", datatype="String", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "getuseridletime": BuiltinFunction(
        name="getuseridletime",
        type="Function",
        return_type="Integer",
        parameters=[],
        precision_scangroup=False
    ),
    "graycodetointeger": BuiltinFunction(
        name="graycodetointeger",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="BooleanRecord", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Int", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=True
    ),
    "initvariable": BuiltinFunction(
        name="initvariable",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Rec", datatype="AnyType", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="InitRec", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "insertarray": BuiltinFunction(
        name="insertarray",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Array", datatype="ArrayObject", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Index", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="ArrayElement", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "insertascii": BuiltinFunction(
        name="insertascii",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="ASCII", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Str", datatype="String", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "insertstring": BuiltinFunction(
        name="insertstring",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="String", datatype="String", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="String2", datatype="String", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Length", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "integertobcd": BuiltinFunction(
        name="integertobcd",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Int", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="BCD", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=True
    ),
    "integertoboolean16": BuiltinFunction(
        name="integertoboolean16",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Int", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="BooleanRecord", datatype="AnyType", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=True
    ),
    "integertoboolean32": BuiltinFunction(
        name="integertoboolean32",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Int", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="BooleanRecord", datatype="AnyType", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=True
    ),
    "integertograycode": BuiltinFunction(
        name="integertograycode",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Int", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="BooleanRecord", datatype="AnyType", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=True
    ),
    "integertooctalstring": BuiltinFunction(
        name="integertooctalstring",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="String", datatype="String", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Value", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Width", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "integertostring": BuiltinFunction(
        name="integertostring",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="String", datatype="String", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Value", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Width", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "isinsimulate": BuiltinFunction(
        name="isinsimulate",
        type="Function",
        return_type="Boolean",
        parameters=[],
        precision_scangroup=False
    ),
    "limit": BuiltinFunction(
        name="limit",
        type="Function",
        return_type="Boolean",
        parameters=[
            Parameter(name="Timer", datatype="Timer", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Value", datatype="Integer", direction="in", sorting="RS", ownership="RO")
        ],
        precision_scangroup=True
    ),
    "ln": BuiltinFunction(
        name="ln",
        type="Function",
        return_type="Real",
        parameters=[
            Parameter(name="Argument", datatype="Real", direction="in", sorting="RS", ownership="RO")
        ],
        precision_scangroup=True
    ),
    "loggedin": BuiltinFunction(
        name="loggedin",
        type="Function",
        return_type="Boolean",
        parameters=[
            Parameter(name="UserSign", datatype="String", direction="in", sorting="RS", ownership="RO")
        ],
        precision_scangroup=False
    ),
    "maxlim": BuiltinFunction(
        name="maxlim",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="In", datatype="Real", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="OnLim", datatype="Real", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Hyst", datatype="Real", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Q", datatype="Boolean", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=True
    ),
    "maxstringlength": BuiltinFunction(
        name="maxstringlength",
        type="Function",
        return_type="Integer",
        parameters=[
            Parameter(name="String", datatype="String", direction="in var", sorting="NoS", ownership="RO")
        ],
        precision_scangroup=False
    ),
    "minlim": BuiltinFunction(
        name="minlim",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="In", datatype="Real", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="OnLim", datatype="Real", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Hyst", datatype="Real", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Q", datatype="Boolean", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=True
    ),
    "mod": BuiltinFunction(
        name="mod",
        type="Function",
        return_type="Integer",
        parameters=[
            Parameter(name="Argument", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Argument", datatype="Integer", direction="in", sorting="RS", ownership="RO")
        ],
        precision_scangroup=True
    ),
    "movefile": BuiltinFunction(
        name="movefile",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="FileName", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="FileName", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Delete", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "nationallowercase": BuiltinFunction(
        name="nationallowercase",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="SourceString", datatype="String", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="DestinationString", datatype="String", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="NationCode", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "nationaluppercase": BuiltinFunction(
        name="nationaluppercase",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="SourceString", datatype="String", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="DestinationString", datatype="String", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="NationCode", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "neweditfile": BuiltinFunction(
        name="neweditfile",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="FileName", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="ReadOnly", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="xPos", datatype="Real", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="yPos", datatype="Real", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="RelativePos", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="NoOfRows", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="NoOfColumns", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="FontKind", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="FontSize", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "newwindow": BuiltinFunction(
        name="newwindow",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="ModulePath", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="WindowTitle", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="RelativePos", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="xPos", datatype="Real", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="yPos", datatype="Real", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="xSize", datatype="Real", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="ySize", datatype="Real", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="HierarchicRoot", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="SelectClass", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="TimeOut", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="WindowDisplayed", datatype="Boolean", direction="out", sorting="NoS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "octalstringtointeger": BuiltinFunction(
        name="octalstringtointeger",
        type="Function",
        return_type="Integer",
        parameters=[
            Parameter(name="String", datatype="String", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "offtimer": BuiltinFunction(
        name="offtimer",
        type="Function",
        return_type="Boolean",
        parameters=[
            Parameter(name="Timer", datatype="OnOffTimerType", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="Enable", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="PresetTime", datatype="Duration", direction="in var", sorting="RS", ownership="RO")
        ],
        precision_scangroup=True
    ),
    "ontimer": BuiltinFunction(
        name="ontimer",
        type="Function",
        return_type="Boolean",
        parameters=[
            Parameter(name="Timer", datatype="OnOffTimerType", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="Enable", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="PresetTime", datatype="Duration", direction="in var", sorting="RS", ownership="RO")
        ],
        precision_scangroup=True
    ),
    "opendevice": BuiltinFunction(
        name="opendevice",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Device", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="DeviceRef", datatype="tObject", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "openreadfile": BuiltinFunction(
        name="openreadfile",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="FileRef", datatype="tObject", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="FileName", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "openwritefile": BuiltinFunction(
        name="openwritefile",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="FileRef", datatype="tObject", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="FileName", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "operatorinteraction": BuiltinFunction(
        name="operatorinteraction",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Tag", datatype="String", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Severity", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Class", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Description", datatype="String", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="OldValue", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="NewValue", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "printfile": BuiltinFunction(
        name="printfile",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="RemotePrinterSysId", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="PrinterName", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="RemoteFileNameSave", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="LocalFileName", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="LocalFileDelete", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "pulsetimer": BuiltinFunction(
        name="pulsetimer",
        type="Function",
        return_type="Boolean",
        parameters=[
            Parameter(name="Timer", datatype="OnOffTimerType", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="PeriodTime", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="OnTime", datatype="Integer", direction="in", sorting="RS", ownership="RO")
        ],
        precision_scangroup=True
    ),
    "putarray": BuiltinFunction(
        name="putarray",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Array", datatype="ArrayObject", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Index", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="ArrayElement", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "putblanks": BuiltinFunction(
        name="putblanks",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="String", datatype="String", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="NumberOfSpaces", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "putfirstqueue": BuiltinFunction(
        name="putfirstqueue",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Queue", datatype="QueueObject", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="QueueElement", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "putlastqueue": BuiltinFunction(
        name="putlastqueue",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Queue", datatype="QueueObject", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="QueueElement", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "putrecordcompnosort": BuiltinFunction(
        name="putrecordcompnosort",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Rec", datatype="AnyType", direction="out", sorting="NoS", ownership="WO"),
            Parameter(name="ComponentIndex", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="InputRec", datatype="AnyType", direction="in var", sorting="NoS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="NoS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "putrecordcomponent": BuiltinFunction(
        name="putrecordcomponent",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Rec", datatype="AnyType", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="ComponentIndex", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="InputRec", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "putremotefile": BuiltinFunction(
        name="putremotefile",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="RemoteSystemIdentity", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="RemoteFileName", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="LocalFileName", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "putremotesinglefile": BuiltinFunction(
        name="putremotesinglefile",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="RemoteSystemIdentity", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="RemoteFileName", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="LocalFileName", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "randomnorm": BuiltinFunction(
        name="randomnorm",
        type="Function",
        return_type="Real",
        parameters=[
            Parameter(name="RandomGenerator", datatype="RandomGenerator", direction="inout", sorting="RS/WS", ownership="RO/WO")
        ],
        precision_scangroup=True
    ),
    "randomrect": BuiltinFunction(
        name="randomrect",
        type="Function",
        return_type="Real",
        parameters=[
            Parameter(name="Randomenerator", datatype="RandomGenerator", direction="inout", sorting="RS/WS", ownership="RO/WO")
        ],
        precision_scangroup=True
    ),
    "randomseed": BuiltinFunction(
        name="randomseed",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="RandomGenerator", datatype="RandomGenerator", direction="inout", sorting="RS/WS", ownership="RO/WO")
        ],
        precision_scangroup=True
    ),
    "readline": BuiltinFunction(
        name="readline",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="FileRef", datatype="tObject", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="String", datatype="String", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "readlinedevice": BuiltinFunction(
        name="readlinedevice",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="DeviceRef", datatype="tObject", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Data", datatype="AnyType", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "readqueue": BuiltinFunction(
        name="readqueue",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Queue", datatype="QueueObject", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Number", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="QueueElement", datatype="AnyType", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "readstringdevice": BuiltinFunction(
        name="readstringdevice",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="DeviceRef", datatype="tObject", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Data", datatype="AnyType", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "readsystemstring": BuiltinFunction(
        name="readsystemstring",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="SystemVarId", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="SystemVarStringVal", datatype="String", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "readvar": BuiltinFunction(
        name="readvar",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="RemoteVariable", datatype="AnyType", direction="inout", sorting="NoS", ownership="NoO"),
            Parameter(name="LocalVariable", datatype="AnyType", direction="out", sorting="NoS", ownership="WO"),
            Parameter(name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "realtostring": BuiltinFunction(
        name="realtostring",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="String", datatype="String", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Value", datatype="Real", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Width", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Fraction", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "removestaticrouting": BuiltinFunction(
        name="removestaticrouting",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="RedundantRoutingInfo", datatype="Boolean", direction="in", sorting="RS", ownership="RO")
        ],
        precision_scangroup=False
    ),
    "restorevariable": BuiltinFunction(
        name="restorevariable",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Variable", datatype="AnyType", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="RestoreFile", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "restorevariablematch": BuiltinFunction(
        name="restorevariablematch",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Variable", datatype="AnyType", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="RestoreFile", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "round": BuiltinFunction(
        name="round",
        type="Function",
        return_type="Integer",
        parameters=[
            Parameter(name="Argument", datatype="Real", direction="in", sorting="RS", ownership="RO")
        ],
        precision_scangroup=True
    ),
    "savetovss": BuiltinFunction(
        name="savetovss",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="FileName", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Comment", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "savevariable": BuiltinFunction(
        name="savevariable",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Variable", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="SaveFile", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "savevariablecoded": BuiltinFunction(
        name="savevariablecoded",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Variable", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="SaveFile", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "searcharray": BuiltinFunction(
        name="searcharray",
        type="Function",
        return_type="Boolean",
        parameters=[
            Parameter(name="Array", datatype="ArrayObject", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="SearchIndex", datatype="Integer", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="SearchCount", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="SearchElement", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="SearchComponent", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="FoundElement", datatype="AnyType", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "searchreccomponent": BuiltinFunction(
        name="searchreccomponent",
        type="Function",
        return_type="Boolean",
        parameters=[
            Parameter(name="Rec", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="SearchIndex", datatype="Integer", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="SearchCount", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="SearchRecord", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="SearchComponent", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="FoundRec", datatype="AnyType", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "setseed": BuiltinFunction(
        name="setseed",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Seed", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="RandomGenerator", datatype="RandomGenerator", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=True
    ),
    "setshowprogram": BuiltinFunction(
        name="setshowprogram",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Enable", datatype="Boolean", direction="in", sorting="RS", ownership="RO")
        ],
        precision_scangroup=False
    ),
    "setstringpos": BuiltinFunction(
        name="setstringpos",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="String", datatype="String", direction="inout", sorting="NoS", ownership="NoO"),
            Parameter(name="Position", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "settime": BuiltinFunction(
        name="settime",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Time", datatype="Time", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=True
    ),
    "setupdevice": BuiltinFunction(
        name="setupdevice",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Device", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Values", datatype="AnyType", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "sin": BuiltinFunction(
        name="sin",
        type="Function",
        return_type="Real",
        parameters=[
            Parameter(name="Argument", datatype="Real", direction="in", sorting="RS", ownership="RO")
        ],
        precision_scangroup=True
    ),
    "sqrt": BuiltinFunction(
        name="sqrt",
        type="Function",
        return_type="Real",
        parameters=[
            Parameter(name="Argument", datatype="Real", direction="in", sorting="RS", ownership="RO")
        ],
        precision_scangroup=True
    ),
    "standalonewindow": BuiltinFunction(
        name="standalonewindow",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="ModulePath", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="EnableTitle", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="WindowTitle", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="xPos", datatype="Real", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="yPos", datatype="Real", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="xSize", datatype="Real", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="ySize", datatype="Real", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="SelectClass", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="TimeOut", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="WindowDisplayed", datatype="Boolean", direction="out", sorting="NoS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "stringlength": BuiltinFunction(
        name="stringlength",
        type="Function",
        return_type="Integer",
        parameters=[
            Parameter(name="String", datatype="String", direction="in var", sorting="NoS", ownership="RO")
        ],
        precision_scangroup=False
    ),
    "stringmatch": BuiltinFunction(
        name="stringmatch",
        type="Function",
        return_type="Boolean",
        parameters=[
            Parameter(name="Pattern", datatype="String", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Searchstring", datatype="String", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="CaseSensitive", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "stringtoasciirecord": BuiltinFunction(
        name="stringtoasciirecord",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="String", datatype="String", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="NoOfCharsPerInteger", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="IntegerRecord", datatype="AnyType", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "stringtoduration": BuiltinFunction(
        name="stringtoduration",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="DurationString", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Duration", datatype="Duration", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "stringtointeger": BuiltinFunction(
        name="stringtointeger",
        type="Function",
        return_type="Integer",
        parameters=[
            Parameter(name="String", datatype="String", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "stringtoreal": BuiltinFunction(
        name="stringtoreal",
        type="Function",
        return_type="Real",
        parameters=[
            Parameter(name="String", datatype="String", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "stringtotime": BuiltinFunction(
        name="stringtotime",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="TimeString", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="TimeFormat", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Time", datatype="Time", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "stringtotimerecord": BuiltinFunction(
        name="stringtotimerecord",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="TimeString", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="TimeFormat", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="TimeRecord", datatype="TimeRecord", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "subdurationfromtime": BuiltinFunction(
        name="subdurationfromtime",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Time", datatype="Time", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Duration", datatype="Duration", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Time", datatype="Time", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=True
    ),
    "subdurations": BuiltinFunction(
        name="subdurations",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Duration", datatype="Duration", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Duration", datatype="Duration", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="DurationSum", datatype="Duration", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=True
    ),
    "subtimerecords": BuiltinFunction(
        name="subtimerecords",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="TimeRecord", datatype="TimeRecord", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="TimeRecord", datatype="TimeRecord", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Duration", datatype="Duration", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=True
    ),
    "subtimes": BuiltinFunction(
        name="subtimes",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Time", datatype="Time", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Time", datatype="Time", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Duration", datatype="Duration", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=True
    ),
    "systemboolean": BuiltinFunction(
        name="systemboolean",
        type="Function",
        return_type="Boolean",
        parameters=[
            Parameter(name="SystemVarId", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "systemcommand": BuiltinFunction(
        name="systemcommand",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Command", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "systeminteger": BuiltinFunction(
        name="systeminteger",
        type="Function",
        return_type="Integer",
        parameters=[
            Parameter(name="SystemVarId", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "systemreal": BuiltinFunction(
        name="systemreal",
        type="Function",
        return_type="Real",
        parameters=[
            Parameter(name="SystemVarId", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "timebefore": BuiltinFunction(
        name="timebefore",
        type="Function",
        return_type="Boolean",
        parameters=[
            Parameter(name="Time", datatype="Time", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Time", datatype="Time", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=True
    ),
    "timer": BuiltinFunction(
        name="timer",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Timer", datatype="Timer", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Enable", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Hold", datatype="Boolean", direction="in", sorting="RS", ownership="RO")
        ],
        precision_scangroup=True
    ),
    "timerclear": BuiltinFunction(
        name="timerclear",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Timer", datatype="Timer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=True
    ),
    "timerecordbefore": BuiltinFunction(
        name="timerecordbefore",
        type="Function",
        return_type="Boolean",
        parameters=[
            Parameter(name="TimeRecord", datatype="TimeRecord", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="TimeRecord", datatype="TimeRecord", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=True
    ),
    "timerecordtostring": BuiltinFunction(
        name="timerecordtostring",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="TimeRecord", datatype="TimeRecord", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="TimeFormat", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="TimeString", datatype="String", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "timerecordtotime": BuiltinFunction(
        name="timerecordtotime",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="TimeRecord", datatype="TimeRecord", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Time", datatype="Time", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=True
    ),
    "timerstart": BuiltinFunction(
        name="timerstart",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Timer", datatype="Timer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=True
    ),
    "timerstop": BuiltinFunction(
        name="timerstop",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Timer", datatype="Timer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=True
    ),
    "timetocalendarrecord": BuiltinFunction(
        name="timetocalendarrecord",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Time", datatype="Time", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="CalendarRecord", datatype="CalendarRecord", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=True
    ),
    "timetostring": BuiltinFunction(
        name="timetostring",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Time", datatype="Time", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="TimeFormat", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="TimeString", datatype="String", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "timetotimerecord": BuiltinFunction(
        name="timetotimerecord",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Time", datatype="Time", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="TimeRecord", datatype="TimeRecord", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=True
    ),
    "toggleeditfile": BuiltinFunction(
        name="toggleeditfile",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="FileName", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="ReadOnly", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="xPos", datatype="Real", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="yPos", datatype="Real", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="RelativePos", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="NoOfRows", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="NoOfColumns", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="FontKind", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="FontSize", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "togglewindow": BuiltinFunction(
        name="togglewindow",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="ModulePath", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="WindowTitle", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="RelativePos", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="xPos", datatype="Real", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="yPos", datatype="Real", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="xSize", datatype="Real", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="ySize", datatype="Real", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="HierarchicRoot", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="SelectClass", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="TimeOut", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="WindowDisplayed", datatype="Boolean", direction="out", sorting="NoS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "vssgetlasterror": BuiltinFunction(
        name="vssgetlasterror",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="ErrorCode", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="ErrorText", datatype="String", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "writeline": BuiltinFunction(
        name="writeline",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="FileRef", datatype="tObject", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="String", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "writelinedevice": BuiltinFunction(
        name="writelinedevice",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="DeviceRef", datatype="tObject", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Data", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="EndOfSection", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "writelongvar": BuiltinFunction(
        name="writelongvar",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="RemoteVariable", datatype="AnyType", direction="inout", sorting="NoS", ownership="NoO"),
            Parameter(name="LocalVariable", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "writestring": BuiltinFunction(
        name="writestring",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="FileRef", datatype="tObject", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="String", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "writestringdevice": BuiltinFunction(
        name="writestringdevice",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="DeviceRef", datatype="tObject", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Data", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="EndOfSection", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
    "writevar": BuiltinFunction(
        name="writevar",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="RemoteVariable", datatype="AnyType", direction="inout", sorting="NoS", ownership="NoO"),
            Parameter(name="LocalVariable", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO")
        ],
        precision_scangroup=False
    ),
}

def is_builtin_function(name: str) -> bool:
    """Check if a function name is a built-in"""
    return name.lower() in SATTLINE_BUILTINS

def get_function_signature(name: str) -> BuiltinFunction | None:
    """Get function signature for validation"""
    return SATTLINE_BUILTINS.get(name.lower())