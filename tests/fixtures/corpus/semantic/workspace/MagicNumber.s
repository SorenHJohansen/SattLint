"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: MagicNumber"
(* SEMANTIC: Several equations use unexplained numeric literals (magic numbers)
   directly in the code. The values 3600, 0.95, and 100 appear with no named
   constant explaining their meaning.
   Expected finding: semantic.magic-number for each unexplained literal.
   Expected: strict syntax-check passes; variables analyzer reports MAGIC_NUMBER. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   RawInput: real  := 0.0;
   Scaled: real  := 0.0;
   Counter: integer  := 0;
   ElapsedSeconds: integer  := 0;
   HoursElapsed: integer  := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      (* Scale raw input — 0.95 and 100.0 are magic numbers *)
      Scaled = RawInput * 0.95 + 100.0;
      (* Convert seconds to hours — 3600 is a magic number *)
      Counter = Counter + 1;
      ElapsedSeconds = Counter;
      HoursElapsed = ElapsedSeconds / 3600;

ENDDEF (*BasePicture*);
