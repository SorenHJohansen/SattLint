"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: KeywordPrefixedIdentifiers"
(* EDGE CASE: Identifiers that begin with or contain SattLine keywords are valid.
   Keywords like IF, AND, NOT, OR, THEN, ELSE are only tokenized as standalone words.
   A name like "IFState", "ANDFailed", "NOTOGActive", "THENFlag", "ORResult",
   "ThenValue", or "ElseValue" is a perfectly legal identifier.
   Expected: strict syntax-check passes. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   IFState: boolean  := False;
   ANDFailed: boolean  := False;
   NOTOGActive: boolean  := True;
   THENFlag: boolean  := False;
   ORResult: boolean  := False;
   ThenValue: integer  := 10;
   ElseValue: integer  := 20;
   Output: integer  := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      IFState = NOTOGActive AND NOT ANDFailed;
      ORResult = IFState OR THENFlag;
      Output = IF IFState THEN ThenValue ELSE ElseValue ENDIF;

ENDDEF (*BasePicture*);
