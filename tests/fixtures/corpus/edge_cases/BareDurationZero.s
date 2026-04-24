"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: BareDurationZero"
(* Covers bare "0" as a duration init value — the plain-seconds boundary form.
   In SattLine a duration may be initialized with a bare quoted string that is
   purely the digit "0" without a unit suffix. This is the edge case because
   "0" could in principle be ambiguous with a bare integer, but the preprocess
   step handles it as zero seconds.
   Expected: strict syntax-check passes (same as DurZero in DurationAndTime.s). *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   ZeroDur: duration  := "0";
   ZeroFull: duration  := Duration_Value "0d0h0m0s0ms";
   Sink: boolean  := False;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Sink = ZeroDur == ZeroFull;

ENDDEF (*BasePicture*);
