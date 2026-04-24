"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: QuotedIdentifierMaxLength"
(* EDGE CASE: A quoted identifier with exactly 20 characters in its body
   (not counting the surrounding single quotes).
   20 characters is the maximum allowed length; 21 or more characters cause
   the parser to raise UnexpectedCharacters.
   This fixture verifies the 20-character boundary is accepted.
   Expected: strict syntax-check passes. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   'ExactlyTwentyChars': integer  := 0;
   'Max20CharName12345': integer  := 1;
   Sink: integer  := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      'ExactlyTwentyChars' = 'ExactlyTwentyChars' + 1;
      'Max20CharName12345' = 'Max20CharName12345' + 1;
      Sink = 'ExactlyTwentyChars' + 'Max20CharName12345';

ENDDEF (*BasePicture*);
