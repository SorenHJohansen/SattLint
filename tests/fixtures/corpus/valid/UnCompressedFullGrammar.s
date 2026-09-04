"Syntax version 2.23, date: 2026-08-27-18:41:22.140 N"
"Original file date: ---"
"Program date: 2026-08-27-18:41:22.140, name: TestCompress"
(* Denne programenhed er oprettet 2026-08-25 11:12 af sqhj. *)

BasePicture
(* ModuleTypeDescription *)
 Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 280432068
TYPEDEFINITIONS
   TestRecord """Description of TestRecord""" = RECORD DateCode_ 136786209
      FieldBool """Description""": boolean Secure := False;
      FieldInt: integer OpSave := 0;
      FieldReal: real  := 0.0;
      FieldBool2: boolean State;
      FieldReal2: real Const;
   ENDDEF
    (*TestRecord*);

   TestRecord2 = RECORD DateCode_ 187731400
      TestField: boolean ;
      TestField2: integer ;
   ENDDEF
    (*TestRecord2*);

TYPEDEFINITIONS
   TestModuleType
   (* ModuleTypeDescription *)
    = MODULEDEFINITION DateCode_ 189212200 ( GroupConn = ScanGroupVar )
   LOCALVARIABLES
      ScanGroupVar: GroupData ;


   ModuleDef
   ClippingBounds = ( -1.0 , -0.619048 ) ( 1.0 , 0.619048 )
   Two_Layers_ LayerLimit_ = 0.5
   ZoomLimits = 2.0 1.0
   Zoomable
   GraphObjects :
      RectangleObject ( -0.8 , 0.42 ) ( -0.32 , 0.2 )
         Layer_ = 1
         OutlineColour : Colour0 = -3
      RectangleObject ( -0.7 , 0.14 ) ( -0.22 , -0.08 )
         Layer_ = 2
         OutlineColour : Colour0 = -3
      RectangleObject ( -0.7 , -0.26 ) ( -0.22 , -0.48 )
         OutlineColour : Colour0 = -3

   ENDDEF (*TestModuleType*);

   PrivateModule = PRIVATE_ MODULEDEFINITION DateCode_ 140177729


   ModuleDef
   ClippingBounds = ( -1.0 , -0.833333 ) ( 1.0 , 0.833333 )

   ENDDEF (*PrivateModule*);

LOCALVARIABLES
   StateVar "Test": boolean State := False;
   abstrinreal, maxreal, minreal, var3: real ;
   abstrin, var2: integer ;
   alttekst: string ;
   var1: boolean ;
   fuldnavn2, brugerident2: string ;
   signafbrudt, aktiver2: boolean ;
   afbrydkommentar: string ;
   aktiverdobbelt: boolean ;
   fuldnavn1, brugerident1, kommentar, formål: string ;
   aktiverenkelt: boolean ;
   realVar2, RealVar1: real ;
   IntVar2, IntVar, nooforws: integer ;
   readolny, wdisplayed: boolean ;
   wtitle, Mpath: string ;
   RelPos, markeret, Tag_Global: boolean ;
   absoluttrin, max, min: integer ;
   Fortryd, OK: boolean ;
   klasse, vigtighedsgrad: integer ;
   beskrivelse: string ;
   ændret, hroot: boolean ;
   synlig: boolean  := True;
   tekst: string ;
   windowdisplayed: boolean ;
   timeout: integer ;
   hierarchicroot: boolean ;
   ysize, xsize: real ;
   WindowTitle: string ;
   SelectClass: integer ;
   ModulePath: string ;
   RotationMax, RotateionMin, RotationVar, YScaleMax, YScaleMin, YScale,
   XScaleMax, XScaleMin, XScale: real ;
   InPicture, Dim: boolean ;
   YMax, YMin: real ;
   YVar: real Secure;
   XMax, XMin, XVar, RefPosition: real ;
   ColorMix: boolean ;
   AltLineColor: integer ;
   BGColorMix, Update, RelTime: boolean ;
   TimeShift: Duration ;
   HelpLines, ValidCurve: boolean ;
   FillAmount: real ;
   CurveComplete: boolean ;
   ShownSamples, StateCurve: integer ;
   LastPoint, FirstPoint: Time ;
   BiasSamples: integer ;
   Position: real ;
   LineColor, AreaColor: integer ;
   StartTime: Time ;
   JourTag, JourName, RemoteSysIdent: string ;
   ActivateJournal: boolean ;
   Decimals, NrOfPoints: integer ;
   Unit: string ;
   LowScale, HighScale: real ;
   Button_Global: boolean ;
   Button: string ;
   Enable: boolean  := True;
   Value, InteractVar: boolean ;
   Class, Importance: integer ;
   Tag, Description: string ;
   ColorChoice: boolean ;
   AltTextColor: integer ;
   ColorChoice2: boolean ;
   AltBGColor, TextColor, BGColor, LineThicknessVar: integer ;
   AreaColorMix: real ;
   UserName1: string ;
   Changed, Activate, Visible: boolean ;
   Text: string ;
   Status, FontSize, FontKind, NoOfColumns, NoOfRows: integer ;
   RelativePos: boolean ;
   YPos, XPos: real ;
   ReadOnly: boolean ;
   FileName, UserName2, UserIdentity2: string ;
   SignAborted, ActivateNr2: boolean ;
   AbortComment: string ;
   ActivateSecond: boolean ;
   UserName, Useridentity, Comment, Purpose: string ;
   Aktivate_Single, Change, Marked, Tast_global: boolean ;
   Tast: string ;
   Aktiver: boolean  := True;
   Interaction: boolean ;
   IndexVar: integer ;
   DefaultPath: string ;
   ResetVar: integer ;
   Test, StateVarAccess, OffLit, BoolFalseLit, OnLit, BoolLit, BoolVar: boolean
   ;
   NodeVar2, NodeVar: Integer ;
   LineColorMixVar "Test comment in description (* test *)", AreaColorMixVar
   "Test #6? in description": real ;
   AltAreaColorVar, AreaColorVar: integer ;
   EnableVar: boolean ;
   ColorMixVar: real ;
   AltLineColorVar, LineColorVar: integer ;
   IntVari: integer  := 1;
   RealVari: real  := 2.0;
   StringVari: string  := "Test";
   IdentstringVar: identstring  := "012345678912345";
   IdentstringVarConst: identstring Const := "012345678912345";
   TernaryInt, WidthVar, DecVar: integer ;
   TimeVar: Time ;
   DurationVar: Duration ;
   TimeFormat: string ;
