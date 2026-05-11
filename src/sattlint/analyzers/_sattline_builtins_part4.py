"""SattLine builtin registry part 4."""

from ._sattline_builtin_types import BuiltinFunction, Parameter

SATTLINE_BUILTINS_PART4: dict[str, BuiltinFunction] = {
    "randomnorm": BuiltinFunction(
        name="randomnorm",
        type="Function",
        return_type="Real",
        parameters=[
            Parameter(
                name="RandomGenerator",
                datatype="RandomGenerator",
                direction="inout",
                sorting="RS/WS",
                ownership="RO/WO",
            )
        ],
        precision_scangroup=True,
    ),
    "randomrect": BuiltinFunction(
        name="randomrect",
        type="Function",
        return_type="Real",
        parameters=[
            Parameter(
                name="RandomGenerator",
                datatype="RandomGenerator",
                direction="inout",
                sorting="RS/WS",
                ownership="RO/WO",
            )
        ],
        precision_scangroup=True,
    ),
    "randomseed": BuiltinFunction(
        name="randomseed",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(
                name="RandomGenerator",
                datatype="RandomGenerator",
                direction="inout",
                sorting="RS/WS",
                ownership="RO/WO",
            )
        ],
        precision_scangroup=True,
    ),
    "readline": BuiltinFunction(
        name="readline",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="FileRef", datatype="tObject", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="String", datatype="String", direction="out", sorting="WS", ownership="WO"),
            Parameter(
                name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"
            ),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "readlinedevice": BuiltinFunction(
        name="readlinedevice",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="DeviceRef", datatype="tObject", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Data", datatype="AnyType", direction="out", sorting="WS", ownership="WO"),
            Parameter(
                name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"
            ),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "readqueue": BuiltinFunction(
        name="readqueue",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Queue", datatype="QueueObject", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Number", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="QueueElement", datatype="AnyType", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "readstringdevice": BuiltinFunction(
        name="readstringdevice",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="DeviceRef", datatype="tObject", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Data", datatype="AnyType", direction="out", sorting="WS", ownership="WO"),
            Parameter(
                name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"
            ),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "readsystemstring": BuiltinFunction(
        name="readsystemstring",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="SystemVarId", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="SystemVarStringVal", datatype="String", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "readvar": BuiltinFunction(
        name="readvar",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="RemoteVariable", datatype="AnyType", direction="inout", sorting="NoS", ownership="NoO"),
            Parameter(name="LocalVariable", datatype="AnyType", direction="out", sorting="NoS", ownership="WO"),
            Parameter(
                name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"
            ),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
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
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "removestaticrouting": BuiltinFunction(
        name="removestaticrouting",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="RedundantRoutingInfo", datatype="Boolean", direction="in", sorting="RS", ownership="RO")
        ],
        precision_scangroup=False,
    ),
    "restorevariable": BuiltinFunction(
        name="restorevariable",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Variable", datatype="AnyType", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="RestoreFile", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "restorevariablematch": BuiltinFunction(
        name="restorevariablematch",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Variable", datatype="AnyType", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="RestoreFile", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "round": BuiltinFunction(
        name="round",
        type="Function",
        return_type="Integer",
        parameters=[Parameter(name="Argument", datatype="Real", direction="in", sorting="RS", ownership="RO")],
        precision_scangroup=True,
    ),
    "savetovss": BuiltinFunction(
        name="savetovss",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="FileName", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Comment", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(
                name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"
            ),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "savevariable": BuiltinFunction(
        name="savevariable",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Variable", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="SaveFile", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "savevariablecoded": BuiltinFunction(
        name="savevariablecoded",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Variable", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="SaveFile", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
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
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
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
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "setbooleanvalue": BuiltinFunction(
        name="SetBooleanValue",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Variable", datatype="Boolean", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Value", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
        ],
        precision_scangroup=False,
    ),
    "setseed": BuiltinFunction(
        name="setseed",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Seed", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(
                name="RandomGenerator", datatype="RandomGenerator", direction="out", sorting="WS", ownership="WO"
            ),
        ],
        precision_scangroup=True,
    ),
    "setshowprogram": BuiltinFunction(
        name="setshowprogram",
        type="Procedure",
        return_type=None,
        parameters=[Parameter(name="Enable", datatype="Boolean", direction="in", sorting="RS", ownership="RO")],
        precision_scangroup=False,
    ),
    "setstringpos": BuiltinFunction(
        name="setstringpos",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="String", datatype="String", direction="inout", sorting="NoS", ownership="NoO"),
            Parameter(name="Position", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "settime": BuiltinFunction(
        name="settime",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Time", datatype="Time", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=True,
    ),
    "setupdevice": BuiltinFunction(
        name="setupdevice",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Device", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Values", datatype="AnyType", direction="inout", sorting="RS/WS", ownership="RO/WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "sin": BuiltinFunction(
        name="sin",
        type="Function",
        return_type="Real",
        parameters=[Parameter(name="Argument", datatype="Real", direction="in", sorting="RS", ownership="RO")],
        precision_scangroup=True,
    ),
    "sqrt": BuiltinFunction(
        name="sqrt",
        type="Function",
        return_type="Real",
        parameters=[Parameter(name="Argument", datatype="Real", direction="in", sorting="RS", ownership="RO")],
        precision_scangroup=True,
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
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "stringlength": BuiltinFunction(
        name="stringlength",
        type="Function",
        return_type="Integer",
        parameters=[Parameter(name="String", datatype="String", direction="in var", sorting="NoS", ownership="RO")],
        precision_scangroup=False,
    ),
    "stringmatch": BuiltinFunction(
        name="stringmatch",
        type="Function",
        return_type="Boolean",
        parameters=[
            Parameter(name="Pattern", datatype="String", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Searchstring", datatype="String", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="CaseSensitive", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "stringtoasciirecord": BuiltinFunction(
        name="stringtoasciirecord",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="String", datatype="String", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="NoOfCharsPerInteger", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="IntegerRecord", datatype="AnyType", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "stringtoduration": BuiltinFunction(
        name="stringtoduration",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="DurationString", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Duration", datatype="Duration", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "stringtointeger": BuiltinFunction(
        name="stringtointeger",
        type="Function",
        return_type="Integer",
        parameters=[
            Parameter(name="String", datatype="String", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "stringtoreal": BuiltinFunction(
        name="stringtoreal",
        type="Function",
        return_type="Real",
        parameters=[
            Parameter(name="String", datatype="String", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
}

__all__ = ["SATTLINE_BUILTINS_PART4"]
