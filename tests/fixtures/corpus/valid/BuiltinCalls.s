"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: BuiltinCalls"
(* Covers built-in function and procedure calls:
   - CopyVariable(src, dst, status) for whole-record copy
   - Equal(a, b) function returning boolean
   - SetStringPos / GetStringPos on a CONST string (allowed by validation)
   - Arithmetic built-ins: MaxLim
   Expected: strict syntax-check passes.
   Note: SetStringPos and GetStringPos on Const string are intentionally allowed. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   DataBlock = RECORD DateCode_ 1
      Value: integer  := 0;
      Flag: boolean  := False;
   ENDDEF
    (*DataBlock*);

LOCALVARIABLES
   Source: DataBlock ;
   Dest: DataBlock ;
   CopyStatus: integer  := 0;
   IsEqual: boolean  := False;
   A, B: integer  := 0;
   StrLen: integer  := 0;
   CursorPos: integer  := 0;
   Template: string Const  := "Template";
   Buffer: string  := "";
   StrStatus: integer  := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      CopyVariable(Source, Dest, CopyStatus);
      IsEqual = Equal(A, B);
      StrLen = StringLength(Buffer);
      SetStringPos(Template, CursorPos, StrStatus);
      StrLen = GetStringPos(Template);
      CopyString(Template, Buffer, StrStatus);

ENDDEF (*BasePicture*);
