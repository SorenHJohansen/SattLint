"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: InteractItems"
(* Covers InteractObjects section with three interact item types:
   - TextBox_: integer input/output widget with OutVar_ write binding
   - ComBut_: boolean toggle button with Enable_ / InVar_ / OutVar_ bindings
   - ComButProc_: procedure-call button (ToggleWindow with arguments)
   Expected: strict syntax-check passes. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   InputValue: integer  := 0;
   EnableFlag: boolean  := False;
   ToggleBit: boolean  := False;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
GraphObjects :
   RectangleObject ( -1.0 , 1.0 ) ( 1.0 , -1.0 )
      OutlineColour : Colour0 = -3
InteractObjects :
   TextBox_ ( -0.8 , 0.9 ) ( 0.8 , 0.7 )
      Int_Value
      Variable = 0 : OutVar_ "InputValue" Abs_ Digits_
      FillColour : Colour0 = 9 Colour1 = -1

   ComBut_ ( -0.8 , 0.6 ) ( 0.8 , 0.4 )
      Bool_Value
      Enable_ = True : InVar_ "EnableFlag" Variable = False : OutVar_
      "ToggleBit" ToggleAction
      Abs_ SetApp_

   ComButProc_ ( -0.8 , 0.3 ) ( 0.8 , 0.1 )
      ToggleWindow
      "" : InVar_ LitString "SubPanel" "" False 0.0 0.0 0.0 : InVar_ 0.5 0.0
      False : InVar_ True 0 0 False 0
      Variable = 0.0

ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      IF ToggleBit THEN
         EnableFlag = True;
      ENDIF;

ENDDEF (*BasePicture*);
