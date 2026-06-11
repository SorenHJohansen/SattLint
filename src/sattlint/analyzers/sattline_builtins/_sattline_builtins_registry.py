"""Aggregated SattLine builtin registry."""

from ._sattline_builtin_types import BuiltinFunction
from ._sattline_builtins_part1 import SATTLINE_BUILTINS_PART1 as SATTLINE_BUILTINS_ABS_TO_CURRENTQUEUESIZE
from ._sattline_builtins_part2 import SATTLINE_BUILTINS_PART2 as SATTLINE_BUILTINS_CURRENTUSER_TO_INTEGERTOBCD
from ._sattline_builtins_part3 import (
    SATTLINE_BUILTINS_PART3 as SATTLINE_BUILTINS_INTEGERTOBOOLEAN16_TO_PUTREMOTESINGLEFILE,
)
from ._sattline_builtins_part4 import SATTLINE_BUILTINS_PART4 as SATTLINE_BUILTINS_RANDOMNORM_TO_STRINGTOREAL
from ._sattline_builtins_part5 import SATTLINE_BUILTINS_PART5 as SATTLINE_BUILTINS_STRINGTOTIME_TO_WRITEVAR

# Keep the registry split below the repo's 500-line cap while making the
# alphabetical shard boundaries explicit at the aggregation seam.
SATTLINE_BUILTINS: dict[str, BuiltinFunction] = {
    **SATTLINE_BUILTINS_ABS_TO_CURRENTQUEUESIZE,
    **SATTLINE_BUILTINS_CURRENTUSER_TO_INTEGERTOBCD,
    **SATTLINE_BUILTINS_INTEGERTOBOOLEAN16_TO_PUTREMOTESINGLEFILE,
    **SATTLINE_BUILTINS_RANDOMNORM_TO_STRINGTOREAL,
    **SATTLINE_BUILTINS_STRINGTOTIME_TO_WRITEVAR,
}

__all__ = ["SATTLINE_BUILTINS"]
