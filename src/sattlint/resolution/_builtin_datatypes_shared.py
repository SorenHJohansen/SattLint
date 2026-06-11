from __future__ import annotations

from sattline_parser.models.ast_model import Simple_DataType

BuiltinFieldSpec = tuple[str, Simple_DataType | str]

_BOOL = Simple_DataType.BOOLEAN
_INT = Simple_DataType.INTEGER
_REAL = Simple_DataType.REAL
_STR = Simple_DataType.STRING
_IDENT = Simple_DataType.IDENTSTRING
_TAG = Simple_DataType.TAGSTRING
_LINE = Simple_DataType.LINESTRING
_MAX = Simple_DataType.MAXSTRING
_TIME = Simple_DataType.TIME
_DURATION = Simple_DataType.DURATION


def _status_text_group(index: int) -> tuple[BuiltinFieldSpec, ...]:
    return (
        (f"OnText{index}", _IDENT),
        (f"OffText{index}", _IDENT),
        (f"Acktext{index}", _IDENT),
        (f"InhibitText{index}", _IDENT),
        (f"InhibitCancelText{index}", _IDENT),
        (f"AutoBlockText{index}", _IDENT),
    )


_SELECT_CLASS_USER_FIELDS = tuple(
    field
    for index in range(1, 11)
    for field in (
        (f"UserClass{index}", _INT),
        (f"UserTimeOut{index}", _INT),
    )
)

_STATUS_TEXT_FIELDS = (
    ("LostStateText", _IDENT),
    *_status_text_group(1),
    *_status_text_group(2),
    *_status_text_group(3),
)

_AXIS_FIELDS = tuple(
    (name, _REAL)
    for name in (
        "Xmin",
        "X1number",
        "X1interval",
        "X2number",
        "X2interval",
        "X3number",
        "X3interval",
        "X4number",
        "X4interval",
        "X5number",
        "X5interval",
        "Ymin",
        "Y1number",
        "Y1interval",
        "Y2number",
        "Y2interval",
        "Y3number",
        "Y3interval",
        "Y4number",
        "Y4interval",
        "Y5number",
        "Y5interval",
    )
)

_CURVE_MASTER_FIELDS = tuple((f"x{x}y{y}", _REAL) for y in range(3) for x in range(5))

_STATIC_FUNCTION_POINT_FIELDS = tuple((f"{axis}{index}", _REAL) for index in range(3, 11) for axis in ("x", "y"))

_STATIC_FUNCTION_USED_FIELDS = tuple((f"x{index}used", _BOOL) for index in range(3, 11))

_MANUAL_AUTO_REAL_FIELDS = (
    ("ManualValue", _REAL),
    ("Automatic", _BOOL),
    ("Max", _REAL),
    ("Min", _REAL),
)

_OPAQUE_BUILTIN_RECORD_NAMES = (
    "AcofTimerType",
    "EventSortRecType",
    "QueueObject",
    "SortedEventType",
    "Timer",
    "tObject",
)

_FIELDLESS_BUILTIN_RECORD_NAMES = ("ArrayObject", "RandomGenerator")

BOOL = _BOOL
INT = _INT
REAL = _REAL
STR = _STR
IDENT = _IDENT
TAG = _TAG
LINE = _LINE
MAX = _MAX
TIME = _TIME
DURATION = _DURATION
SELECT_CLASS_USER_FIELDS = _SELECT_CLASS_USER_FIELDS
STATUS_TEXT_FIELDS = _STATUS_TEXT_FIELDS
AXIS_FIELDS = _AXIS_FIELDS
CURVE_MASTER_FIELDS = _CURVE_MASTER_FIELDS
STATIC_FUNCTION_POINT_FIELDS = _STATIC_FUNCTION_POINT_FIELDS
STATIC_FUNCTION_USED_FIELDS = _STATIC_FUNCTION_USED_FIELDS
MANUAL_AUTO_REAL_FIELDS = _MANUAL_AUTO_REAL_FIELDS
FIELDLESS_BUILTIN_RECORD_NAMES = _FIELDLESS_BUILTIN_RECORD_NAMES
OPAQUE_BUILTIN_RECORD_NAMES = _OPAQUE_BUILTIN_RECORD_NAMES

__all__ = [
    "AXIS_FIELDS",
    "BOOL",
    "CURVE_MASTER_FIELDS",
    "DURATION",
    "FIELDLESS_BUILTIN_RECORD_NAMES",
    "IDENT",
    "INT",
    "LINE",
    "MANUAL_AUTO_REAL_FIELDS",
    "MAX",
    "OPAQUE_BUILTIN_RECORD_NAMES",
    "REAL",
    "SELECT_CLASS_USER_FIELDS",
    "STATIC_FUNCTION_POINT_FIELDS",
    "STATIC_FUNCTION_USED_FIELDS",
    "STATUS_TEXT_FIELDS",
    "STR",
    "TAG",
    "TIME",
    "BuiltinFieldSpec",
]
