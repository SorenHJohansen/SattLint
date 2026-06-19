"Syntax version 2.23, date: 2026-06-19-13:30:36.856 N"
"Original file date: ---"
"Program date: 2026-06-19-13:30:36.856, name: Test"
(* Denne programenhed er oprettet 2026-04-30 14:57 af sqhj. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 355036303
LOCALVARIABLES
   DefaultPath: string Const := "+ToggleParWindow";
   Counter: integer ;
   PathOK, PathNotOK: identstring  := "";
   OprPathIndex: integer  := 0;
   si0, si1, si2, si3, si4, si5, si6, si7, si8, si9, si10, si11, si12, si13,
   si14, si15, si16, siNot, siNot2, siNot3, siNot4, siNot5: integer ;


ModuleDef
ClippingBounds = ( -10.0 , -10.0 ) ( 10.0 , 10.0 )
ZoomLimits = 0.0 0.01

ModuleCode
EQUATIONBLOCK Start_SetStrings COORD -0.14, -0.28 OBJSIZE 1.4, 0.78 :
   (* No overflow *);
   ClearString(PathOK);
   InsertString(PathOK, DefaultPath, 1, si0);
   InsertString(PathOK, DefaultPath, 1, si1);
   InsertString(PathOK, DefaultPath, 1, si2);
   InsertString(PathOK, DefaultPath, 1, si3);
   InsertString(PathOK, DefaultPath, 1, si4);
   InsertString(PathOK, DefaultPath, 1, si5);
   InsertString(PathOK, DefaultPath, 1, si6);
   InsertString(PathOK, DefaultPath, 1, si7);
   InsertString(PathOK, DefaultPath, 1, si8);
   InsertString(PathOK, DefaultPath, 1, si9);
   InsertString(PathOK, DefaultPath, 1, si10);
   InsertString(PathOK, DefaultPath, 1, si11);
   InsertString(PathOK, DefaultPath, 1, si12);
   InsertString(PathOK, DefaultPath, 1, si13);
   InsertString(PathOK, DefaultPath, 1, si14);
   (* OverFlow *);
   ClearString(PathNotOK);
   InsertString(PathNotOK, DefaultPath, 1, si0);
   InsertString(PathNotOK, DefaultPath, 1, si1);
   InsertString(PathNotOK, DefaultPath, 1, si2);
   InsertString(PathNotOK, DefaultPath, 1, si3);
   InsertString(PathNotOK, DefaultPath, 1, si4);
   InsertString(PathNotOK, DefaultPath, 1, si5);
   InsertString(PathNotOK, DefaultPath, 1, si6);
   InsertString(PathNotOK, DefaultPath, 1, si7);
   InsertString(PathNotOK, DefaultPath, 1, si8);
   InsertString(PathNotOK, DefaultPath, 1, si9);
   InsertString(PathNotOK, DefaultPath, 1, si10);
   InsertString(PathNotOK, DefaultPath, 1, si11);
   InsertString(PathNotOK, DefaultPath, 1, si12);
   InsertString(PathNotOK, DefaultPath, 1, si13);
   SetStringPos(PathOK, 1, si14);
   SetStringPos(PathNotOK, 1, si15);
   Concatenate(PathOK, PathNotOK, PathNotOK, si16);

ENDDEF (*BasePicture*);
