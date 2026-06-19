"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: UnicodeIdentifiers"
(* Edge case: identifiers with extended Latin / accented characters.
   Grammar rule: identifier Unicode support. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   Temperature: integer  := 0;
   Débit: integer  := 0;
   Überdruck: integer  := 0;
   Resultado: integer  := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Débit = Temperature + Überdruck;
      Resultado = Débit;

ENDDEF (*BasePicture*);
