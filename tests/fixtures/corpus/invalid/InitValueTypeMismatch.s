"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: InitValueTypeMismatch"
(* INVALID: An integer variable initialized with a string literal.
   Declaration validation rejects incompatible init literal types.
   An integer variable must be initialized with an integer literal,
   not a quoted string.
   Expected: strict syntax-check fails at stage "validation". *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   Counter: integer  := "not a number";

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

ENDDEF (*BasePicture*);
