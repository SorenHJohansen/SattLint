"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: VariableModifiers"
(* Exercises the three variable modifiers: Const, State, OpSave.
   Const variables may not be written in equations.
   State variables support :Old / :New temporal access.
   OpSave variables persist operator-set values across restarts.
   Expected: strict syntax-check passes. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   MaxLimit: integer Const  := 100;
   ActiveFlag: boolean State  := False;
   OperatorSetpoint: real OpSave  := 50.0;
   Output: integer  := 0;
   Changed: boolean  := False;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      IF OperatorSetpoint > MaxLimit THEN
         Output = MaxLimit;
      ELSE
         Output = OperatorSetpoint;
      ENDIF;
      Changed = ActiveFlag:New AND NOT ActiveFlag:Old;

ENDDEF (*BasePicture*);
