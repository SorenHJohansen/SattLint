"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: ConstStringSetGetPos"
(* EDGE CASE: SetStringPos and GetStringPos on a CONST string variable.
   These builtins adjust the cursor position on the string buffer rather than
   writing string contents, so they are explicitly allowed on Const strings
   by validation (unlike regular string writes which would be rejected).
   Expected: strict syntax-check passes despite the Const modifier. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   TemplateName: string Const  := "Template:Row";
   CursorPos: integer  := 0;
   ReadStatus: integer  := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      SetStringPos(TemplateName, CursorPos, ReadStatus);
      ReadStatus = GetStringPos(TemplateName);

ENDDEF (*BasePicture*);
