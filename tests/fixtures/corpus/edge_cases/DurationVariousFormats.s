"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: DurationVariousFormats"
(* EDGE CASE: All documented valid duration literal forms in one file.
   Covers bare quoted duration strings in every supported format variation
   plus the Duration_Value wrapper form and negative duration.
   All forms must pass strict validation without error.
   Expected: strict syntax-check passes. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   (* Duration_Value wrapper form *)
   D01: duration  := Duration_Value "0d0h0m0s0ms";
   D02: duration  := Duration_Value "1d2h3m4s500ms";
   D03: duration  := Duration_Value "-0d0h5m0s0ms";

   (* Bare short forms: hours, minutes *)
   D04: duration  := "1h";
   D05: duration  := "4m";
   D06: duration  := "30s";

   (* Bare combined forms *)
   D07: duration  := "7m6s123ms";
   D08: duration  := "5d5h3m6.5s";
   D09: duration  := "1h30m";
   D10: duration  := "2h15m30s";

   (* Plain-second forms (decimal seconds) *)
   D11: duration  := "12.345";
   D12: duration  := "0";
   D13: duration  := "3600";

   Sink: boolean  := False;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Sink = D01 == D02 OR D03 == D04 OR D05 == D06 OR D07 == D08 OR
             D09 == D10 OR D11 == D12 OR D13 == D01;

ENDDEF (*BasePicture*);
