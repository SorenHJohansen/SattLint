"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: CoordInvarTail"
(* Edge case: invariant/coord tail syntax — expression branch.
   Grammar rule: coord_invar_tail expression alternative. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   Target: integer  := 0;
   Source: integer  := 10;

ModuleDef
ClippingBounds = ( -1.0 : (Source + 1) , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Target = Source;

ENDDEF (*BasePicture*);
