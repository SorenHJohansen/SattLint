"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: NeverReadVariable"
(* SEMANTIC: A local variable is written in equations but never read on the
   right-hand side of any expression, used in a condition, or mapped out.
   A write-only variable is a signal that the result is discarded.
   Expected finding: semantic.never-read-write for 'SinkOnly'.
   Expected: strict syntax-check passes; analyzer reports NEVER_READ finding. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   Source: integer  := 5;
   SinkOnly: integer  := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      SinkOnly = Source + 1;

ENDDEF (*BasePicture*);
