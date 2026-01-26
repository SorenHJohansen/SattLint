# parser_decode.py
import re

# Seed mappings from your samples (robust and visible in both forms)
SEED_MAPPING: dict[str, str] = {
    "#6?": "Invocation",
    "#6=": "IgnoreMaxModule",
    "#8=": ":",
    "#71": "MODULEDEFINITION",
    "#81": "DateCode_",
    "#78": "TYPEDEFINITIONS",
    "#72": "RECORD",
    "#85": "ENDDEF",
    "#7:": "OpSave",
    "#7:;": "OpSave;",
    "#7;;": ";",
    "#01": "(",
    "#8?": "=",
    "#8:": "=>",
    "#8;": ":=",
    "#1<": "False",
    "#1<;": "False;",
    "#1>": "False",
    "#1>;": "False;",
    "#1=": "True",
    "#1=;": "True;",
    "#1;;": "True;",
    "#1;": "True",
    "#79": "SUBMODULES",
    "#73": "MODULEPARAMETERS",
    "#7<": "LOCALVARIABLES",
        "#74": "GLOBAL",
    "#80": ";",
    "#80;": ";",
    "#17": "Old",
    "#17;": "Old;",
        "#18": "Old",
    "#18;": "Old;",
    "#87": "Frame_Module",
    "#6<": "LayerModule",
    "#6>": "ModuleDef",
    "#65": "ClippingBounds",
    "#66": "Dim_",
    "#40": "InteractObjects",
    "#41": "SimpleInteract",
    "#42": "MenuInteract",
    "#::": "TextBox_",
    "#4?": "GraphObjects",
    "#56": "TextObject",
    "#70": "",
    "#52": "RectangleObject",
    "#50": "LineObject",
    "#51": "OvalObject",
    "#53": "SegmentObject",
    "#54": "PolygonObject",
    "#55": "Spline",
    "#57": "Polyline",
    "#58": "LeftAligned",
    "#5<": "OutlineColour",
    "#5;": "FillColour",
    "#5:": "RightAligned",
    "#59": "CenterAligned",
    "#5=": "ColourStyle",
    "#5?": "VarName",
    "#5>": "Width_",
    "#95": "ProcedureInteract",
    "#61": "Colour0",
    "#62": "Colour1",
    "#63": "ZoomLimits",
    "#6:": "Zoomable",
    "#68": "Connection",
    "#69": "ConnectionNode",
    "#43": "SelectVariable",
    "#84": "ModuleCode",
    "#86": "GroupConn",
    "#77": "Secure",
    "#77;": "Secure;",
    "#20": "EQUATIONBLOCK",
    "#22": "SEQUENCE",
    "#23": "ENDSEQUENCE",
    "#88": "COORD",
    "#89": "OBJSIZE",
    "#26": "SEQINITSTEP",
    "#27": "SEQSTEP",
    "#28": "ENTERCODE",
    "#29": "ACTIVECODE",
    "#30": "SEQTRANSITION",
    "#31": "WAIT_FOR",
    "#34": "ALTERNATIVESEQ",
    "#35": "ALTERNATIVEBRANCH",
    "#36": "ENDALTERNATIVE",
    "#2:": "EXITCODE",
    "#94;": "Default;",
    "#94": "Default",
    "#7;": "Const",
    "#;5": "Layer_",
    "#;7": "Int_Value",
    "#;6": "Bool_Value",
    "#64": "Enable_",
    "#3>": "InVar_",
    "#3?": "OutVar_",
    "#3<": "SEQFORK",
    "#3=": "SEQBREAK",
    "#47": "Variable",
    "#48": "OpMin",
    "#49": "OpMax",
    "#4:": "OpStep",
    "#4=": "ToggleAction",
    "#4;": "SetAction",
    "#4<": "ResetAction",
    "#60": "ValueFraction",
    "#9>": "Event_Text_",
    "#9?": "Event_Tag_",
    "#9=": "Value_Changed",
    "#9<": "Enable_",
    "#96": "LitString",
    "#:0": "Event_Severity_",
    "#:1": "Event_Class_",
    "#:6": "ComBut_",
    "#:7": "ComButProc_",
    "#:8": "OptBut_",
    "#:>": "Value_",
    "#:9": "CheckBox_",
    "#:3": "Format_String_",
    "#:5": "Key_",
    "#:4": "Grid",
    "#:?": "Decimal_",
    "#:;": "Visible_",
    "#:<": "Abs_",
    "#;0": "Digits_",
    "#;1": "NoOf_",
    "#;3": "SetApp_",
    "#;4": "Two_Layers_",
    "#;?": "LayerLimit_",
    "#;:": "Alt_Text",
    "#;9": "String_Value",
    "#;=": "Cancel_Variable",
    "#;;": "Enable_Delay",
    "#;<": "OK_Variable",
    "#16": "NOT",
    "#14": "AND",
    "#0?": "IF",
    "#11": "ELSIF",
    "#10": "THEN",
    "#15": "OR",
    "#12": "ELSE",
    "#13;": "ENDIF;",
    "#13": "ENDIF",
    "#05": ">",
    "#04": "<",
    "#07": ">=",
    "#06": "<=",
    "#08": "==",
    "#09": "<>",
    "#<0": "SnglSgn",
    "#<1": "SnglSgnEna",
    "#<2": "Purpose_",
    "#<4": "SgnrCom",
    "#<5": "CommentChng",
    "#<6": "CommentMand",
    "#<7": "Signer1_",
    "#<8": "Signer1Name_",
    "#<9": "DblSgn",
    "#<:": "DblSgnEna",
    "#<;": "CansCom",
    "#<<": "SgnCans",
    "#<=": "Signer2_",
    "#<>": "Signer2Name_",
}

