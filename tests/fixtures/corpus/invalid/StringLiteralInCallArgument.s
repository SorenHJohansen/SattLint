"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: StringLiteralInCallArgument"
(* INVALID: A string literal used as an argument to a function call.
   String literals are rejected in module-code function or procedure call
   arguments; they are only allowed in parameter mappings (=> "literal").
   EqualStrings requires string variable references, not inline string literals.
   Expected: strict syntax-check fails at stage "validation". *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   Input: string  := "";
   IsMatch: boolean  := False;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      IsMatch = EqualStrings(Input, "Expected", True);

ENDDEF (*BasePicture*);
