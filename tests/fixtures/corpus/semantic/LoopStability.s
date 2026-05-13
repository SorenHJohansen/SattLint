"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: LoopStability"
(* SEMANTIC: Conflicting literal writes to the same setpoint in one scope.
   Expected findings include the loop-stability semantic rule. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   Setpoint: integer  := 0;
   Output: integer  := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Control COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Setpoint = 10;
      Setpoint = 20;
      Output = Setpoint;

ENDDEF (*BasePicture*);
