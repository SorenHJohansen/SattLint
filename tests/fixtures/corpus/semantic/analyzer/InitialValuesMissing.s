"Syntax version 2.23, date: 2026-06-22-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-22-12:00:00.000, name: InitialValuesMissing"
(* Dedicated initial-values analyzer fixture. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   RecParReal = MODULEDEFINITION DateCode_ 1
   MODULEPARAMETERS
      Value: real;
      MinValue: real := 0.0;
      MaxValue: real := 100.0;
   LOCALVARIABLES
      Active: boolean  := False;
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ModuleCode
   EQUATIONBLOCK Eq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Active = Value > MinValue;
   ENDDEF (*RecParReal*);

SUBMODULES
   RecipeSP Invocation
      ( 0.0 , 0.0 , 0.0 , 0.5 , 0.5
       ) : RecParReal (
      MinValue => 0.0,
      MaxValue => 100.0);

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

ENDDEF (*BasePicture*);