SUBMODULES
   SM1 Invocation
      ( 1.54 , -0.66 , 0.0 , 0.24 , 0.24
       ) : MODULEDEFINITION DateCode_ 169034560
   MODULEPARAMETERS
      NodeVar2: Integer ;


   ModuleDef
   ClippingBounds = ( -1.0 , -0.583333 ) ( 1.0 , 0.583333 )
   GraphObjects :
      TextObject ( -0.04 , 0.48 ) ( -0.64 , 0.28 )
         "NodeVar2"
         ConnectionNode ( -0.82 , 0.38 )
         LeftAligned
         OutlineColour : Colour0 = -3

   ENDDEF (*SM1*);

   SM2 Invocation
      ( 1.04 , 0.74 , 0.0 , 0.16 , 0.16
       SymbolModule ) : MODULEDEFINITION DateCode_ 282543324
   MODULEPARAMETERS
      TestGlobarlVar: boolean ;
   LOCALVARIABLES
      StateVar: boolean State;
      EntryCode, ActiveCodetest, ExitcodeTest: boolean ;


   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   Zoomable

   ModuleCode

   OPENSEQUENCE   COORD -1.0,-1.0 OBJSIZE 2.0,2.0
      SEQINITSTEP ST_Initstep
      SEQTRANSITION Tr1 WAIT_FOR 200 > 100
      SEQSTEP S1
      SEQTRANSITION  WAIT_FOR S1.X
      SEQSTEP S2
         ENTERCODE
            StateVar:New = StateVar:Old;
      SEQTRANSITION Tr4 WAIT_FOR StateVar
      PARALLELSEQ
         SEQSTEP S3
            ENTERCODE
               EntryCode = True;
            ACTIVECODE
               ActiveCodetest = Off;
            EXITCODE
               ExitcodeTest = On;
      PARALLELBRANCH
         SEQSTEP
      PARALLELBRANCH
         SEQSTEP S6
      ENDPARALLEL
      ALTERNATIVESEQ
         SEQTRANSITION Tr11 WAIT_FOR On
         SUBSEQSTEP Test
            PARALLELSEQ
               SEQSTEP S12
            PARALLELBRANCH
               SEQINITSTEP S13
            ENDPARALLEL
         ENDSUBSEQSTEP
         SUBSEQTRANSITION
            SUBSEQTRANSITION
               SUBSEQTRANSITION
                  ALTERNATIVESEQ
                     SEQTRANSITION Tr15 WAIT_FOR On
                  ALTERNATIVEBRANCH
                     SEQTRANSITION Tr16 WAIT_FOR On
                  ENDALTERNATIVE
                  SEQSTEP S14
                  SEQTRANSITION Tr14 WAIT_FOR On
               ENDSUBSEQTRANSITION
            ENDSUBSEQTRANSITION
         ENDSUBSEQTRANSITION
      ALTERNATIVEBRANCH
         SEQTRANSITION Tr12 WAIT_FOR On
         SUBSEQUENCE test4
            PARALLELSEQ
               SEQSTEP S10
                  SEQFORK Tr12 SEQBREAK
            PARALLELBRANCH
               SEQSTEP S11
                  SEQFORK Tr11
            ENDPARALLEL
            SEQTRANSITION Tr13 WAIT_FOR On
         ENDSUBSEQUENCE
      ENDALTERNATIVE
      SEQSTEP S9
      SEQTRANSITION Tr10 WAIT_FOR On
      PARALLELSEQ
         SEQSTEP S7
      PARALLELBRANCH
         SEQSTEP S8
      ENDPARALLEL
      ALTERNATIVESEQ
         SUBSEQTRANSITION test3
            SEQTRANSITION Tr3 WAIT_FOR On
         ENDSUBSEQTRANSITION
      ALTERNATIVEBRANCH
         SEQTRANSITION Tr8 WAIT_FOR True
            SEQFORK S2 SEQBREAK
      ALTERNATIVEBRANCH
         SEQTRANSITION Tr9 WAIT_FOR Off
            SEQFORK S3
      ENDALTERNATIVE
      SEQSTEP S5
      SUBSEQTRANSITION SubSeq
         ALTERNATIVESEQ
            ALTERNATIVESEQ
               SEQTRANSITION Tr5 WAIT_FOR True
            ALTERNATIVEBRANCH
               SEQTRANSITION Tr6 WAIT_FOR True
            ENDALTERNATIVE
         ALTERNATIVEBRANCH
            SEQTRANSITION Tr7 WAIT_FOR Off
         ENDALTERNATIVE
      ENDSUBSEQTRANSITION
   ENDOPENSEQUENCE


   ENDDEF (*SM2*) (
   TestGlobarlVar => GLOBAL BoolVar);

   SM3
   (* ModuleDescription *)
    Invocation
      ( -0.1 , -0.74 , 0.0 , 0.3 , 0.3
       IgnoreMaxModule ) : MODULEDEFINITION DateCode_ 190137640
   MODULEPARAMETERS
      IntVari: integer ;
      DefaultPar: integer  := Default;
   LOCALVARIABLES
      IntOpSave: integer OpSave;
   SUBMODULES
      SM1 Invocation
         ( -0.04 , -5.55112E-17 , 0.0 , 0.92 , 0.92
          ) : MODULEDEFINITION DateCode_ 186189000
      MODULEPARAMETERS
         IntVari: integer ;
      SUBMODULES
         SM1 Invocation
            ( 0.02 , -0.02 , 0.0 , 0.94 , 0.94
             ) : MODULEDEFINITION DateCode_ 186153400
         MODULEPARAMETERS
            IntVari: integer ;
         SUBMODULES
            SM1 Invocation
               ( 0.0 , 0.0 , 0.0 , 0.92 , 0.92
                ) : MODULEDEFINITION DateCode_ 186061520
            MODULEPARAMETERS
               BoolVar: boolean ;
               IntVari: integer ;


            ModuleDef
            ClippingBounds = ( -1.0 , -0.73913 )
            ( 1.0 , 0.73913 )

            ENDDEF (*SM1*) (
            BoolVar => GLOBAL BoolVar,
            IntVari => IntVari);


         ModuleDef
         ClippingBounds = ( -1.0 , -0.765957 ) ( 1.0 , 0.765957 )

         ENDDEF (*SM1*) (
         IntVari => IntVari);


      ModuleDef
      ClippingBounds = ( -1.0 , -0.782609 ) ( 1.0 , 0.782609 )

      ENDDEF (*SM1*) (
      IntVari => IntVari);


   ModuleDef
   ClippingBounds = ( -1.0 , -0.8 ) ( 1.0 , 0.8 )
   Zoomable

   ENDDEF (*SM3*) (
   IntVari => IntVari);

   TestModuleType1
   (* ModuleDescription *)
    Invocation
      ( 0.3 , -1.38 , 0.0 , 0.84 , 0.84
       ) : TestModuleType;

   SM4 Invocation
      ( 2.32 , -0.64 , 0.0 , 0.4 , 0.4
       LayerModule ) : MODULEDEFINITION DateCode_ 189839200


   ModuleDef
   ClippingBounds = ( -1.0 , -0.4 ) ( 1.0 , 0.4 )
   Zoomable

   ENDDEF (*SM4*);

   FM1 Invocation
      ( 3.48 : InVar_ "XVar" ClippingBounds = 3.48 3.48 0.0 : InVar_ "XMin"
       100.0 : InVar_ "XMax"  ,
        1.08 : InVar_ "YVar" ClippingBounds = 1.08 1.08 0.0 : InVar_ "YMin"
       100.0 : InVar_ "YMax"  ,
        0.0 : InVar_ "RotationVar" ClippingBounds = 0.0 0.0 0.0 : InVar_
       "RotateionMin"  100.0 : InVar_ "RotationMax"  ,
        0.36 : InVar_ "XScale" ClippingBounds = 0.36 0.36 0.0 : InVar_
       "XScaleMin"  100.0 : InVar_ "XScaleMax"  ,
        0.36 : InVar_ "YScale" ClippingBounds = 0.36 0.36 0.0 : InVar_
       "YScaleMin"  100.0 : InVar_ "YScaleMax"
       Enable_ = True : InVar_ "Enable" Dim_ = False : InVar_ "Dim"
       Module_In_View = False : OutVar_ "InPicture" ) : MODULEDEFINITION
   DateCode_ 136387689 ( Frame_Module )


   ModuleDef
   ClippingBounds = ( -1.0 , -0.444444 ) ( 1.0 , 0.444444 )

   ENDDEF (*FM1*);

   PrivateModule1 Invocation
      ( -1.16 , 1.16 , 0.0 , 0.24 , 0.24
       ) : PrivateModule;


