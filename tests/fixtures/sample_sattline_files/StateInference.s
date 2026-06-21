"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: StateInference"
(* Covers state_inference.condition_always_true, condition_always_false,
   unreachable_branch. These are NOT semantic.* IDs but state_inference.* kinds. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   AlwaysOne: integer  := 1;
   Input: integer  := 0;
   Output: integer  := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      IF AlwaysOne == 1 THEN
         Output = Input;
      ELSE
         Output = 0;
      ENDIF;

ENDDEF (*BasePicture*);
