"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: VarQualityIssues"
(* Covers UI_ONLY, PROCEDURE_STATUS, WRITE_WITHOUT_EFFECT, GLOBAL_SCOPE_MINIMIZATION.
   Each kind has one triggering variable and one clean variable that does not trigger.
   Expected: strict syntax-check passes. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   DisplayValue: integer  := 0;
   ReadValue: integer  := 0;
   StatusWord: integer  := 0;
   ActiveStatus: integer  := 0;
   UnusedWrite: integer  := 0;
   EffectWrite: integer  := 0;
   GlobalFlag: boolean  := False;
   LocalFlag: boolean  := False;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      DisplayValue = ReadValue + 1;
      StatusWord = StatusWord + 1;
      ActiveStatus = ActiveStatus + 2;
      UnusedWrite = 5;
      EffectWrite = ReadValue + 3;
      GlobalFlag = NOT GlobalFlag;
      LocalFlag = ReadValue > 10;
      ReadValue = EffectWrite - 1;

ENDDEF (*BasePicture*);
