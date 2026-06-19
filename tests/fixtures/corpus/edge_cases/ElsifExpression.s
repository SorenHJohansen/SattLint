"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: ElsifExpr"
(* Edge case: ELSIF in a ternary-like expression inside equation block.
   Grammar rules: ternary_if / ELSIF. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   Mode: integer  := 0;
   Output: integer  := 0;
   Result: integer  := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      IF Mode = 1 THEN
         Output = 10;
      ELSIF Mode = 2 THEN
         Output = 20;
      ELSIF Mode = 3 THEN
         Output = 30;
      ELSE
         Output = 0;
      ENDIF;
      Result = Output + 1;

ENDDEF (*BasePicture*);