ModuleDef
ClippingBounds = ( -10.0 , -10.0 ) ( 10.0 , 10.0 )
ZoomLimits = 0.0 0.01
Zoomable
Grid = 0.04
GraphObjects :
   TextObject ( 0.02 , 1.1 ) ( 0.02 , 1.0 )
      "TextLeft" LeftAligned
      OutlineColour : Colour0 = -3
   TextObject ( 0.56 , 1.1 ) ( 0.56 , 1.0 )
      "TextCenter"
      OutlineColour : Colour0 = -3
   TextObject ( 1.2 , 1.1 ) ( 1.2 , 1.0 )
      "TextRight" RightAligned
      OutlineColour : Colour0 = -3
   TextObject ( 1.58 , 1.1 ) ( 1.58 , 1.0 )
      "RealVari" VarName Width_ = 5 : InVar_ "WidthVar"  ValueFraction = 2 :
      InVar_ "DecVar"  RightAligned
      OutlineColour : Colour0 = -3
   TextObject ( 2.08 , 1.1 ) ( 2.08 , 1.0 )
      "TimeVar" VarName Width_ = 5  ValueFraction = 2  Format_String_ = "" :
      InVar_ "TimeFormat"  RightAligned
      OutlineColour : Colour0 = -3
   LineObject ( 1.64 , 0.9 ) ( 1.84 , 0.9 )
      Enable_ = True : InVar_ "EnableVar"
      OutlineColour : Width_ = 2 : InVar_ "LineThicknessVar" Colour0 = -3 :
      InVar_ "LineColorVar" Colour1 = -1 : InVar_ "AltLineColorVar" ColourStyle
      = 0.0 : InVar_ "ColorMixVar"
   RectangleObject ( 1.64 , 0.82 ) ( 1.84 , 0.7 )
      Enable_ = True : InVar_ "EnableVar"
      OutlineColour : Colour0 = -3 : InVar_ "LineColorVar" Colour1 = -1 :
      InVar_ "AltLineColorVar" ColourStyle = 0.0 : InVar_ "LineColorMixVar"
      FillColour : Colour0 = -1 : InVar_ "AreaColorVar" Colour1 = 9 : InVar_
      "AltAreaColorVar" ColourStyle = 0.0 : InVar_ "AreaColorMixVar"
   OvalObject ( 2.32 , 1.02 ) ( 2.7 , 0.7 )
      Enable_ = True : ( NOT EnableVar)
      OutlineColour : Colour0 = -3 : InVar_ "LineColorVar" Colour1 = -1 :
      InVar_ "AltLineColorVar" ColourStyle = 0.0 : InVar_ "ColorMixVar"
      FillColour : Colour0 = -1 : InVar_ "AreaColorVar" Colour1 = 9 : InVar_
      "AltAreaColorVar" ColourStyle = 0.0 : InVar_ "AreaColorMixVar"
   SegmentObject ( 1.08 , 1.82 ) ( 1.6 , 1.68 ) ( 1.60402 , 1.94411 )
      Enable_ = True : InVar_ "EnableVar"
      OutlineColour : Colour0 = -3 : InVar_ "LineColorVar" Colour1 = -1 :
      InVar_ "AltLineColorVar" ColourStyle = 0.0 : InVar_ "ColorMixVar"
      FillColour : Colour0 = -1 : InVar_ "AreaColorVar" Colour1 = 9 : InVar_
      "AltAreaColorVar" ColourStyle = 0.0 : InVar_ "AreaColorMix"
   PolygonObject ( 2.18 , 1.78 ) ( 1.98 , 1.48 )
      ( 2.42 , 1.48 ) ( 2.48 , 1.8 ) ( 2.16 , 1.88 )
      OutlineColour : Colour0 = -3
   CompositeObject
   CompositeObject
   CompositeObject
   CompositeObject
   CompositeObject
   TextObject ( 1.38 , -0.22 ) ( 1.66 , -0.4 )
      "NodeVar"
      ConnectionNode ( 1.26 , -0.24 )

      OutlineColour : Colour0 = -3
   PolygonObject Polyline Connection ( 1.26 , -0.24 )
      ( 1.34 , -0.58 ) ( 1.3432 , -0.5688 )
      Enable_ = True : InVar_ "Enable"
      OutlineColour : Colour0 = -3
   PolygonObject Spline ( 2.74 , 1.78 ) ( 2.54 , 1.48 )
      ( 2.98 , 1.48 )
      ( 3.04 : InVar_ "XVar" ClippingBounds = 3.04 3.04 0.0 : InVar_ "XMin"
      100.0 : InVar_ "XMax"  ,
        1.8 : InVar_ "YVar" ClippingBounds = 1.8 1.8 0.0 : InVar_ "YMin"  100.0
      : InVar_ "YMax"  ) ( 2.72 , 1.88 )
      OutlineColour : Colour0 = -3
   PolygonObject Spline Connection ( 3.38 , 1.78 )
      ( 3.18 , 1.48 ) ( 3.62 , 1.48 ) ( 3.68 , 1.8 )
      ( 3.36 , 1.88 )
      OutlineColour : Colour0 = -3
   PolygonObject Polyline Spline ( 2.22 , 2.38 )
      ( 2.02 , 2.08 ) ( 2.46 , 2.08 ) ( 2.52 , 2.4 )
      ( 2.2 , 2.48 )
      OutlineColour : Colour0 = -3
   PolygonObject Polyline ( 2.82 , 2.34 ) ( 2.62 , 2.04 )
      ( 3.06 , 2.04 ) ( 3.12 , 2.36 ) ( 2.8 , 2.44 )
      Enable_ = True : InVar_ "EnableVar"
      OutlineColour : Width_ = 1 : InVar_ "LineThicknessVar" Colour0 = -3 :
      InVar_ "LineColorVar" Colour1 = -1 : InVar_ "AltLineColorVar" ColourStyle
      = 50.0 : InVar_ "ColorMixVar"
   CompositeObject
   CompositeObject
   CompositeObject
   TextObject ( 1.46 , 0.06 ) ( 1.74 , -0.12 )
      "NodeVar"
      ConnectionNode ( 1.34 , 0.04 )
      LeftAligned
      Enable_ = True : InVar_ "Enable"
      OutlineColour : Colour0 = 34 : InVar_ "LineColor" Colour1 = 45 : InVar_
      "AltLineColor" ColourStyle = True : InVar_ "ColorMix"
      FillColour : Colour0 = 67 : InVar_ "BGColor" Colour1 = 76 : InVar_
      "AltBGColor" ColourStyle = True : InVar_ "BGColorMix"
