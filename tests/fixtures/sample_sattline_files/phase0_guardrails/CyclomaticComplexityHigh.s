"Syntax version 2.23, date: 2026-04-22-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-22-12:00:00.000, name: CyclomaticComplexityHigh"

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
   Cond0, Cond1, Cond2, Cond3, Cond4: boolean := False;
   Cond5, Cond6, Cond7, Cond8, Cond9: boolean := False;
   Output: integer := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      IF Cond0 THEN
         Output = 0;
      ENDIF;
      IF Cond1 THEN
         Output = 1;
      ENDIF;
      IF Cond2 THEN
         Output = 2;
      ENDIF;
      IF Cond3 THEN
         Output = 3;
      ENDIF;
      IF Cond4 THEN
         Output = 4;
      ENDIF;
      IF Cond5 THEN
         Output = 5;
      ENDIF;
      IF Cond6 THEN
         Output = 6;
      ENDIF;
      IF Cond7 THEN
         Output = 7;
      ENDIF;
      IF Cond8 THEN
         Output = 8;
      ENDIF;
      IF Cond9 THEN
         Output = 9;
      ENDIF;

ENDDEF (*BasePicture*);