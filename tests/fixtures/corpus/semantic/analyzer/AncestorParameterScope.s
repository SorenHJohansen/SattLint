"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: AncestorParameterScope"
(* SEMANTIC: a frame module declares nothing, so a reference in its code or a
   "VarName" text resolves lexically to an ancestor parameter. The enclosing
   module forwards the value through a parameter mapping, and that forward must
   count as a use of both the frame's ancestor parameter and the mapped source.
   The same text name is declared in two modules, so the global index cannot
   decide it and only the lexical scope finds the right declaration.
   Expected finding: none. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

MODULEPARAMETERS
   Setting: integer  := 0;
   HeaderTextA: string  := "";
   HeaderTextB: string  := "";

SUBMODULES
   Middle Invocation
      ( 0.1 , 0.1 , 0.0 , 0.8 , 0.8
       ) : MODULEDEFINITION DateCode_ 2
   MODULEPARAMETERS
      Setting: integer  := 1;

   SUBMODULES
      Panel Invocation
         ( 0.1 , 0.1 , 0.0 , 0.8 , 0.8
         IgnoreMaxModule ) : MODULEDEFINITION DateCode_ 3 ( Frame_Module )

      ModuleDef
      ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
      ModuleCode
      EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
         Setting = Setting + Setting;

      ENDDEF (*Panel*);

   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ENDDEF (*Middle*) ( Setting => Setting );

   HeaderA Invocation
      ( 0.1 , 0.0 , 0.0 , 0.8 , 0.4
       ) : MODULEDEFINITION DateCode_ 4
   MODULEPARAMETERS
      HeaderName: string  := "";

   SUBMODULES
      PanelA Invocation
         ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
         IgnoreMaxModule ) : MODULEDEFINITION DateCode_ 5 ( Frame_Module )

      ModuleDef
      ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
      GraphObjects :
         TextObject ( -0.8 , 0.5 ) ( 0.8 , -0.5 )
            "HeaderName" VarName Width_ = 5  ValueFraction = 2
            OutlineColour : Colour0 = -3

      ENDDEF (*PanelA*);

   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ENDDEF (*HeaderA*) ( HeaderName => HeaderTextA );

   HeaderB Invocation
      ( 0.1 , -0.5 , 0.0 , 0.8 , 0.4
       ) : MODULEDEFINITION DateCode_ 6
   MODULEPARAMETERS
      HeaderName: string  := "";

   SUBMODULES
      PanelB Invocation
         ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
         IgnoreMaxModule ) : MODULEDEFINITION DateCode_ 7 ( Frame_Module )

      ModuleDef
      ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
      GraphObjects :
         TextObject ( -0.8 , 0.5 ) ( 0.8 , -0.5 )
            "HeaderName" VarName Width_ = 5  ValueFraction = 2
            OutlineColour : Colour0 = -3

      ENDDEF (*PanelB*);

   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ENDDEF (*HeaderB*) ( HeaderName => HeaderTextB );

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
