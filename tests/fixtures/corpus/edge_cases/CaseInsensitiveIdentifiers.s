"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: CaseInsensitiveIdentifiers"
(* Covers case-insensitive identifier matching.
   SattLine identifiers compare case-insensitively via casefold().
   A single variable 'counter' is declared and then accessed in three
   different case forms in the same equation block — all refer to the
   same variable, so the last assignment wins each scan cycle.
   Expected: strict syntax-check passes. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   counter: integer  := 0;
   Output: integer  := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      counter = counter + 1;
      Counter = Counter + 10;
      COUNTER = COUNTER + 100;
      Output = counter;

ENDDEF (*BasePicture*);
