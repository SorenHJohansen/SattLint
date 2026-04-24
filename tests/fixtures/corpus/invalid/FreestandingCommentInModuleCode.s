"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: FreestandingCommentInModuleCode"
(* INVALID: A comment appearing directly inside ModuleCode before the
   first EQUATIONBLOCK or SEQUENCE block.
   Single-file strict validation rejects freestanding comments directly
   inside ModuleCode at the top level (before any code block).
   Comments ARE allowed inside EQUATIONBLOCK or SEQUENCE bodies.
   Expected: strict syntax-check fails at stage "validation". *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   Output: integer  := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   (* This comment is invalid: it appears before any EQUATIONBLOCK or SEQUENCE *)
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Output = Output + 1;

ENDDEF (*BasePicture*);
