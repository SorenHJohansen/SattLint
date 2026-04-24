"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: NegativeDurationValue"
(* Covers negative duration initialization using the Duration_Value form.
   A negative duration represents a time-in-the-past or reverse elapsed-time.
   The Duration_Value form with a leading minus is the documented way to
   express negative durations; the sign applies to the whole value.
   Expected: strict syntax-check passes. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   NegFive: duration  := Duration_Value "-0d0h5m0s0ms";
   NegHour: duration  := Duration_Value "-1d0h0m0s0ms";
   NegSmall: duration  := Duration_Value "-0d0h0m30s500ms";
   Sink: boolean  := False;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Sink = NegFive == NegHour OR NegSmall == NegFive;

ENDDEF (*BasePicture*);
