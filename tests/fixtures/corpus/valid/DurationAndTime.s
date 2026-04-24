"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: DurationAndTime"
(* Covers duration and time variable declarations and usage.
   Both the Duration_Value form and bare quoted duration strings are valid.
   Both the Time_Value form and bare ISO timestamp strings are valid.
   Expected: strict syntax-check passes. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   DurFull: duration  := Duration_Value "0d0h5m0s0ms";
   DurBare: duration  := "7m6s123ms";
   DurHours: duration  := "1h";
   DurMinutes: duration  := "4m";
   DurComplex: duration  := "5d5h3m6.5s";
   DurSeconds: duration  := "12.345";
   DurZero: duration  := "0";
   DurNegative: duration  := Duration_Value "-0d0h5m0s0ms";
   TimeFull: time  := Time_Value "1984-01-01-00:00:00.000";
   TimeBare: time  := "2026-04-23-12:00:00.000";
   TimeMidnight: time  := "2000-12-31-23:59:59.999";
   Sink: boolean  := False;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Sink = DurFull == DurBare OR TimeFull == TimeBare OR DurZero == DurHours;

ENDDEF (*BasePicture*);
