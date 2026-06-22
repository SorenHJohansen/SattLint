"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: NumericConstraints"
(* SEMANTIC: Visible Min_/Max_ bounds should constrain assignments.
   Expected findings include the numeric-constraints semantic rule. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   Min_Output: integer  := 0;
   Max_Output: integer  := 10;
   Output: integer  := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      IF Output < Min_Output THEN
         Output = Min_Output;
      ENDIF;
      IF Output > Max_Output THEN
         Output = Max_Output;
      ENDIF;
      Output = 12;
      IF Output > Max_Output THEN
         Output = Output;
      ENDIF;

ENDDEF (*BasePicture*);
