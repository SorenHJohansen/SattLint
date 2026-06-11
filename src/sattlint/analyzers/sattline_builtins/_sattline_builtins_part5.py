"""SattLine builtin registry shard for stringtotime-writevar."""

from ._sattline_builtin_types import BuiltinFunction, Parameter

SATTLINE_BUILTINS_PART5: dict[str, BuiltinFunction] = {
    "stringtotime": BuiltinFunction(
        name="stringtotime",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="TimeString", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="TimeFormat", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Time", datatype="Time", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "stringtotimerecord": BuiltinFunction(
        name="stringtotimerecord",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="TimeString", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="TimeFormat", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="TimeRecord", datatype="TimeRecord", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "subdurationfromtime": BuiltinFunction(
        name="subdurationfromtime",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Time", datatype="Time", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Duration", datatype="Duration", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Time", datatype="Time", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=True,
    ),
    "subdurations": BuiltinFunction(
        name="subdurations",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Duration", datatype="Duration", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Duration", datatype="Duration", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="DurationSum", datatype="Duration", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=True,
    ),
    "subtimerecords": BuiltinFunction(
        name="subtimerecords",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="TimeRecord", datatype="TimeRecord", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="TimeRecord", datatype="TimeRecord", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Duration", datatype="Duration", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=True,
    ),
    "subtimes": BuiltinFunction(
        name="subtimes",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Time", datatype="Time", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Time", datatype="Time", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Duration", datatype="Duration", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=True,
    ),
    "systemboolean": BuiltinFunction(
        name="systemboolean",
        type="Function",
        return_type="Boolean",
        parameters=[
            Parameter(name="SystemVarId", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "systemcommand": BuiltinFunction(
        name="systemcommand",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Command", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(
                name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"
            ),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "systeminteger": BuiltinFunction(
        name="systeminteger",
        type="Function",
        return_type="Integer",
        parameters=[
            Parameter(name="SystemVarId", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "systemreal": BuiltinFunction(
        name="systemreal",
        type="Function",
        return_type="Real",
        parameters=[
            Parameter(name="SystemVarId", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "timebefore": BuiltinFunction(
        name="timebefore",
        type="Function",
        return_type="Boolean",
        parameters=[
            Parameter(name="Time", datatype="Time", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Time", datatype="Time", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=True,
    ),
    "timer": BuiltinFunction(
        name="timer",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Timer", datatype="Timer", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Enable", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Hold", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
        ],
        precision_scangroup=True,
    ),
    "timerclear": BuiltinFunction(
        name="timerclear",
        type="Procedure",
        return_type=None,
        parameters=[Parameter(name="Timer", datatype="Timer", direction="out", sorting="WS", ownership="WO")],
        precision_scangroup=True,
    ),
    "timerecordbefore": BuiltinFunction(
        name="timerecordbefore",
        type="Function",
        return_type="Boolean",
        parameters=[
            Parameter(name="TimeRecord", datatype="TimeRecord", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="TimeRecord", datatype="TimeRecord", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=True,
    ),
    "timerecordtostring": BuiltinFunction(
        name="timerecordtostring",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="TimeRecord", datatype="TimeRecord", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="TimeFormat", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="TimeString", datatype="String", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "timerecordtotime": BuiltinFunction(
        name="timerecordtotime",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="TimeRecord", datatype="TimeRecord", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Time", datatype="Time", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=True,
    ),
    "timerstart": BuiltinFunction(
        name="timerstart",
        type="Procedure",
        return_type=None,
        parameters=[Parameter(name="Timer", datatype="Timer", direction="out", sorting="WS", ownership="WO")],
        precision_scangroup=True,
    ),
    "timerstop": BuiltinFunction(
        name="timerstop",
        type="Procedure",
        return_type=None,
        parameters=[Parameter(name="Timer", datatype="Timer", direction="out", sorting="WS", ownership="WO")],
        precision_scangroup=True,
    ),
    "timetocalendarrecord": BuiltinFunction(
        name="timetocalendarrecord",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Time", datatype="Time", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="CalendarRecord", datatype="CalendarRecord", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=True,
    ),
    "timetostring": BuiltinFunction(
        name="timetostring",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Time", datatype="Time", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="TimeFormat", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="TimeString", datatype="String", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "timetotimerecord": BuiltinFunction(
        name="timetotimerecord",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Time", datatype="Time", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="TimeRecord", datatype="TimeRecord", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=True,
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
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
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
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "vssgetlasterror": BuiltinFunction(
        name="vssgetlasterror",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="ErrorCode", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="ErrorText", datatype="String", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "writeline": BuiltinFunction(
        name="writeline",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="FileRef", datatype="tObject", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="String", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(
                name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"
            ),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "writelinedevice": BuiltinFunction(
        name="writelinedevice",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="DeviceRef", datatype="tObject", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Data", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="EndOfSection", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(
                name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"
            ),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "writelongvar": BuiltinFunction(
        name="writelongvar",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="RemoteVariable", datatype="AnyType", direction="inout", sorting="NoS", ownership="NoO"),
            Parameter(name="LocalVariable", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(
                name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"
            ),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "writestring": BuiltinFunction(
        name="writestring",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="FileRef", datatype="tObject", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="String", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(
                name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"
            ),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "writestringdevice": BuiltinFunction(
        name="writestringdevice",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="DeviceRef", datatype="tObject", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Data", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="EndOfSection", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(
                name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"
            ),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "writevar": BuiltinFunction(
        name="writevar",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="RemoteVariable", datatype="AnyType", direction="inout", sorting="NoS", ownership="NoO"),
            Parameter(name="LocalVariable", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(
                name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"
            ),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
}

__all__ = ["SATTLINE_BUILTINS_PART5"]
