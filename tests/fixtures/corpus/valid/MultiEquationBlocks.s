"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: MultiEquationBlocks"
(* Covers multiple EQUATIONBLOCK sections in one ModuleCode.
   The grammar allows any number of named EQUATIONBLOCK sections, each with
   its own COORD and OBJSIZE and its own list of statements. Each block is
   independently laid out in the graphical editor.
   Expected: strict syntax-check passes. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   RawA: real  := 0.0;
   RawB: real  := 0.0;
   Scaled: real  := 0.0;
   Output: boolean  := False;
   Accumulator: real  := 0.0;
   Count: integer  := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Inputs COORD 0.0, 0.0 OBJSIZE 0.4, 0.5 :
      Scaled = RawA + RawB;

   EQUATIONBLOCK Logic COORD 0.5, 0.0 OBJSIZE 0.5, 0.5 :
      IF Scaled > 100.0 THEN
         Output = True;
      ELSE
         Output = False;
      ENDIF;

   EQUATIONBLOCK Accum COORD 0.0, 0.5 OBJSIZE 0.4, 0.5 :
      IF Output THEN
         Accumulator = Accumulator + Scaled;
         Count = Count + 1;
      ENDIF;

   EQUATIONBLOCK Status COORD 0.5, 0.5 OBJSIZE 0.5, 0.5 :
      (* This block intentionally left with no statements to test empty block *)

ENDDEF (*BasePicture*);
