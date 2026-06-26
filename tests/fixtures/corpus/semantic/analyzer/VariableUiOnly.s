"Syntax version 2.23, date: 2026-06-25-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-25-12:00:00.000, name: VariableUiOnly"
(* Covers UI_ONLY_VARIABLE. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   DisplayValue: integer  := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
GraphObjects :
   TextObject ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
      "Value" VarName Width_ = 5 : InVar_ "DisplayValue"

ENDDEF (*BasePicture*);
