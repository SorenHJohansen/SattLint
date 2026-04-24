"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: BuiltinWrongArity"
(* INVALID: A builtin function called with the wrong number of arguments.
   EqualStrings expects exactly 3 arguments (String1, String2, CaseSensitive)
   but this call provides only 2.
   Expected: strict syntax-check fails at stage "validation". *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   Name1: string  := "";
   Name2: string  := "";
   Match: boolean  := False;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Match = EqualStrings(Name1, Name2);

ENDDEF (*BasePicture*);
