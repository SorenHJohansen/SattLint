"""SattLine builtin registry part 1."""

from ._sattline_builtin_types import BuiltinFunction, Parameter

SATTLINE_BUILTINS_PART1: dict[str, BuiltinFunction] = {
    "abs": BuiltinFunction(
        name="abs",
        type="Function",
        return_type="AnyType",
        parameters=[Parameter(name="Argument", datatype="AnyType", direction="in", sorting="RS", ownership="RO")],
        precision_scangroup=True,
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
            Parameter(name="Time", datatype="Duration", direction="in var", sorting="RS", ownership="RO"),
        ],
        precision_scangroup=True,
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
            Parameter(name="Time", datatype="Duration", direction="in var", sorting="RS", ownership="RO"),
        ],
        precision_scangroup=True,
    ),
    "acof3": BuiltinFunction(
        name="acof3",
        type="Function",
        return_type="Boolean",
        parameters=[
            Parameter(name="Acof", datatype="AcofType", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="OO", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="O", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Time", datatype="Duration", direction="in var", sorting="RS", ownership="RO"),
        ],
        precision_scangroup=True,
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
            Parameter(name="Time", datatype="Duration", direction="in var", sorting="RS", ownership="RO"),
        ],
        precision_scangroup=True,
    ),
    "acof5": BuiltinFunction(
        name="acof5",
        type="Function",
        return_type="Boolean",
        parameters=[
            Parameter(name="Acof", datatype="AcofType", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="OO", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="C", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Time", datatype="Duration", direction="in var", sorting="RS", ownership="RO"),
        ],
        precision_scangroup=True,
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
            Parameter(name="Time", datatype="Duration", direction="in var", sorting="RS", ownership="RO"),
        ],
        precision_scangroup=True,
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
            Parameter(name="Time", datatype="Duration", direction="in var", sorting="RS", ownership="RO"),
        ],
        precision_scangroup=True,
    ),
    "adddurations": BuiltinFunction(
        name="adddurations",
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
    "addtimeandduration": BuiltinFunction(
        name="addtimeandduration",
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
    "arctan": BuiltinFunction(
        name="arctan",
        type="Function",
        return_type="Real",
        parameters=[Parameter(name="Argument", datatype="Real", direction="in", sorting="RS", ownership="RO")],
        precision_scangroup=True,
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
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "assignsystemboolean": BuiltinFunction(
        name="assignsystemboolean",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="SysVarId", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="SystemVarBoolVal", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "assignsysteminteger": BuiltinFunction(
        name="assignsysteminteger",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="SysVarId", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="SystemVarIntVal", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "assignsystemreal": BuiltinFunction(
        name="assignsystemreal",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="SysVarId", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="SystemVarRealVal", datatype="Real", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "assignsystemstring": BuiltinFunction(
        name="assignsystemstring",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="SysVarId", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="SystemVarStringVal", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "bcdtointeger": BuiltinFunction(
        name="bcdtointeger",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="BCD", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Int", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=True,
    ),
    "boolean16tointeger": BuiltinFunction(
        name="boolean16tointeger",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="BooleanRecord", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Int", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=True,
    ),
    "boolean32tointeger": BuiltinFunction(
        name="boolean32tointeger",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="BooleanRecord", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Int", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=True,
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
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "clearqueue": BuiltinFunction(
        name="clearqueue",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Queue", datatype="QueueObject", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "clearstring": BuiltinFunction(
        name="clearstring",
        type="Procedure",
        return_type=None,
        parameters=[Parameter(name="String", datatype="String", direction="out", sorting="WS", ownership="WO")],
        precision_scangroup=False,
    ),
    "closedevice": BuiltinFunction(
        name="closedevice",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="DeviceRef", datatype="tObject", direction="in", sorting="RS", ownership="RO"),
            Parameter(
                name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"
            ),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "closefile": BuiltinFunction(
        name="closefile",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="FileRef", datatype="tObject", direction="in var", sorting="RS", ownership="RO"),
            Parameter(
                name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"
            ),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "comlidial": BuiltinFunction(
        name="comlidial",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="ComliMaster", datatype="tObject", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="TelePhoneNo", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(
                name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"
            ),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "comlihangup": BuiltinFunction(
        name="comlihangup",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="ComliMaster", datatype="tObject", direction="in", sorting="RS", ownership="RO"),
            Parameter(
                name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"
            ),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "concatenate": BuiltinFunction(
        name="concatenate",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="String1", datatype="String", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="String2", datatype="String", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Result", datatype="String", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "copyduration": BuiltinFunction(
        name="copyduration",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Source", datatype="Duration", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Destination", datatype="Duration", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=True,
    ),
    "copystring": BuiltinFunction(
        name="copystring",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Source", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Destination", datatype="String", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=True,
    ),
    "copystringnosort": BuiltinFunction(
        name="copystringnosort",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Source", datatype="String", direction="in var", sorting="NoS", ownership="RO"),
            Parameter(name="Destination", datatype="String", direction="out", sorting="NoS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=True,
    ),
    "copytime": BuiltinFunction(
        name="copytime",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Source", datatype="Time", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Destination", datatype="Time", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=True,
    ),
    "copyvariable": BuiltinFunction(
        name="copyvariable",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Source", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Destination", datatype="AnyType", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=True,
    ),
    "copyvarnosort": BuiltinFunction(
        name="copyvarnosort",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Source", datatype="AnyType", direction="in var", sorting="NoS", ownership="RO"),
            Parameter(name="Destination", datatype="AnyType", direction="out", sorting="NoS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=True,
    ),
    "cos": BuiltinFunction(
        name="cos",
        type="Function",
        return_type="Real",
        parameters=[Parameter(name="Argument", datatype="Real", direction="in", sorting="RS", ownership="RO")],
        precision_scangroup=True,
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
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "createdevice": BuiltinFunction(
        name="createdevice",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Device", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "createqueue": BuiltinFunction(
        name="createqueue",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Queue", datatype="QueueObject", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Size", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="QueueElement", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "createwritefile": BuiltinFunction(
        name="createwritefile",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="FileRef", datatype="tObject", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="FileName", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(
                name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"
            ),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "currentqueuesize": BuiltinFunction(
        name="currentqueuesize",
        type="Function",
        return_type="Integer",
        parameters=[
            Parameter(name="Queue", datatype="QueueObject", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
}

__all__ = ["SATTLINE_BUILTINS_PART1"]
