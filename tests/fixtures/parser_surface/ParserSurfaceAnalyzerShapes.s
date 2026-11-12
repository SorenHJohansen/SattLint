"Syntax version 2.23, date: 2026-11-12-00:00:00.000 N"
"Original file date: ---"
"Program date: 2026-11-12-00:00:00.000, name: ParserSurfaceAnalyzerShapes"
(* Parsed by the Phase 3 analyzer tests. Each construct is a reference the
   variable analyzer must keep visible: text and pick-button names, header
   argument tails, clipping tails, a procedure expression argument, an
   interactor body with an enable tail / out-var assignment / colour, and
   literal versus variable parameter mappings. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0 ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   MakerType = MODULEDEFINITION DateCode_ 1
   MODULEPARAMETERS
      Param1: integer ;
      Param2: integer ;
      Param3: integer ;
   LOCALVARIABLES
      Result: integer := 0;
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Result = Param1 + Param2;
   ENDDEF (*MakerType*);

LOCALVARIABLES
   TextVar: string := "";
   PickVar: integer := 0;
   HeaderFlag: boolean := False;
   HeaderOut: boolean := False;
   BodyFlag: boolean := False;
   BodyOut: boolean := False;
   ProcArg: integer := 0;
   PosVar: real := 0.0;
   ClipVar: real := 0.0;
   MappedVar: integer := 0;
   UnusedMappedVar: integer := 0;
   ColourVar: real := 0.0;

SUBMODULES
   Child Invocation
      ( 0.0 : InVar_ "PosVar" , 0.0 , 0.0 , 0.5 , 0.5
       Param1 = 5
       Enable_ = True : InVar_ "HeaderFlag"
       Module_In_View = True : OutVar_ "HeaderOut" ) : MODULEDEFINITION
   MODULEPARAMETERS
      Param1: integer ;

   ModuleDef
   ClippingBounds = ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
   ENDDEF (*Child*);

   Maker Invocation
      ( 0.0 , 0.0 , 0.0 , 0.5 , 0.5 ) : MakerType (
      Param1 => 5,
      Param2 => MappedVar,
      Param3 => UnusedMappedVar );

ModuleDef
ClippingBounds = ( -1.0 , -1.0 : InVar_ "ClipVar" ) ( 1.0 , 1.0 )
GraphObjects :
   TextObject ( -0.8 , 0.9 ) ( 0.8 , 0.7 )
      "textvar" VarName
      OutlineColour : Colour0 = -3
InteractObjects :
   TextBox_ ( -0.8 , 0.6 ) ( 0.8 , 0.4 )
      Int_Value
      Enable_ = True : InVar_ "BodyFlag"
      Variable = 0 : OutVar_ "BodyOut"
      IntObjPickButton = "pickvar" VarName
      Custom_Flag
      FillColour : Colour0 = 9 : InVar_ "ColourVar" Colour1 = -1

   ComButProc_ ( -0.8 , 0.3 ) ( 0.8 , 0.1 )
      ToggleWindow : ( ProcArg + 1 )
      Variable = 0.0

ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      HeaderFlag = True;
ENDDEF (*BasePicture*);