InteractObjects :
   ComBut_ ( 0.24 , 1.58 ) ( 0.56 , 1.46 )
      Bool_Value
      Variable = True Event_Text_ = "" : InVar_ "beskrivelse" Event_Tag_ = "" :
      InVar_ "tag" Event_Severity_ = 0 : InVar_ "vigtighedsgrad" Event_Class_ =
      0 : InVar_ "klasse" ToggleAction
      Abs_
   OptBut_ ( 0.32 , 1.34 ) ( 0.54 , 1.24 )
      Bool_Value
      Enable_ = True : InVar_ "Enable" Value_Changed = False : OutVar_
      "Changed" Variable = False : OutVar_ "InteractVar" Key_ = "" : InVar_
      "Button" GLOBAL = False : InVar_ "Button_Global" Visible_ = True : InVar_
      "Visible" Value_ = False : InVar_ "Value"
      TextObject = "" : InVar_ "Text"
      SnglSgn
      Signer1_ = "" : OutVar_ "UserIdentity"
      Signer1Name_ = "" : OutVar_ "UserName"
      DblSgn
      CansCom = "" : OutVar_ "AbortComment"
      SgnCans = False : OutVar_ "SignAborted"
      Signer2_ = "" : OutVar_ "UserIdentity2"
      Signer2Name_ = "" : OutVar_ "UserName2"

      OutlineColour : Colour0 = 14 : InVar_ "TextColor" Colour1 = 24 : InVar_
      "AltTextColor" ColourStyle = True : InVar_ "ColorChoice"
      FillColour : Colour0 = -1 : InVar_ "BGColor" Colour1 = -1 : InVar_
      "AltBGColor" ColourStyle = True : InVar_ "ColorChoice2"
   CheckBox_ ( 1.02 , 1.42 ) ( 1.46 , 1.32 )
      Bool_Value
      Enable_ = True : InVar_ "aktiver" Value_Changed = False : OutVar_
      "ændret" Variable = False : OutVar_ "synlig" Key_ = "" : InVar_ "tast"
      GLOBAL = False : InVar_ "tast_global" Event_Text_ = "" : InVar_
      "Description" Event_Tag_ = "" : InVar_ "Tag" Event_Severity_ = 0 : InVar_
      "Importance" Event_Class_ = 0 : InVar_ "Class" Visible_ = True : InVar_
      "synlig" TextObject = "" : InVar_ "tekst"
      Enable_Delay = True : InVar_ True
      OK_Variable = False : InVar_ "OK"
      Cancel_Variable = False : InVar_ "Fortryd"

      FillColour : Colour1 = -1
   TextBox_ ( 1.7 , 1.34 ) ( 2.26 , 1.2 )
      Int_Value
      Enable_ = True : InVar_ "Aktiver" Value_Changed = False : OutVar_
      "Ændret" Variable = 0 : OutVar_ "timeout" OpMin = 0 : InVar_ "min" OpMax
      = 2147483647 : InVar_ "max" OpStep = 1 : InVar_ "absoluttrin" Key_ = "" :
      InVar_ "Tast" GLOBAL = False : InVar_ "Tag_Global" Event_Text_ = "" :
      InVar_ "beskrivelse" Event_Tag_ = "" : InVar_ "tag" Event_Severity_ = 0 :
      InVar_ "vigtighedsgrad" Event_Class_ = 0 : InVar_ "klasse" Visible_ =
      True : InVar_ "Synlig" LeftAligned Abs_ Digits_
      Enable_Delay = True : InVar_ True
      OK_Variable = False : InVar_ "OK"
      Cancel_Variable = False : InVar_ "Fortryd"

      OutlineColour : Colour0 = 0 : InVar_ "TextColor" Colour1 = -1 : InVar_
      "AltTextColor" ColourStyle = False : InVar_ "ColorChoice"
      FillColour : Colour0 = 9 : InVar_ "BGColor" Colour1 = -1 : InVar_
      "AltBGColor" ColourStyle = True : InVar_ "ColorChoice2"
   ComButProc_ ( -0.44 , 1.72 ) ( -0.12 , 1.58 )
      NewWindow
      "" : InVar_ "modulepath" "" : InVar_ "windowtitle" False : InVar_
      "relativepos" 0.0 : InVar_ "xpos" 0.0 : InVar_ "ypos" 0.0 : InVar_
      "xsize" 0.0 : InVar_ "ysize" False : InVar_ "hroot" 0 : InVar_
      "selectclass" 0 : InVar_ "timeout" False : OutVar_ "windowdisplayed" 0 :
      OutVar_ "status"
      Enable_ = True : InVar_ "aktiver" Value_Changed = False : OutVar_
      "ændret" Variable = 0.0 Key_ = "" : InVar_ "tast" GLOBAL = False : InVar_
      "tast_global" Visible_ = True : InVar_ "synlig" TextObject = "" : InVar_
      "tekst"

   ComButProc_ ( -0.46 , 1.54 ) ( -0.1 , 1.42 )
      ToggleWindow
      "" : InVar_ "ModulePath" "" : InVar_ "WindowTitle" False : InVar_
      "RelativePos" 0.0 : InVar_ "XPos" 0.0 : InVar_ "ypos" 0.0 : InVar_
      "xsize" 0.0 : InVar_ "ysize" False : InVar_ "hierarchicroot" 0 : InVar_
      "selectclass" 0 : InVar_ "timeout" False : OutVar_ "windowdisplayed" 0 :
      OutVar_ "status"
      Enable_ = True : InVar_ "aktiver" Value_Changed = False : OutVar_
      "changed" Variable = 0.0 Key_ = "" : InVar_ "tast" GLOBAL = False :
      InVar_ "tast_global" Visible_ = True : InVar_ "synlig" TextObject = "" :
      InVar_ "tekst"

   ComButProc_ ( -0.46 , 1.36 ) ( -0.04 , 1.22 )
      DeleteWindow
      "" : InVar_ "ModulePath" 0 : InVar_ "SelectClass" 0 : OutVar_ "LineColor"
      Enable_ = True : InVar_ "Activate" Value_Changed = False : OutVar_
      "Changed" Variable = 0.0 Key_ = "" : InVar_ "Tast" GLOBAL = False :
      InVar_ "Tast_Global" Visible_ = True : InVar_ "Visible" TextObject = "" :
      InVar_ "Text"

   ComButProc_ ( -0.46 , 1.16 ) ( -0.1 , 1.02 )
      WindowContent
      "" : InVar_ "ModulePath" 0 : OutVar_ "ShownSamples"
      Enable_ = True : InVar_ "Activate" Value_Changed = False : OutVar_
      "Changed" Variable = 0.0 Key_ = "" : InVar_ "Tast" GLOBAL = False :
      InVar_ "Tast_Global" Visible_ = True : InVar_ "Visible" TextObject = "" :
      InVar_ "Text"

   ComButProc_ ( -0.44 , 0.94 ) ( -0.1 , 0.82 )
      NewEditFile
      "" : InVar_ "FileName" False : InVar_ "ReadOnly" 0.0 : InVar_ "XPos" 0.0
      : InVar_ "YPos" False : InVar_ "RelativePos" 0 : InVar_ "NoOfRows" 0 :
      InVar_ "NoOfColumns" 0 : InVar_ "FontKind" 0 : InVar_ "FontSize" 0 :
      OutVar_ "Status"
      Enable_ = True : InVar_ "Activate" Value_Changed = False : OutVar_
      "Changed" Variable = 0.0 Key_ = "" : InVar_ "Tast" GLOBAL = False :
      InVar_ "Tast_Global" Visible_ = True : InVar_ "Visible" TextObject = "" :
      InVar_ "Text"

   ComButProc_ ( -0.46 , 0.74 ) ( -0.1 , 0.58 )
      ToggleEditFile
      "" : InVar_ "FileName" False : InVar_ "ReadOnly" 0.0 : InVar_ "xpos" 0.0
      : InVar_ "ypos" False : InVar_ "relativepos" 0 : InVar_ "noofrows" 0 :
      InVar_ "noofcolumns" 0 : InVar_ "fontkind" 0 : InVar_ "fontsize" 0 :
      OutVar_ "status"
      Enable_ = True : InVar_ "aktiver" Value_Changed = False : OutVar_
      "ændret" Variable = 0.0 Key_ = "" : InVar_ "tast" GLOBAL = False : InVar_
      "tast_global" Visible_ = True : InVar_ "synlig" TextObject = "" : InVar_
      "tekst"

   ComButProc_ ( -0.48 , 0.5 ) ( -0.1 , 0.36 )
      DeleteEditFile
      "" : InVar_ "filename" 0 : OutVar_ "status"
      Enable_ = True : InVar_ "aktiver" Value_Changed = False : OutVar_
      "ændret" Variable = 0.0 Key_ = "" : InVar_ "tast" GLOBAL = False : InVar_
      "tast_global" Visible_ = True : InVar_ "synlig" TextObject = "" : InVar_
      "tekst"

   SimpleInteract ( 0.22 , 0.46 ) ( 0.58 , 0.34 )
      Bool_Value
      Enable_ = True : InVar_ "Aktiver" SelectVariable = False : OutVar_
      "Marked" Value_Changed = False : OutVar_ "Change" Variable = False :
      OutVar_ "Interaction" SetAction Key_ = "" : InVar_ "Tast" GLOBAL = False
      : InVar_ "Tast_global" Event_Text_ = "" : InVar_ LitString "Description"
      Event_Tag_ = "" : InVar_ LitString "Tag" Event_Severity_ = 0 : InVar_ 1
      Event_Class_ = 0 : InVar_ 2
      SnglSgn
      SnglSgnEna = False : InVar_ "Aktivate_Single"
      Purpose_ = "" : OutVar_ "Purpose"
      PurposeChng
      SgnrCom = "" : OutVar_ "Comment"
      CommentChng
      CommentMand
      Signer1_ = "" : OutVar_ "Useridentity"
      Signer1Name_ = "" : OutVar_ "UserName"
      DblSgn
      DblSgnEna = False : InVar_ "ActivateSecond"
      Enable_ = False : InVar_ "ActivateNr2"
      CansCom = "" : OutVar_ "AbortComment"
      SgnCans = False : OutVar_ "SignAborted"
      Signer2_ = "" : OutVar_ "UserIdentity2"
      Signer2Name_ = "" : OutVar_ "UserName2"

   MenuInteract ( 0.22 , 0.26 ) ( 0.58 , 0.12 )
      Int_Value
      Enable_ = True : InVar_ "Aktiver" SelectVariable = False : OutVar_
      "Markeret" Value_Changed = False : OutVar_ "Ændret" Variable = 0 :
      OutVar_ "absoluttrin" OpMin = 0 : InVar_ "min" OpMax = 2147483647 :
      InVar_ "max" OpStep = 1 : InVar_ "vigtighedsgrad" Key_ = "" : InVar_
      "Tast" GLOBAL = False : InVar_ "Tast_Global" Event_Text_ = "" : InVar_
      "Beskrivelse" Event_Tag_ = "" : InVar_ "Tag" Event_Severity_ = 0 : InVar_
      "Vigtighedsgrad" Event_Class_ = 0 : InVar_ "Klasse"

   MenuInteract ( 0.7 , 0.46 ) ( 1.06 , 0.34 )
      Real_Value
      Enable_ = True : InVar_ "Aktiver" SelectVariable = False : OutVar_
      "Markeret" Value_Changed = False : OutVar_ "Ændret" Variable = 0.0 :
      OutVar_ "xsize" OpMin = 0.0 : InVar_ "RotationMax" OpMax = 100.0 : InVar_
      "RotationVar" OpStep = 1.0 : InVar_ "YScaleMax" Key_ = "" : InVar_ "Tast"
      GLOBAL = False : InVar_ "Tast_Global" Event_Text_ = "" : InVar_
      "Beskrivelse" Event_Tag_ = "" : InVar_ "Tag" Event_Severity_ = 0 : InVar_
      "Vigtighedsgrad" Event_Class_ = 0 : InVar_ "Klasse"

   MenuInteract ( 0.7 , 0.3 ) ( 1.08 , 0.14 )
      String_Value
      Enable_ = True : InVar_ "aktiver" SelectVariable = False : OutVar_
      "markeret" Value_Changed = False : OutVar_ "ændret" Variable = "" :
      OutVar_ "JourTag" Key_ = "" : InVar_ "tast" GLOBAL = False : InVar_
      "tast_global" Event_Text_ = "" : InVar_ "Beskrivelse" Event_Tag_ = "" :
      InVar_ "Tag" Event_Severity_ = 0 : InVar_ "Vigtighedsgrad" Event_Class_ =
      0 : InVar_ "Klasse"

   MenuInteract ( 0.24 , 0.04 ) ( 0.58 , -0.12 )
      Time_Value
      Enable_ = True : InVar_ "Aktiver" SelectVariable = False : OutVar_
      "Markeret" Value_Changed = False : OutVar_ "Ændret" Variable = "" :
      OutVar_ "FirstPoint" Format_String_ = "" : InVar_ "WindowTitle" Key_ = ""
      : InVar_ "Tast" GLOBAL = False : InVar_ "Tag_Global" Event_Text_ = "" :
      InVar_ "Beskrivelse" Event_Tag_ = "" : InVar_ "Tag" Event_Severity_ = 0 :
      InVar_ "Vigtighedsgrad" Event_Class_ = 0 : InVar_ "Klasse"

   MenuInteract ( 0.72 , 0.1 ) ( 1.12 , -0.08 )
      Duration_Value
      Enable_ = True : InVar_ "Aktiver" SelectVariable = False : OutVar_
      "markeret" Value_Changed = False : OutVar_ "ændret" Variable = "" :
      OutVar_ "TimeShift" Format_String_ = "" : InVar_ "ModulePath" Key_ = "" :
      InVar_ "tast" GLOBAL = False : InVar_ "tast_global" Event_Text_ = "" :
      InVar_ "Beskrivelse" Event_Tag_ = "" : InVar_ "Tag" Event_Severity_ = 0 :
      InVar_ "Vigtighedsgrad" Event_Class_ = 0 : InVar_ "Klasse"

   ProcedureInteract ( 1.38 , 0.36 ) ( 1.86 , 0.18 )
      DeleteEditFile
      "" : InVar_ "FileName" 0 : OutVar_ "Status"
      Enable_ = True : InVar_ "Aktiver" Value_Changed = False : OutVar_
      "Ændret" Variable = 0.0 Key_ = "" : InVar_ "Tast" GLOBAL = False : InVar_
      "Tast_Global"
   TextBox_ ( 2.42 , 1.34 ) ( 2.98 , 1.2 )
      Time_Value
      Enable_ = True : InVar_ "Aktiver" Value_Changed = False : OutVar_
      "Ændret" Variable = "" : OutVar_ "StartTime" Format_String_ = "" : InVar_
      "tekst" Key_ = "" : InVar_ "Tast" GLOBAL = False : InVar_ "Tag_Global"
      Event_Text_ = "" : InVar_ "beskrivelse" Event_Tag_ = "" : InVar_ "tag"
      Event_Severity_ = 0 : InVar_ "vigtighedsgrad" Event_Class_ = 0 : InVar_
      "klasse" Visible_ = True : InVar_ "Synlig" CenterAligned Abs_ Digits_
      Enable_Delay = True : InVar_ True
      OK_Variable = False : InVar_ "OK"
      Cancel_Variable = False : InVar_ "Fortryd"

      OutlineColour : Colour0 = 0 : InVar_ "TextColor" Colour1 = -1 : InVar_
      "AltTextColor" ColourStyle = False : InVar_ "ColorChoice"
      FillColour : Colour0 = 9 : InVar_ "BGColor" Colour1 = -1 : InVar_
      "AltBGColor" ColourStyle = True : InVar_ "ColorChoice2"
   TextBox_ ( 3.1 , 1.34 ) ( 3.66 , 1.2 )
      Duration_Value
      Enable_ = True : InVar_ "Aktiver" Value_Changed = False : OutVar_
      "Ændret" Variable = "" : OutVar_ "DurationVar" Format_String_ = "" :
      InVar_ "tekst" Key_ = "" : InVar_ "Tast" GLOBAL = False : InVar_
      "Tag_Global" Event_Text_ = "" : InVar_ "beskrivelse" Event_Tag_ = "" :
      InVar_ "tag" Event_Severity_ = 0 : InVar_ "vigtighedsgrad" Event_Class_ =
      0 : InVar_ "klasse" Visible_ = True : InVar_ "Synlig" RightAligned Abs_
      Digits_
      Enable_Delay = True : InVar_ True
      OK_Variable = False : InVar_ "OK"
      Cancel_Variable = False : InVar_ "Fortryd"

      OutlineColour : Colour0 = 0 : InVar_ "TextColor" Colour1 = -1 : InVar_
      "AltTextColor" ColourStyle = False : InVar_ "ColorChoice"
      FillColour : Colour0 = 9 : InVar_ "BGColor" Colour1 = -1 : InVar_
      "AltBGColor" ColourStyle = True : InVar_ "ColorChoice2"
   SimpleInteract ( -0.18 , 0.26 ) ( 0.18 , 0.12 )
      Int_Value
      Enable_ = True : InVar_ "Aktiver" SelectVariable = False : OutVar_
      "Markeret" Value_Changed = False : OutVar_ "Ændret" Variable = 0 :
      OutVar_ "absoluttrin" OpMin = 0 : InVar_ "min" OpMax = 2147483647 :
      InVar_ "max" OpStep = 1 : InVar_ "vigtighedsgrad" Key_ = "" : InVar_
      "Tast" GLOBAL = False : InVar_ "Tast_Global" Event_Text_ = "" : InVar_
      "Beskrivelse" Event_Tag_ = "" : InVar_ "Tag" Event_Severity_ = 0 : InVar_
      "Vigtighedsgrad" Event_Class_ = 0 : InVar_ "Klasse"

   SimpleInteract ( -0.26 , -0.22 ) ( 0.1 , -0.34 )
      Bool_Value
      Enable_ = True : InVar_ "Aktiver" SelectVariable = False : OutVar_
      "Marked" Value_Changed = False : OutVar_ "Change" Variable = False :
      OutVar_ "Interaction" ResetAction Key_ = "" : InVar_ "Tast" GLOBAL =
      False : InVar_ "Tast_global" Event_Text_ = "" : InVar_ LitString
      "Description" Event_Tag_ = "" : InVar_ LitString "Tag" Event_Severity_ =
      0 : InVar_ 1 Event_Class_ = 0 : InVar_ 2
      SnglSgn
      SnglSgnEna = False : InVar_ "Aktivate_Single"
      Purpose_ = "" : OutVar_ "Purpose"
      PurposeChng
      SgnrCom = "" : OutVar_ "Comment"
      CommentChng
      CommentMand
      Signer1_ = "" : OutVar_ "Useridentity"
      Signer1Name_ = "" : OutVar_ "UserName"
      DblSgn
      DblSgnEna = False : InVar_ "ActivateSecond"
      Enable_ = False : InVar_ "ActivateNr2"
      CansCom = "" : OutVar_ "AbortComment"
      SgnCans = False : OutVar_ "SignAborted"
      Signer2_ = "" : OutVar_ "UserIdentity2"
      Signer2Name_ = "" : OutVar_ "UserName2"

   SimpleInteract ( -0.34 , -0.42 ) ( 0.0199999 , -0.54 )
      Bool_Value
      Enable_ = True : InVar_ "Aktiver" SelectVariable = False : OutVar_
      "Marked" Value_Changed = False : OutVar_ "Change" Variable = False :
      OutVar_ "Interaction" ToggleAction Key_ = "" : InVar_ "Tast" GLOBAL =
      False : InVar_ "Tast_global" Event_Text_ = "" : InVar_ LitString
      "Description" Event_Tag_ = "" : InVar_ LitString "Tag" Event_Severity_ =
      0 : InVar_ 1 Event_Class_ = 0 : InVar_ 2
      SnglSgn
      SnglSgnEna = False : InVar_ "Aktivate_Single"
      Purpose_ = "" : OutVar_ "Purpose"
      PurposeChng
      SgnrCom = "" : OutVar_ "Comment"
      CommentChng
      CommentMand
      Signer1_ = "" : OutVar_ "Useridentity"
      Signer1Name_ = "" : OutVar_ "UserName"
      DblSgn
      DblSgnEna = False : InVar_ "ActivateSecond"
      Enable_ = False : InVar_ "ActivateNr2"
      CansCom = "" : OutVar_ "AbortComment"
      SgnCans = False : OutVar_ "SignAborted"
      Signer2_ = "" : OutVar_ "UserIdentity2"
      Signer2Name_ = "" : OutVar_ "UserName2"

   MenuInteract ( -0.66 , -0.22 ) ( -0.3 , -0.34 )
      Bool_Value
      Enable_ = True : InVar_ "Aktiver" SelectVariable = False : OutVar_
      "Marked" Value_Changed = False : OutVar_ "Change" Variable = False :
      OutVar_ "Interaction" Key_ = "" : InVar_ "Tast" GLOBAL = False : InVar_
      "Tast_global" Event_Text_ = "" : InVar_ LitString "Description"
      Event_Tag_ = "" : InVar_ LitString "Tag" Event_Severity_ = 0 : InVar_ 1
      Event_Class_ = 0 : InVar_ 2
      SnglSgn
      SnglSgnEna = False : InVar_ "Aktivate_Single"
      Purpose_ = "" : OutVar_ "Purpose"
      PurposeChng
      SgnrCom = "" : OutVar_ "Comment"
      CommentChng
      CommentMand
      Signer1_ = "" : OutVar_ "Useridentity"
      Signer1Name_ = "" : OutVar_ "UserName"
      DblSgn
      DblSgnEna = False : InVar_ "ActivateSecond"
      Enable_ = False : InVar_ "ActivateNr2"
      CansCom = "" : OutVar_ "AbortComment"
      SgnCans = False : OutVar_ "SignAborted"
      Signer2_ = "" : OutVar_ "UserIdentity2"
      Signer2Name_ = "" : OutVar_ "UserName2"

   ProcedureInteract ( 0.48 , -0.72 ) ( 0.92 , -0.88 )
      NewWindow
      "" : InVar_ "ModulePath" "" : InVar_ "WindowTitle" False : InVar_
      "RelPos" 0.0 : InVar_ "Xpos" 0.0 : InVar_ "ypos" 0.0 : InVar_ "xsize" 0.0
      : InVar_ "ysize" False : InVar_ "hroot" 0 : InVar_ "selectclass" 0 :
      InVar_ "timeout" False : OutVar_ "windowdisplayed" 0 : OutVar_ "status"
      Enable_ = True : InVar_ "aktiver" Value_Changed = False : OutVar_
      "ændret" Variable = 0.0 Key_ = "" : InVar_ "tast" GLOBAL = False : InVar_
      "tag_global"
   ProcedureInteract ( 0.48 , -0.96 ) ( 1.0 , -1.08 )
      ToggleWindow
      "" : InVar_ "Mpath" "" : InVar_ "wtitle" False : InVar_ "relpos" 0.0 :
      InVar_ "xpos" 0.0 : InVar_ "ypos" 0.0 : InVar_ "xsize" 0.0 : InVar_
      "ysize" False : InVar_ "hroot" 0 : InVar_ "selectclass" 0 : InVar_
      "timeout" False : OutVar_ "wdisplayed" 0 : OutVar_ "status"
      Enable_ = True : InVar_ "aktiver" Value_Changed = False : OutVar_
      "ændret" Variable = 0.0 Key_ = "" : InVar_ "tast" GLOBAL = False : InVar_
      "tast_global"
   ProcedureInteract ( 0.44 , -1.16 ) ( 1.0 , -1.32 )
      DeleteWindow
      "" : InVar_ "mpath" 0 : InVar_ "selectclass" 0 : OutVar_ "status"
      Enable_ = True : InVar_ "aktiver" Value_Changed = False : OutVar_
      "ændret" Variable = 0.0 Key_ = "" : InVar_ "tast" GLOBAL = False : InVar_
      "tast_global"
   ProcedureInteract ( 0.44 , -1.44 ) ( 0.96 , -1.56 )
      WindowContent
      "" : InVar_ "mpath" 0 : OutVar_ "status"
      Enable_ = True : InVar_ "aktiver" Value_Changed = False : OutVar_
      "ændret" Variable = 0.0 Key_ = "" : InVar_ "tast" GLOBAL = False : InVar_
      "tast_global"
   ProcedureInteract ( 0.4 , -1.68 ) ( 1.0 , -1.8 )
      NewEditFile
      "" : InVar_ "filename" False : InVar_ "readonly" 0.0 : InVar_ "xpos" 0.0
      : InVar_ "ypos" False : InVar_ "relpos" 0 : InVar_ "noofrows" 0 : InVar_
      "noofcolumns" 0 : InVar_ "fontkind" 0 : InVar_ "fontsize" 0 : OutVar_
      "status"
      Enable_ = True : InVar_ "aktiver" Value_Changed = False : OutVar_
      "ændret" Variable = 0.0 Key_ = "" : InVar_ "tast" GLOBAL = False : InVar_
      "tast_global"
   ProcedureInteract ( 0.4 , -1.88 ) ( 1.08 , -2.04 )
      ToggleEditFile
      "" : InVar_ "filename" False : InVar_ "readolny" 0.0 : InVar_ "xpos" 0.0
      : InVar_ "ypos" False : InVar_ "relpos" 0 : InVar_ "nooforws" 0 : InVar_
      "noofcolumns" 0 : InVar_ "fontkind" 0 : InVar_ "fontsize" 0 : OutVar_
      "status"
      Enable_ = True : InVar_ "aktiver" Value_Changed = False : OutVar_
      "ændret" Variable = 0.0 Key_ = "" : InVar_ "tast" GLOBAL = False : InVar_
      "tast_global"
   TextBox_ ( 1.92 , -1.0 ) ( 2.64 , -1.24 )
      Int_Value
      Enable_ = True : InVar_ "Aktiver" Value_Changed = False : OutVar_
      "Ændret" Variable = 0 : OutVar_ "max" OpMin = 0 : InVar_ "min" OpMax =
      2147483647 : InVar_ "max" OpStep = 1 : InVar_ "vigtighedsgrad" Key_ = ""
      : InVar_ "Tast" GLOBAL = False : InVar_ "Tast_Global" Event_Text_ = "" :
      InVar_ "Beskrivelse" Event_Tag_ = "" : InVar_ "Tag" Event_Severity_ = 0 :
      InVar_ "Vigtighedsgrad" Event_Class_ = 0 : InVar_ "Klasse" Visible_ =
      True : InVar_ "Synlig" LeftAligned Abs_ Digits_
      Enable_Delay = True : InVar_ True
      OK_Variable = False : InVar_ "OK"
      Cancel_Variable = False : InVar_ "Fortryd"

      FillColour : Colour0 = 9 Colour1 = -1
   TextBox_ ( 3.64 , -0.96 ) ( 4.36 , -1.2 )
      Int_Value
      Enable_ = True : InVar_ "Aktiver" Value_Changed = False : OutVar_
      "Ændret" Variable = 0 : OutVar_ "max" OpMin = 0 : InVar_ "min" OpMax =
      2147483647 : InVar_ "max" OpStep = 1 : InVar_ "vigtighedsgrad" Key_ = ""
      : InVar_ "Tast" GLOBAL = False : InVar_ "Tast_Global" Event_Text_ = "" :
      InVar_ "Beskrivelse" Event_Tag_ = "" : InVar_ "Tag" Event_Severity_ = 0 :
      InVar_ "Vigtighedsgrad" Event_Class_ = 0 : InVar_ "Klasse" Visible_ =
      True : InVar_ "Synlig" RightAligned Abs_ Digits_
      Enable_Delay = True : InVar_ True
      OK_Variable = False : InVar_ "OK"
      Cancel_Variable = False : InVar_ "Fortryd"

      FillColour : Colour0 = 9 Colour1 = -1
   TextBox_ ( 2.88 , -1.04 ) ( 3.6 , -1.28 )
      Int_Value
      Enable_ = True : InVar_ "Aktiver" Value_Changed = False : OutVar_
      "Ændret" Variable = 0 : OutVar_ "max" OpMin = 0 : InVar_ "min" OpMax =
      2147483647 : InVar_ "max" OpStep = 1 : InVar_ "vigtighedsgrad" Key_ = ""
      : InVar_ "Tast" GLOBAL = False : InVar_ "Tast_Global" Event_Text_ = "" :
      InVar_ "Beskrivelse" Event_Tag_ = "" : InVar_ "Tag" Event_Severity_ = 0 :
      InVar_ "Vigtighedsgrad" Event_Class_ = 0 : InVar_ "Klasse" Visible_ =
      True : InVar_ "Synlig" CenterAligned Abs_ Digits_
      Enable_Delay = True : InVar_ True
      OK_Variable = False : InVar_ "OK"
      Cancel_Variable = False : InVar_ "Fortryd"

      FillColour : Colour0 = 9 Colour1 = -1
   TextBox_ ( 1.96 , -1.4 ) ( 2.68 , -1.64 )
      Real_Value
      Enable_ = True : InVar_ "Aktiver" Value_Changed = False : OutVar_
      "Ændret" Variable = 0.0 : OutVar_ "RotateionMin" OpMin = 0.0 : InVar_
      "RotateionMin" OpMax = 0.0 : InVar_ "YScaleMax" OpStep = 0.0 : InVar_
      "YScaleMax" Key_ = "" : InVar_ "Tast" GLOBAL = False : InVar_
      "Tast_Global" Event_Text_ = "" : InVar_ "Beskrivelse" Event_Tag_ = "" :
      InVar_ "Tag" Event_Severity_ = 0 : InVar_ "Vigtighedsgrad" Event_Class_ =
      0 : InVar_ "Klasse" Visible_ = True : InVar_ "Synlig" LeftAligned
      Relative_ Decimal_
      NoOf_ = 2 : InVar_ "absoluttrin"
      Enable_Delay = True : InVar_ True
      OK_Variable = False : InVar_ "OK"
      Cancel_Variable = False : InVar_ "Fortryd"

      FillColour : Colour0 = 9 Colour1 = -1
   TextBox_ ( 2.8 , -1.4 ) ( 3.52 , -1.64 )
      Real_Value
      Enable_ = True : InVar_ "Aktiver" Value_Changed = False : OutVar_
      "Ændret" Variable = 0.0 : OutVar_ "RotateionMin" OpMin = 0.0 : InVar_
      "RotateionMin" OpMax = 0.0 : InVar_ "YScaleMax" OpStep = 0.0 : InVar_
      "YScaleMax" Key_ = "" : InVar_ "Tast" GLOBAL = False : InVar_
      "Tast_Global" Event_Text_ = "" : InVar_ "Beskrivelse" Event_Tag_ = "" :
      InVar_ "Tag" Event_Severity_ = 0 : InVar_ "Vigtighedsgrad" Event_Class_ =
      0 : InVar_ "Klasse" Visible_ = True : InVar_ "Synlig" LeftAligned
      Relative_ Digits_
      NoOf_ = 6 : InVar_ "AltLineColor"
      Enable_Delay = True : InVar_ True
      OK_Variable = False : InVar_ "OK"
      Cancel_Variable = False : InVar_ "Fortryd"

      FillColour : Colour0 = 9 Colour1 = -1
   ComBut_ ( -1.4 , 1.28 ) ( -1.04 , 1.16 )
      Bool_Value
      Enable_ = True : InVar_ "aktiver" Value_Changed = False : OutVar_
      "ændret" Variable = False : OutVar_ "var1" Key_ = "" : InVar_ "tast"
      GLOBAL = False : InVar_ "tast_global" Event_Text_ = "" : InVar_
      "beskrivelse" Event_Tag_ = "" : InVar_ "tag" Event_Severity_ = 0 : InVar_
      "vigtighedsgrad" Event_Class_ = 0 : InVar_ "klasse" Visible_ = True :
      InVar_ "synlig" SetAction
      Abs_ TextObject = "" : InVar_ "tekst"
      Alt_Text = "" : InVar_ "alttekst"
      SetApp_
      SnglSgn
      SnglSgnEna = False : InVar_ "aktiverenkelt"
      Purpose_ = "" : OutVar_ "formål"
      PurposeChng
      SgnrCom = "" : OutVar_ "kommentar"
      CommentChng
      CommentMand
      Signer1_ = "" : OutVar_ "brugerident1"
      Signer1Name_ = "" : OutVar_ "fuldnavn1"
      DblSgn
      DblSgnEna = False : InVar_ "aktiverdobbelt"
      Enable_ = False : InVar_ "aktiver2"
      CansCom = "" : OutVar_ "afbrydkommentar"
      SgnCans = False : OutVar_ "signafbrudt"
      Signer2_ = "" : OutVar_ "brugerident2"
      Signer2Name_ = "" : OutVar_ "fuldnavn2"

   ComBut_ ( -1.4 , 0.96 ) ( -1.04 , 0.84 )
      Int_Value
      Enable_ = True : InVar_ "aktiver" Value_Changed = False : OutVar_
      "ændret" Variable = 0 : OutVar_ "var2" OpMin = 0 : InVar_ "min" OpMax = 0
      : InVar_ "max" OpStep = 1 : InVar_ "abstrin" Key_ = "" : InVar_ "tast"
      GLOBAL = False : InVar_ "tast_global" Event_Text_ = "" : InVar_
      "beskrivelse" Event_Tag_ = "" : InVar_ "tag" Event_Severity_ = 0 : InVar_
      "vigtighedsgrad" Event_Class_ = 0 : InVar_ "klasse" Visible_ = True :
      InVar_ "synlig" Abs_ TextObject = "" : InVar_ "tekst"
      Alt_Text = "" : InVar_ "alttekst"
      SnglSgn
      SnglSgnEna = False : InVar_ "aktiverenkelt"
      Purpose_ = "" : OutVar_ "formål"
      PurposeChng
      SgnrCom = "" : OutVar_ "kommentar"
      CommentChng
      CommentMand
      Signer1_ = "" : OutVar_ "brugerident1"
      Signer1Name_ = "" : OutVar_ "fuldnavn1"
      DblSgn
      DblSgnEna = False : InVar_ "aktiverdobbelt"
      Enable_ = False : InVar_ "aktiver2"
      CansCom = "" : OutVar_ "afbrydkommentar"
      SgnCans = False : OutVar_ "signafbrudt"
      Signer2_ = "" : OutVar_ "brugerident2"
      Signer2Name_ = "" : OutVar_ "fuldnavn2"

   ComBut_ ( -1.0 , 0.96 ) ( -0.64 , 0.84 )
      Int_Value
      Enable_ = True : InVar_ "aktiver" Value_Changed = False : OutVar_
      "ændret" Variable = 0 : OutVar_ "var2" Key_ = "" : InVar_ "tast" GLOBAL =
      False : InVar_ "tast_global" Event_Text_ = "" : InVar_ "beskrivelse"
      Event_Tag_ = "" : InVar_ "tag" Event_Severity_ = 0 : InVar_
      "vigtighedsgrad" Event_Class_ = 0 : InVar_ "klasse" Visible_ = True :
      InVar_ "synlig" Abs_ TextObject = "" : InVar_ "tekst"
      Alt_Text = "" : InVar_ "alttekst"
      SetVal_
      SetApp_
      Value_ = 0 : InVar_ "intvar"
      SnglSgn
      SnglSgnEna = False : InVar_ "aktiverenkelt"
      Purpose_ = "" : OutVar_ "formål"
      PurposeChng
      SgnrCom = "" : OutVar_ "kommentar"
      CommentChng
      CommentMand
      Signer1_ = "" : OutVar_ "brugerident1"
      Signer1Name_ = "" : OutVar_ "fuldnavn1"
      DblSgn
      DblSgnEna = False : InVar_ "aktiverdobbelt"
      Enable_ = False : InVar_ "aktiver2"
      CansCom = "" : OutVar_ "afbrydkommentar"
      SgnCans = False : OutVar_ "signafbrudt"
      Signer2_ = "" : OutVar_ "brugerident2"
      Signer2Name_ = "" : OutVar_ "fuldnavn2"

   ComBut_ ( -1.0 , 1.28 ) ( -0.64 , 1.16 )
      Bool_Value
      Enable_ = True : InVar_ "aktiver" Value_Changed = False : OutVar_
      "ændret" Variable = False : OutVar_ "var1" Key_ = "" : InVar_ "tast"
      GLOBAL = False : InVar_ "tast_global" Event_Text_ = "" : InVar_
      "beskrivelse" Event_Tag_ = "" : InVar_ "tag" Event_Severity_ = 0 : InVar_
      "vigtighedsgrad" Event_Class_ = 0 : InVar_ "klasse" Visible_ = True :
      InVar_ "synlig" ResetAction
      Abs_ TextObject = "" : InVar_ "tekst"
      Alt_Text = "" : InVar_ "alttekst"
      SetApp_
      SnglSgn
      SnglSgnEna = False : InVar_ "aktiverenkelt"
      Purpose_ = "" : OutVar_ "formål"
      PurposeChng
      SgnrCom = "" : OutVar_ "kommentar"
      CommentChng
      CommentMand
      Signer1_ = "" : OutVar_ "brugerident1"
      Signer1Name_ = "" : OutVar_ "fuldnavn1"
      DblSgn
      DblSgnEna = False : InVar_ "aktiverdobbelt"
      Enable_ = False : InVar_ "aktiver2"
      CansCom = "" : OutVar_ "afbrydkommentar"
      SgnCans = False : OutVar_ "signafbrudt"
      Signer2_ = "" : OutVar_ "brugerident2"
      Signer2Name_ = "" : OutVar_ "fuldnavn2"

   ComBut_ ( -0.76 , 1.28 ) ( -0.4 , 1.16 )
      Bool_Value
      Enable_ = True : InVar_ "aktiver" Value_Changed = False : OutVar_
      "ændret" Variable = False : OutVar_ "var1" Key_ = "" : InVar_ "tast"
      GLOBAL = False : InVar_ "tast_global" Event_Text_ = "" : InVar_
      "beskrivelse" Event_Tag_ = "" : InVar_ "tag" Event_Severity_ = 0 : InVar_
      "vigtighedsgrad" Event_Class_ = 0 : InVar_ "klasse" Visible_ = True :
      InVar_ "synlig" ToggleAction
      Abs_ TextObject = "" : InVar_ "tekst"
      Alt_Text = "" : InVar_ "alttekst"
      SetApp_
      SnglSgn
      SnglSgnEna = False : InVar_ "aktiverenkelt"
      Purpose_ = "" : OutVar_ "formål"
      PurposeChng
      SgnrCom = "" : OutVar_ "kommentar"
      CommentChng
      CommentMand
      Signer1_ = "" : OutVar_ "brugerident1"
      Signer1Name_ = "" : OutVar_ "fuldnavn1"
      DblSgn
      DblSgnEna = False : InVar_ "aktiverdobbelt"
      Enable_ = False : InVar_ "aktiver2"
      CansCom = "" : OutVar_ "afbrydkommentar"
      SgnCans = False : OutVar_ "signafbrudt"
      Signer2_ = "" : OutVar_ "brugerident2"
      Signer2Name_ = "" : OutVar_ "fuldnavn2"

   ComBut_ ( -1.4 , 0.68 ) ( -1.04 , 0.56 )
      Real_Value
      Enable_ = True : InVar_ "aktiver" Value_Changed = False : OutVar_
      "ændret" Variable = 0.0 : OutVar_ "var3" OpMin = 0.0 : InVar_ "minreal"
      OpMax = 0.0 : InVar_ "maxreal" OpStep = 0.0 : InVar_ "abstrinreal" Key_ =
      "" : InVar_ "tast" GLOBAL = False : InVar_ "tast_global" Event_Text_ = ""
      : InVar_ "beskrivelse" Event_Tag_ = "" : InVar_ "tag" Event_Severity_ = 0
      : InVar_ "vigtighedsgrad" Event_Class_ = 0 : InVar_ "klasse" Visible_ =
      True : InVar_ "synlig" Abs_ TextObject = "" : InVar_ "tekst"
      Alt_Text = "" : InVar_ "alttekst"
      SnglSgn
      SnglSgnEna = False : InVar_ "aktiverenkelt"
      Purpose_ = "" : OutVar_ "formål"
      PurposeChng
      SgnrCom = "" : OutVar_ "kommentar"
      CommentChng
      CommentMand
      Signer1_ = "" : OutVar_ "brugerident1"
      Signer1Name_ = "" : OutVar_ "fuldnavn1"
      DblSgn
      DblSgnEna = False : InVar_ "aktiverdobbelt"
      Enable_ = False : InVar_ "aktiver2"
      CansCom = "" : OutVar_ "afbrydkommentar"
      SgnCans = False : OutVar_ "signafbrudt"
      Signer2_ = "" : OutVar_ "brugerident2"
      Signer2Name_ = "" : OutVar_ "fuldnavn2"

   ComBut_ ( -0.96 , 0.68 ) ( -0.6 , 0.56 )
      Real_Value
      Enable_ = True : InVar_ "aktiver" Value_Changed = False : OutVar_
      "ændret" Variable = 0.0 : OutVar_ "var3" OpMin = 0.0 : InVar_ "minreal"
      OpMax = 0.0 : InVar_ "maxreal" Key_ = "" : InVar_ "tast" GLOBAL = False :
      InVar_ "tast_global" Event_Text_ = "" : InVar_ "beskrivelse" Event_Tag_ =
      "" : InVar_ "tag" Event_Severity_ = 0 : InVar_ "vigtighedsgrad"
      Event_Class_ = 0 : InVar_ "klasse" Visible_ = True : InVar_ "synlig"
      Relative_ TextObject = "" : InVar_ "tekst"
      Alt_Text = "" : InVar_ "alttekst"
      SnglSgn
      SnglSgnEna = False : InVar_ "aktiverenkelt"
      Purpose_ = "" : OutVar_ "formål"
      PurposeChng
      SgnrCom = "" : OutVar_ "kommentar"
      CommentChng
      CommentMand
      Signer1_ = "" : OutVar_ "brugerident1"
      Signer1Name_ = "" : OutVar_ "fuldnavn1"
      DblSgn
      DblSgnEna = False : InVar_ "aktiverdobbelt"
      Enable_ = False : InVar_ "aktiver2"
      CansCom = "" : OutVar_ "afbrydkommentar"
      SgnCans = False : OutVar_ "signafbrudt"
      Signer2_ = "" : OutVar_ "brugerident2"
      Signer2Name_ = "" : OutVar_ "fuldnavn2"

   ComBut_ ( -0.76 , 1.44 ) ( -0.4 , 1.32 )
      Bool_Value
      Enable_ = True : InVar_ "aktiver" Value_Changed = False : OutVar_
      "ændret" Variable = False : OutVar_ "var1" Key_ = "" : InVar_ "tast"
      GLOBAL = False : InVar_ "tast_global" Event_Text_ = "" : InVar_
      "beskrivelse" Event_Tag_ = "" : InVar_ "tag" Event_Severity_ = 0 : InVar_
      "vigtighedsgrad" Event_Class_ = 0 : InVar_ "klasse" Visible_ = True :
      InVar_ "synlig" ToggleAction
      Abs_ TextObject = "" : InVar_ LitString "tekst"
      Alt_Text = "" : InVar_ LitString "alttekst"
      SetApp_
      SnglSgn
      SnglSgnEna = False : InVar_ "aktiverenkelt"
      Purpose_ = "" : OutVar_ "formål"
      PurposeChng
      SgnrCom = "" : OutVar_ "kommentar"
      CommentChng
      CommentMand
      Signer1_ = "" : OutVar_ "brugerident1"
      Signer1Name_ = "" : OutVar_ "fuldnavn1"
      DblSgn
      DblSgnEna = False : InVar_ "aktiverdobbelt"
      Enable_ = False : InVar_ "aktiver2"
      CansCom = "" : OutVar_ "afbrydkommentar"
      SgnCans = False : OutVar_ "signafbrudt"
      Signer2_ = "" : OutVar_ "brugerident2"
      Signer2Name_ = "" : OutVar_ "fuldnavn2"

   ComBut_ ( -1.0 , 1.44 ) ( -0.64 , 1.32 )
      Bool_Value
      Enable_ = True : InVar_ "aktiver" Value_Changed = False : OutVar_
      "ændret" Variable = False : OutVar_ "var1" Key_ = "" : InVar_ "tast"
      GLOBAL = False : InVar_ "tast_global" Event_Text_ = "" : InVar_
      "beskrivelse" Event_Tag_ = "" : InVar_ "tag" Event_Severity_ = 0 : InVar_
      "vigtighedsgrad" Event_Class_ = 0 : InVar_ "klasse" Visible_ = True :
      InVar_ "synlig" ResetAction
      Abs_ TextObject = "" : InVar_ "tekst"
      Alt_Text = "" : InVar_ "alttekst"
      SetApp_
      SnglSgn
      SnglSgnEna = False : InVar_ "aktiverenkelt"
      Purpose_ = "" : OutVar_ "formål"
      PurposeChng
      SgnrCom = "" : OutVar_ "kommentar"
      CommentChng
      CommentMand
      Signer1_ = "" : OutVar_ "brugerident1"
      Signer1Name_ = "" : OutVar_ "fuldnavn1"
      DblSgn
      DblSgnEna = False : InVar_ "aktiverdobbelt"
      Enable_ = False : InVar_ "aktiver2"
      CansCom = "" : OutVar_ "afbrydkommentar"
      SgnCans = False : OutVar_ "signafbrudt"
      Signer2_ = "" : OutVar_ "brugerident2"
      Signer2Name_ = "" : OutVar_ "fuldnavn2"


