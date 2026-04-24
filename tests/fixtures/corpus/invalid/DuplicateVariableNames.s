"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: DuplicateVariableNames"
(* INVALID: Two local variables with the same name (case-insensitive).
   Scope uniqueness validation rejects duplicate names within the same
   declaration scope. The check is case-insensitive: Counter and counter
   are treated as the same name.
   Expected: strict syntax-check fails at stage "validation". *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   Counter: integer  := 0;
   counter: integer  := 10;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

ENDDEF (*BasePicture*);
