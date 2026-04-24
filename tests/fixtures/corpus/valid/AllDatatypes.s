"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: AllDatatypes"
(* Covers all six built-in scalar datatypes as local variables with init values.
   Also exercises positive, negative, and zero literals.
   Expected: strict syntax-check passes; all variables used. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   IntPos: integer  := 100;
   IntNeg: integer  := -42;
   IntZero: integer  := 0;
   RealPos: real  := 1.5;
   RealNeg: real  := -0.5;
   RealZero: real  := 0.0;
   BoolTrue: boolean  := True;
   BoolFalse: boolean  := False;
   StrVar: string  := "Hello World";
   StrEmpty: string  := "";
   CopyStatus: integer  := 0;
   DurVar: duration  := Duration_Value "0d1h30m0s0ms";
   TimeVar: time  := Time_Value "2026-01-01-00:00:00.000";
   SinkInt: integer  := 0;
   SinkReal: real  := 0.0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      SinkInt = IntPos + IntNeg + IntZero;
      SinkReal = RealPos + RealNeg + RealZero;
      BoolTrue = NOT BoolFalse;
      CopyString(StrEmpty, StrVar, CopyStatus);

ENDDEF (*BasePicture*);
