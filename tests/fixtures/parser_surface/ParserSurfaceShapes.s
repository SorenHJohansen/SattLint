"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: ParserSurfaceShapes"
(* Parsed by the parser surface contract test. Every construct here is a shape
   the analyzers must keep reading: a text object that names a variable, a
   pick button that names a variable, bound header arguments, clipping tails,
   a procedure call with an expression argument, and an interactor body with
   an assignment, a flag, and a colour. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0 ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   TextVar: string  := "";
   PickVar: integer  := 0;
   Flag: boolean  := False;
   OutVal: boolean  := False;
   ProcArg: integer  := 0;
   PosVar: real  := 0.0;
   ClipVar: real  := 0.0;

SUBMODULES
   Child Invocation
      ( 0.0 : InVar_ "PosVar" , 0.0 , 0.0 , 0.5 , 0.5
       Param1 = 5
       Enable_ = True : InVar_ "Flag"
       Module_In_View = True : OutVar_ "OutVal" ) : MODULEDEFINITION
   MODULEPARAMETERS
      Param1: integer ;


   ModuleDef
   ClippingBounds = ( 0.0 , 0.0 ) ( 1.0 , 1.0 )

   ENDDEF (*Child*);

ModuleDef
ClippingBounds = ( -1.0 , -1.0 : InVar_ "ClipVar" ) ( 1.0 , 1.0 )
GraphObjects :
   TextObject ( -0.8 , 0.9 ) ( 0.8 , 0.7 )
      "TextVar" VarName
      OutlineColour : Colour0 = -3
InteractObjects :
   TextBox_ ( -0.8 , 0.6 ) ( 0.8 , 0.4 )
      Int_Value
      Variable = 0 : OutVar_ "OutVal"
      IntObjPickButton = "PickVar" VarName
      Custom_Flag
      FillColour : Colour0 = 9 Colour1 = -1

   ComButProc_ ( -0.8 , 0.3 ) ( 0.8 , 0.1 )
      ToggleWindow : ( ProcArg + 1 )
      Variable = 0.0

ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Flag = True;

ENDDEF (*BasePicture*);
