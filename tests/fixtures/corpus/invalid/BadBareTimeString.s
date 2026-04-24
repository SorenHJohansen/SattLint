"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: BadBareTimeString"
(* INVALID: A time variable initialized with a bare quoted string that
   does not match the YYYY-MM-DD-hh:mm:ss.ttt format.
   "2026/04/23 12:00:00" uses wrong separators and is rejected.
   Expected: strict syntax-check fails at stage "validation". *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   Timestamp: time  := "2026/04/23 12:00:00";

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

ENDDEF (*BasePicture*);
