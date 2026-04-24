"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: GraphicsObjects"
(* Covers ModuleDef graphical layout constructs:
   - ClippingBounds with coordinate pairs
   - GraphObjects section with RectangleObject and TextObject
   - OutlineColour attribute on a GraphObject
   - Width_ and ValueFraction attributes on a TextObject
   - InVar_ tail linking a graphic display to a variable
   - Zoomable and optional Invocation flags
   Expected: strict syntax-check passes. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0 IgnoreMaxModule
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   DisplayValue: integer  := 0;
   LabelEnable: boolean  := True;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
Zoomable
GraphObjects :
   RectangleObject ( -1.0 , 1.0 ) ( 1.0 , -1.0 )
      OutlineColour : Colour0 = 5
   TextObject ( -0.8 , 0.5 ) ( 0.8 , -0.5 )
      "DisplayValue" VarName Width_ = 8  ValueFraction = 0  LeftAligned
      Enable_ = True : InVar_ "LabelEnable"
      OutlineColour : Colour0 = -3
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      DisplayValue = DisplayValue + 1;

ENDDEF (*BasePicture*);
