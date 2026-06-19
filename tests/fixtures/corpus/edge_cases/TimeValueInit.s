"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: TimeValueInit"
(* Edge case: Time_Value and Duration_Value in variable initializers.
   Grammar rule: time_value. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   StartTime: time  := Time_Value "2026-01-01-00:00:00.000";
   EndTime: time  := Time_Value "2026-12-31-23:59:59.999";
   Delay: duration  := Duration_Value "500ms";
   Timeout: duration  := Duration_Value "30s";

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

ENDDEF (*BasePicture*);
