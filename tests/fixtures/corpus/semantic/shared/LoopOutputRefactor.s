"Syntax version 2.23, date: 2026-06-22-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-22-12:00:00.000, name: LoopOutputRefactor"
(* Direct analyzer fixture for sorting.loop_output_refactor. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   A: integer  := 0;
   B: integer  := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Input COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      A = B;
   EQUATIONBLOCK Feedback COORD 1.0, 0.0 OBJSIZE 1.0, 1.0 :
      B = A;

ENDDEF (*BasePicture*);
