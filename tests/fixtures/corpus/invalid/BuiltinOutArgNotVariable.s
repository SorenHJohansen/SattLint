"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: BuiltinOutArgNotVariable"
(* INVALID: An 'out' builtin parameter receives an expression rather than
   a plain variable reference.
   CopyTime requires both arguments to be variable references because arg 2
   has direction 'out'. Passing a ternary IF expression for an out argument
   is rejected because the runtime cannot write back to an expression.
   Expected: strict syntax-check fails at stage "validation". *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   SourceTime: time  := "2026-01-01-00:00:00.000";
   DestinationA: time  := "2026-01-01-00:00:00.000";
   DestinationB: time  := "2026-01-01-00:00:00.000";
   UseA: boolean  := True;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      CopyTime(SourceTime, IF UseA THEN DestinationA ELSE DestinationB ENDIF);

ENDDEF (*BasePicture*);
