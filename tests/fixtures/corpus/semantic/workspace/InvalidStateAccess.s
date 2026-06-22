"Syntax version 2.23, date: 2026-06-22-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-22-12:00:00.000, name: InvalidStateAccess"
(* SEMANTIC: :Old is used on a nested record leaf that is not declared State.
   Expected: semantic.invalid-state-access. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   RegressionType = RECORD DateCode_ 1
      Running: boolean  := False;
      Spare: boolean  := False;
   ENDDEF
    (*RegressionType*);

   StateBoxType = RECORD DateCode_ 1
      Regression: RegressionType ;
      Enabled: boolean  := False;
   ENDDEF
    (*StateBoxType*);

LOCALVARIABLES
   StateBox: StateBoxType ;
   Output: boolean  := False;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
   StateBox.Regression.Running = True;
   Output = StateBox.Regression.Running:Old;

ENDDEF (*BasePicture*);
