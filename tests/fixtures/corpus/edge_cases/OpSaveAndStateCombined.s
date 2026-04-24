"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: OpSaveAndStateCombined"
(* Covers a variable declared with both OpSave and State modifiers.
   The grammar allows any combination of CONST, STATE, OPSAVE, SECURE modifiers
   in a variable group. OpSave causes the value to be restored on power-up,
   State enables :Old / :New access. Combining them is valid.
   Expected: strict syntax-check passes. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   NormalVar: integer  := 0;
   SavedVar: integer  OpSave := 0;
   StateVar: integer  State := 0;
   SavedStateVar: integer  OpSave State := 0;
   SavedStateBool: boolean  OpSave State := False;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      NormalVar = NormalVar + 1;
      SavedVar = SavedVar + 1;
      StateVar = StateVar + 1;
      SavedStateVar = SavedStateVar + 1;
      IF SavedStateBool:Old AND NOT SavedStateBool:New THEN
         NormalVar = 0;
      ENDIF;

ENDDEF (*BasePicture*);
