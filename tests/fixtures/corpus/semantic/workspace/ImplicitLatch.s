"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: ImplicitLatch"
(* SEMANTIC: A boolean variable is written only in the THEN branch of an
   IF/THEN/ENDIF statement. When the condition is False the variable retains
   its previous value, creating an implicit latch (unintended memory).
   Expected finding: semantic.implicit-latch for 'ActiveLed'.
   Expected: strict syntax-check passes; variables analyzer reports IMPLICIT_LATCH. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   Condition: boolean  := False;
   ActiveLed: boolean  := False;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      IF Condition THEN
         ActiveLed = True;
      ENDIF;

ENDDEF (*BasePicture*);
