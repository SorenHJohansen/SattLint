"Syntax version 2.23, date: 2026-06-19-12:41:09.218 N"
"Original file date: ---"
"Program date: 2026-06-19-12:41:09.218, name: Test"
(* Denne programenhed er oprettet 2026-04-30 14:57 af sqhj. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 333375086
LOCALVARIABLES
   DefaultPath: string Const := "+ToggleParWindow";
   Counter: integer ;
   PathOK, PathNotOK: string  := "";
   OprPathIndex: integer  := 0;
   si, si2, si3, si4, si5, siNot, siNot2, siNot3, siNot4, siNot5: integer ;
SUBMODULES
   ToggleParWindow Invocation
      ( -0.24 , 0.58 , 0.0 , 0.6 , 0.44
       ) : MODULEDEFINITION DateCode_ 307677188
   MODULEPARAMETERS
      Path "Path to pop-up module": string  := "--ParDisplay+++Form";
      RelativePos: boolean  := False;
      Info "IN Optional information (HMI only)": identstring  := "";
      WindowTitle "IN Optional WindowTitle": string  := "";
      xPos: real  := 0.3;
      yPos: real  := 0.2;
      xSize: real  := 0.33;
      Enable "IN Interaction possible on Enable AND EnablePrivilege",
      EnablePrivilege "IN Interaction possible on Enable AND EnablePrivilege":
      boolean  := True;
   LOCALVARIABLES
      ShowInfo "Enable Info text on button": boolean ;
   SUBMODULES
      FM1 Invocation
         ( 0.5 , 0.5 , 0.0 , 0.5 , 0.5
          ) : MODULEDEFINITION DateCode_ 307663975 ( Frame_Module )


      ModuleDef
      ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
      GraphObjects :
         TextObject ( -1.0 , -1.0 ) ( 1.0 , 0.3 )
            "Info" VarName Width_ = 5  ValueFraction = 2
            OutlineColour : Colour0 = -3

      ENDDEF (*FM1*);


   ModuleDef
   ClippingBounds = ( 0.0 , 1.49012E-08 ) ( 1.0 , 1.0 )
   GraphObjects :
      TextObject ( 0.035 , 0.035 ) ( 0.035 , 0.11 )
         "1" LeftAligned
         Enable_ = True : InVar_ False
         OutlineColour : Colour0 = -3
      RectangleObject ( 5.96046E-08 , 1.49012E-08 )
         ( 1.0 , 1.0 )
         OutlineColour : Colour0 = 5
   InteractObjects :
      ComButProc_ ( 1.49012E-08 , -2.98023E-08 )
         ( 1.0 , 1.0 )
         ToggleWindow
         "" : InVar_ "Path" "" : InVar_ "WindowTitle" False : InVar_
         "RelativePos" 0.0 : InVar_ "XPos" 0.0 : InVar_ "YPos" 0.0 : InVar_
         "XSize" 0.0 False 0 0 False 0
         Enable_ = True : (EnablePrivilege AND Enable) Variable = 0.0
         TextObject = "" : InVar_ LitString "+"


   ModuleCode
   EQUATIONBLOCK Start_Init COORD -1.60187E-07, 2.38419E-07 OBJSIZE 1.0, 0.14 :
      ShowInfo = StringLength(Info) > 0;

   ENDDEF (*ToggleParWindow*);


ModuleDef
ClippingBounds = ( -10.0 , -10.0 ) ( 10.0 , 10.0 )
ZoomLimits = 0.0 0.01
GraphObjects :
   CompositeObject

ModuleCode
EQUATIONBLOCK Start_SetStrings COORD -0.14, -0.28 OBJSIZE 1.4, 0.78 :
   (* Path OK *);
   CopyString(DefaultPath, PathOK, si);
   SetStringPos(PathOK, 1, si2);
   InsertString(PathOK, DefaultPath, 2, si3);
   SetStringPos(PathOK, GetStringPos(PathOK) - 2, si4);
   CutString(PathOK, 2, si5);
   (* Path NOT OK *);
   (* Results in the string "+T+ToggleParWindow" *);
   CopyString(DefaultPath, PathNotOK, siNot);
   SetStringPos(PathNotOK, 1, siNot2);
   InsertString(PathNotOK, DefaultPath, 2, siNot3);
EQUATIONBLOCK Counter COORD 1.26, -0.28 OBJSIZE 1.4, 0.78 :
   Counter = Counter + 1;
   IF Counter > 2 THEN
      Counter = 0;
   ENDIF;
   OprPathIndex = Counter;

ENDDEF (*BasePicture*);