# You can optionally seed more when you see stable pairs in other files.
# For example, many compressed samples also use:
# "#01" often appears at the start of tuples like "( 0.0 , 0.0 , ...", but since "(" remains visible,
# we avoid guessing punctuation for "#01" until learned via an aligned pair.

_MARKER_RE = re.compile(r"#[0-9A-Za-z;:=><?]+")


def is_compressed(text: str) -> bool:
    """Heuristic detector for compressed SattLine format."""
    markers = _MARKER_RE.findall(text)
    if not markers:
        return False
    compact_len = max(len(re.sub(r"\s+", "", text)), 1)
    marker_char_ratio = len("".join(markers)) / compact_len
    marker_count = len(markers)
    keyword_hits = sum(
        1
        for kw in (
            "MODULEDEFINITION",
            "TYPEDEFINITIONS",
            "MODULEPARAMETERS",
            "EQUATIONBLOCK",
        )
        if kw in text
    )
    return (
        marker_count >= 50
        or marker_char_ratio >= 0.02
        or (marker_count >= 10 and keyword_hits == 0)
    )


def decode_compressed(text: str, mapping: dict[str, str]) -> str:
    """Replace #markers using the mapping. Leaves unknown markers as-is."""
    def _subst(m: re.Match) -> str:
        tok = m.group(0)
        if tok.startswith("#01") and len(tok) > 3:
            return "(" + tok[3:]
        if tok == "#0<":
            return "*"
        if tok.startswith("#0<") and len(tok) > 3:
            return "* " + tok[3:]
        return mapping.get(tok, " ")

    decoded = _MARKER_RE.sub(_subst, text)
    # Normalize common ABB formatting quirks
    decoded = re.sub(r"\bENDDEF\b\s*;", "ENDDEF", decoded)
    decoded = re.sub(r";\s*:=", " :=", decoded)
    decoded = re.sub(r"ENDIF;\s*,", "ENDIF,", decoded)
    decoded = re.sub(r"ENDIF;\s*\)", "ENDIF)", decoded)
    decoded = re.sub(r":=\s*;", ":= Default;", decoded)
    decoded = re.sub(r"\bGraphObjects\b\s*:\s*InteractObjects\b", "InteractObjects", decoded)
    decoded = re.sub(
        r"(ExecuteLocalOld\s*=\s*ExecuteLocal:Old)\s+ENDDEF",
        r"\1; ENDDEF",
        decoded,
    )
    decoded = re.sub(
        r"(ExecuteState:Old)\s+IF\b",
        r"\1; IF",
        decoded,
    )
    # Ensure IF statements terminate with ';' (but not inside expressions)
    decoded = re.sub(r"\bENDIF\b(?!\s*[;,\)])", "ENDIF;", decoded)
    # Drop empty GraphObjects sections before ENDDEF
    decoded = re.sub(
        r"\bGraphObjects\b\s*:\s*ENDDEF\b",
        "ENDDEF",
        decoded,
    )
    # Ensure variable groups end with ';' before ENDDEF
    decoded = re.sub(
        r"\b(integer|real|boolean|string)\b\s+ENDDEF\b",
        r"\1 ; ENDDEF",
        decoded,
        flags=re.IGNORECASE,
    )
    # Normalize Enable_ tails to use InVar_ for grammar compatibility
    decoded = re.sub(
        r"(Enable_\s*=\s*\w+\s*:)\s*OutVar_",
        r"\1 InVar_",
        decoded,
    )
    # Avoid BOOL tokenizing identifiers like TrueVar
    decoded = re.sub(r"\bTrueVar\b", "TTrueVar", decoded)
    # Inject missing ModuleCode before EQUATIONBLOCK when none exists in the same module
    def _ensure_modulecode(m: re.Match) -> str:
        last_enddef = decoded.rfind("ENDDEF", 0, m.start())
        last_modulecode = decoded.rfind("ModuleCode", 0, m.start())
        if last_modulecode > last_enddef:
            return m.group(0)
        return "ModuleCode " + m.group(0)

    decoded = re.sub(r"\bEQUATIONBLOCK\b", _ensure_modulecode, decoded)
    # Fill empty trailing function arguments (e.g., "Func(a, )")
    decoded = re.sub(
        r"\b([A-Za-z_][A-Za-z0-9_]*)\(([^)]*?),\s*\)",
        r"\1(\2, 0)",
        decoded,
    )
    return decoded
def preprocess_sl_text(text: str) -> tuple[str, dict[str, str]]:
    """Decode compressed text using the seed mapping (no file output)."""
    mapping = dict(SEED_MAPPING)
    decoded = decode_compressed(text, mapping)
    return decoded, mapping
