"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: CoordInVarTail"
(* Covers InVar_ tails on invocation coordinate values.
   A submodule can have its position and size bound dynamically to variables
   by adding ": InVar_ <variable>" after a coordinate value.
   Expected: strict syntax-check passes. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   PanelType = MODULEDEFINITION DateCode_ 1
   LOCALVARIABLES
      PanelData: integer  := 0;

   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ModuleCode
   EQUATIONBLOCK PanelEq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      PanelData = PanelData + 1;

   ENDDEF (*PanelType*);

LOCALVARIABLES
   PanelX: real  := 0.1;
   PanelY: real  := -0.5;
   PanelW: real  := 0.4;
   PanelH: real  := 0.3;

SUBMODULES
   Panel Invocation
      ( 0.1 : InVar_ PanelX , -0.5 : InVar_ PanelY , 0.0 , 0.4 : InVar_ PanelW , 0.3 : InVar_ PanelH
       ) : PanelType;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      PanelX = PanelX + 0.01;
      PanelY = PanelY - 0.01;

ENDDEF (*BasePicture*);