ModuleCode

SEQUENCE SQ_1  (SeqControl,SeqTimer) COORD 0.0, 0.56 OBJSIZE 0.3, 0.3
   SEQINITSTEP ST_Initstep
   SEQTRANSITION Tr1 WAIT_FOR ST_InitStep.t > 100
   SEQSTEP S1
   SEQTRANSITION Tr2 WAIT_FOR S1.X
   SEQSTEP S2
      ENTERCODE
         StateVar:New = StateVar:Old;
   SEQTRANSITION Tr4 WAIT_FOR StateVar
   PARALLELSEQ
      SEQSTEP S3
   PARALLELBRANCH
      SEQSTEP S4
   ENDPARALLEL
   SEQTRANSITION Tr3 WAIT_FOR True
   SEQSTEP S5
   SUBSEQTRANSITION SubSeq
      ALTERNATIVESEQ
         ALTERNATIVESEQ
            SEQTRANSITION Tr5 WAIT_FOR True
         ALTERNATIVEBRANCH
            SEQTRANSITION Tr6 WAIT_FOR True
         ENDALTERNATIVE
      ALTERNATIVEBRANCH
         SEQTRANSITION Tr7 WAIT_FOR True
      ENDALTERNATIVE
   ENDSUBSEQTRANSITION
ENDSEQUENCE

EQUATIONBLOCK EQ_1 COORD 0.4, 0.6 OBJSIZE 0.3, 0.3 :
   TernaryInt = IF StateVar THEN 1 ELSIF 2 == 2 THEN 3 ELSE 0 ENDIF;
   BoolLit = True;
   OnLit = On;
   BoolFalseLit = False;
   OffLit = Off;
   StateVarAccess = StateVar:Old;
   Test = True AND True OR False OR  NOT True;
   Test = 1 > 2 AND 2 >= 3 OR 3 < 4 AND  NOT 4 <= 5 OR 7 == 6 OR 6 <> 8;
   IF SQ_1.Reset THEN
      Test = False;
   ELSIF  NOT SQ_1.Reset THEN
      Test = False;
   ELSE
      Test = On;
   ENDIF;
   IntVar = 1/0;
   IntVar2 = 1000*1000*1000*1000*1000*1000*1000*1000*1000*1000*1000*1000*1000;
   RealVar1 = 1.0/0.0;
   realVar2 = 1000.0*1000*1000*1000*1000*1000*1000*1000*1000*1000*1000*1000*
      1000;

ENDDEF (*BasePicture*);
