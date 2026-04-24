"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: UnusedVariable"
(* SEMANTIC: A local variable is declared but never referenced in any equation,
   sequence, graphic, or parameter mapping.
   Expected finding: semantic.unused-variable for 'DeadCounter'.
   Expected: strict syntax-check passes; analyzer reports UNUSED finding. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   ActiveCount: integer  := 0;
   DeadCounter: integer  := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      ActiveCount = ActiveCount + 1;

ENDDEF (*BasePicture*);
