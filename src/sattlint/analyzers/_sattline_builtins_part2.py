"""SattLine builtin registry part 2."""

from ._sattline_builtin_types import BuiltinFunction, Parameter

SATTLINE_BUILTINS_PART2: dict[str, BuiltinFunction] = {
    "currentuser": BuiltinFunction(
        name="currentuser",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="UserName", datatype="String", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="UserClassName", datatype="String", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "cutstring": BuiltinFunction(
        name="cutstring",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="String", datatype="String", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Length", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
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
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "deletearray": BuiltinFunction(
        name="deletearray",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Array", datatype="ArrayObject", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "deleteeditfile": BuiltinFunction(
        name="deleteeditfile",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="FileName", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "deletefile": BuiltinFunction(
        name="deletefile",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="FileName", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(
                name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"
            ),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "deletequeue": BuiltinFunction(
        name="deletequeue",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Queue", datatype="QueueObject", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "deletewindow": BuiltinFunction(
        name="deletewindow",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="ModulePath", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="SelectClass", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "durationgreaterthan": BuiltinFunction(
        name="durationgreaterthan",
        type="Function",
        return_type="Boolean",
        parameters=[
            Parameter(name="Duration", datatype="Duration", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Duration", datatype="Duration", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=True,
    ),
    "durationtodurrec": BuiltinFunction(
        name="durationtodurrec",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Duration", datatype="Duration", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="DurationRecord", datatype="DurationRecord", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=True,
    ),
    "durationtostring": BuiltinFunction(
        name="durationtostring",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Duration", datatype="Duration", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="DurationString", datatype="String", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "durrectoduration": BuiltinFunction(
        name="durrectoduration",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(
                name="DurationRecord", datatype="DurationRecord", direction="in var", sorting="RS", ownership="RO"
            ),
            Parameter(name="Duration", datatype="Duration", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=True,
    ),
    "elapsed": BuiltinFunction(
        name="elapsed",
        type="Function",
        return_type="Integer",
        parameters=[Parameter(name="Timer", datatype="Timer", direction="in var", sorting="RS", ownership="RO")],
        precision_scangroup=True,
    ),
    "equal": BuiltinFunction(
        name="equal",
        type="Function",
        return_type="Boolean",
        parameters=[
            Parameter(name="Variable", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Variable", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
        ],
        precision_scangroup=True,
    ),
    "equalstrings": BuiltinFunction(
        name="equalstrings",
        type="Function",
        return_type="Boolean",
        parameters=[
            Parameter(name="String1", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="String2", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="CaseSensitive", datatype="Boolean", direction="in", sorting="RS", ownership="RO"),
        ],
        precision_scangroup=True,
    ),
    "equalvariables": BuiltinFunction(
        name="equalvariables",
        type="Function",
        return_type="Boolean",
        parameters=[
            Parameter(name="Variable", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Variable", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=True,
    ),
    "exp": BuiltinFunction(
        name="exp",
        type="Function",
        return_type="Real",
        parameters=[Parameter(name="Argument", datatype="Real", direction="in", sorting="RS", ownership="RO")],
        precision_scangroup=True,
    ),
    "extractstring": BuiltinFunction(
        name="extractstring",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="String", datatype="String", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="String2", datatype="String", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Length", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "fdurationtostring": BuiltinFunction(
        name="fdurationtostring",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Duration", datatype="Duration", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="DurationFormat", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="DurationString", datatype="String", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "fileexists": BuiltinFunction(
        name="fileexists",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="FileName", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(
                name="AsyncOperation", datatype="AsyncOperation", direction="inout", sorting="RS/WS", ownership="RO/WO"
            ),
            Parameter(name="DebugStatus", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "getarray": BuiltinFunction(
        name="getarray",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Array", datatype="ArrayObject", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Index", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="ArrayElement", datatype="AnyType", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "getascii": BuiltinFunction(
        name="getascii",
        type="Function",
        return_type="Integer",
        parameters=[
            Parameter(name="Str", datatype="String", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "getfirstqueue": BuiltinFunction(
        name="getfirstqueue",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Queue", datatype="QueueObject", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="QueueElement", datatype="AnyType", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "getlastqueue": BuiltinFunction(
        name="getlastqueue",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Queue", datatype="QueueObject", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="QueueElement", datatype="AnyType", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "getrecordcompnosort": BuiltinFunction(
        name="getrecordcompnosort",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Rec", datatype="AnyType", direction="in var", sorting="NoS", ownership="RO"),
            Parameter(name="ComponentIndex", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="ResultRec", datatype="AnyType", direction="out", sorting="NoS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="NoS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "getrecordcomponent": BuiltinFunction(
        name="getrecordcomponent",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Rec", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="ComponentIndex", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="ResultRec", datatype="AnyType", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "getremotefile": BuiltinFunction(
        name="getremotefile",
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
    "getremotesinglefile": BuiltinFunction(
        name="getremotesinglefile",
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
    "getstringpos": BuiltinFunction(
        name="getstringpos",
        type="Function",
        return_type="Integer",
        parameters=[Parameter(name="String", datatype="String", direction="inout", sorting="NoS", ownership="NoO")],
        precision_scangroup=False,
    ),
    "getsystemtype": BuiltinFunction(
        name="getsystemtype", type="Function", return_type="Integer", parameters=[], precision_scangroup=False
    ),
    "gettime": BuiltinFunction(
        name="gettime",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Time", datatype="Time", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=True,
    ),
    "getuserfullname": BuiltinFunction(
        name="getuserfullname",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="UserName", datatype="String", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="FullName", datatype="String", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "getuseridletime": BuiltinFunction(
        name="getuseridletime", type="Function", return_type="Integer", parameters=[], precision_scangroup=False
    ),
    "graycodetointeger": BuiltinFunction(
        name="graycodetointeger",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="BooleanRecord", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Int", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=True,
    ),
    "initvariable": BuiltinFunction(
        name="initvariable",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Rec", datatype="AnyType", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="InitRec", datatype="AnyType", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "insertarray": BuiltinFunction(
        name="insertarray",
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
    "insertascii": BuiltinFunction(
        name="insertascii",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="ASCII", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Str", datatype="String", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "insertstring": BuiltinFunction(
        name="insertstring",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="String", datatype="String", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="String2", datatype="String", direction="in var", sorting="RS", ownership="RO"),
            Parameter(name="Length", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=False,
    ),
    "integertobcd": BuiltinFunction(
        name="integertobcd",
        type="Procedure",
        return_type=None,
        parameters=[
            Parameter(name="Int", datatype="Integer", direction="in", sorting="RS", ownership="RO"),
            Parameter(name="BCD", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
            Parameter(name="Status", datatype="Integer", direction="out", sorting="WS", ownership="WO"),
        ],
        precision_scangroup=True,
    ),
}

__all__ = ["SATTLINE_BUILTINS_PART2"]
