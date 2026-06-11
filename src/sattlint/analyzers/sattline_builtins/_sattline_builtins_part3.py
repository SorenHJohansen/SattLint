"""SattLine builtin registry shard for integertoboolean16-putremotesinglefile."""

from ._sattline_builtin_types import BuiltinFunction, Parameter

SATTLINE_BUILTINS_PART3: dict[str, BuiltinFunction] = {
    "integertoboolean16": BuiltinFunction(
        name="integertoboolean16",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Int", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="BooleanRecord", datatype="AnyType", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=True,
    ),
    "integertoboolean32": BuiltinFunction(
        name="integertoboolean32",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Int", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="BooleanRecord", datatype="AnyType", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=True,
    ),
    "integertograycode": BuiltinFunction(
        name="integertograycode",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Int", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="BooleanRecord", datatype="AnyType", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=True,
    ),
    "integertooctalstring": BuiltinFunction(
        name="integertooctalstring",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="String", datatype="String", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Value", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Width", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "integertostring": BuiltinFunction(
        name="integertostring",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="String", datatype="String", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Value", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Width", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "isinsimulate": BuiltinFunction(
        name="isinsimulate", type="Function", return_type="Boolean", parameters=[], precision_scangroup=False
    ),
    "limit": BuiltinFunction(
        name="limit",
        type="Function",
        return_type="Boolean",
        parameters=[
            Parameter(name="Timer", datatype="Timer", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Value", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
        ],
        precision_scangroup=True,
    ),
    "ln": BuiltinFunction(
        name="ln",
        type="Function",
        return_type="Real",
        parameters=[Parameter(name="Argument", datatype="Real", direction="in", sorting="RS", ownership="RO")],
        precision_scangroup=True,
    ),
    "loggedin": BuiltinFunction(
        name="loggedin",
        type="Function",
        return_type="Boolean",
        parameters=[Parameter(name="UserSign", datatype="String", direction="in", sorting="RS", ownership="RO")],
        precision_scangroup=False,
    ),
    "maxlim": BuiltinFunction(
        name="maxlim",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="In", datatype="Real", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="OnLim", datatype="Real", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Hyst", datatype="Real", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Q", datatype="Boolean", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=True,
    ),
    "maxstringlength": BuiltinFunction(
        name="maxstringlength",
        type="Function",
        return_type="Integer",
        parameters=[Parameter(name="String", datatype="String", direction="in var", sorting="NoS", ownership="RO")],
        precision_scangroup=False,
    ),
    "minlim": BuiltinFunction(
        name="minlim",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="In", datatype="Real", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="OnLim", datatype="Real", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Hyst", datatype="Real", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Q", datatype="Boolean", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=True,
    ),
    "mod": BuiltinFunction(
        name="mod",
        type="Function",
        return_type="Integer",
        parameters=[
            Parameter(name="Argument", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Argument", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
        ],
        precision_scangroup=True,
    ),
    "movefile": BuiltinFunction(
        name="movefile",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="FileName", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="FileName", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Delete", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(
                name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"
            ),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "nationallowercase": BuiltinFunction(
        name="nationallowercase",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="SourceString", datatype="String", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="DestinationString", datatype="String", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="NationCode", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "nationaluppercase": BuiltinFunction(
        name="nationaluppercase",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="SourceString", datatype="String", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="DestinationString", datatype="String", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="NationCode", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
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
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
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
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "octalstringtointeger": BuiltinFunction(
        name="octalstringtointeger",
        type="Function",
        return_type="Integer",
        parameters=[
            Parameter(name="String", datatype="String", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "offtimer": BuiltinFunction(
        name="offtimer",
        type="Function",
        return_type="Boolean",
        parameters=[
            Parameter(name="Timer", datatype="OnOffTimerType", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="Enable", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="PresetTime", datatype="Duration", direction="in var", sorting="RS", ownership="RO"),
        ],
        precision_scangroup=True,
    ),
    "ontimer": BuiltinFunction(
        name="ontimer",
        type="Function",
        return_type="Boolean",
        parameters=[
            Parameter(name="Timer", datatype="OnOffTimerType", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="Enable", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="PresetTime", datatype="Duration", direction="in var", sorting="RS", ownership="RO"),
        ],
        precision_scangroup=True,
    ),
    "opendevice": BuiltinFunction(
        name="opendevice",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Device", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="DeviceRef", datatype="tObject", direction="out", sorting="WS", ownership="WO"),
            Parameter(
                name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"
            ),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "openreadfile": BuiltinFunction(
        name="openreadfile",
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
    "openwritefile": BuiltinFunction(
        name="openwritefile",
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
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
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
            Parameter(
                name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"
            ),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "pulsetimer": BuiltinFunction(
        name="pulsetimer",
        type="Function",
        return_type="Boolean",
        parameters=[
            Parameter(name="Timer", datatype="OnOffTimerType", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="PeriodTime", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="OnTime", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
        ],
        precision_scangroup=True,
    ),
    "putarray": BuiltinFunction(
        name="putarray",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Array", datatype="ArrayObject", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Index", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="ArrayElement", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "putblanks": BuiltinFunction(
        name="putblanks",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="String", datatype="String", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="NumberOfSpaces", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "putfirstqueue": BuiltinFunction(
        name="putfirstqueue",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Queue", datatype="QueueObject", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="QueueElement", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "putlastqueue": BuiltinFunction(
        name="putlastqueue",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Queue", datatype="QueueObject", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="QueueElement", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "putrecordcompnosort": BuiltinFunction(
        name="putrecordcompnosort",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Rec", datatype="AnyType", direction="out", sorting="NoS", ownership="WO"),
            Parameter(name="ComponentIndex", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="InputRec", datatype="AnyType", direction="in var", sorting="NoS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="NoS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "putrecordcomponent": BuiltinFunction(
        name="putrecordcomponent",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Rec", datatype="AnyType", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="ComponentIndex", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="InputRec", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "putremotefile": BuiltinFunction(
        name="putremotefile",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="RemoteSystemIdentity", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="RemoteFileName", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="LocalFileName", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(
                name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"
            ),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "putremotesinglefile": BuiltinFunction(
        name="putremotesinglefile",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="RemoteSystemIdentity", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="RemoteFileName", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="LocalFileName", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(
                name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"
            ),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
}

__all__ = ["SATTLINE_BUILTINS_PART3"]
