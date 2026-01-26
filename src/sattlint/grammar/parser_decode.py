# parser_decode.py
import re

# Seed mappings from your samples (robust and visible in both forms)

SEED_MAPPING: dict[str, str] = {
    # --- Core / control ---
    "#01": "(",
    "#04": "<",
    "#05": ">",
    "#06": "<=",
    "#07": ">=",
    "#08": "==",
    "#09": "<>",
    "#0?": "IF",
    "#10": "THEN",
    "#11": "ELSIF",
    "#12": "ELSE",
    "#13": "ENDIF",
    "#14": "AND",
    "#15": "OR",
    "#16": "NOT",
    # --- Booleans  ---
    "#1<": "False",
    "#1>": "False",
    "#1=": "True",
    # --- Sequences ---
    "#20": "EQUATIONBLOCK",
    "#22": "SEQUENCE",
    "#23": "ENDSEQUENCE",
    "#26": "SEQINITSTEP",
    "#27": "SEQSTEP",
    "#28": "ENTERCODE",
    "#29": "ACTIVECODE",
    "#30": "SEQTRANSITION",
    "#31": "WAIT_FOR",
    "#34": "ALTERNATIVESEQ",
    "#35": "ALTERNATIVEBRANCH",
    "#36": "ENDALTERNATIVE",
    "#3<": "SEQFORK",
    "#3=": "SEQBREAK",
    "#2:": "EXITCODE",
    # --- Variables ---
    "#3>": "InVar_",
    "#3?": "OutVar_",
    "#47": "Variable",
    "#60": "ValueFraction",
    # --- Module structure ---
    "#6>": "ModuleDef",
    "#6?": "Invocation",
    "#6=": "IgnoreMaxModule",
    "#6<": "LayerModule",
    "#65": "ClippingBounds",
    "#66": "Dim_",
    "#71": "MODULEDEFINITION",
    "#72": "RECORD",
    "#73": "MODULEPARAMETERS",
    "#74": "GLOBAL",
    "#78": "TYPEDEFINITIONS",
    "#79": "SUBMODULES",
    "#80": ";",
    "#81": "DateCode_",
    "#84": "ModuleCode",
    "#85": "ENDDEF",
    "#86": "GroupConn",
    "#87": "Frame_Module",
    # --- Graph / UI ---
    "#4?": "GraphObjects",
    "#40": "InteractObjects",
    "#41": "SimpleInteract",
    "#42": "MenuInteract",
    "#50": "LineObject",
    "#51": "OvalObject",
    "#52": "RectangleObject",
    "#53": "SegmentObject",
    "#54": "PolygonObject",
    "#55": "Spline",
    "#56": "TextObject",
    "#57": "Polyline",
    "#58": "LeftAligned",
    "#59": "CenterAligned",
    "#5:": "RightAligned",
    "#5<": "OutlineColour",
    "#5;": "FillColour",
    "#5=": "ColourStyle",
    "#5>": "Width_",
    "#61": "Colour0",
    "#62": "Colour1",
    "#63": "ZoomLimits",
    "#6:": "Zoomable",
    "#68": "Connection",
    "#69": "ConnectionNode",
    # --- Interactions ---
    "#95": "ProcedureInteract",
    "#96": "LitString",
    # --- Keywords / flags ---
    "#7;": "Const",
    "#7<": "LOCALVARIABLES",
    "#7:": "OpSave",
    "#77": "Secure",
    "#17": "Old",
    "#18": "Old",
    "#94": "Default",
    # --- Enable / layers ---
    "#64": "Enable_",
    "#;4": "Two_Layers_",
    "#;?": "LayerLimit_",
    "#;5": "Layer_",
    # --- Events ---
    "#9<": "Enable_",
    "#9>": "Event_Text_",
    "#9?": "Event_Tag_",
    "#9=": "Value_Changed",
    "#:0": "Event_Severity_",
    "#:1": "Event_Class_",
    "#:4": "Grid",
    "#:5": "Key_",
    "#:6": "ComBut_",
    "#:7": "ComButProc_",
    "#:8": "OptBut_",
    "#:9": "CheckBox_",
    # --- Misc UI ---
    "#:<": "Abs_",
    "#:>": "Value_",
    "#:?": "Decimal_",
    "#:;": "Visible_",
    "#;0": "Digits_",
    "#;1": "NoOf_",
    "#;3": "SetApp_",
    "#;9": "String_Value",
    "#;;": "Enable_Delay",
    "#;<": "OK_Variable",
    # --- Signatures ---
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
    decoded = re.sub(
        r"\bGraphObjects\b\s*:\s*InteractObjects\b", "InteractObjects", decoded
    )
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
