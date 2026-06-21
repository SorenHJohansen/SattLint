"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: ModuleOptions"
(* Edge case: ModuleDef with Two_Layers_ and Grid options.
   Grammar rule: moduledef_opts. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   GridChild = MODULEDEFINITION DateCode_ 1
   LOCALVARIABLES
      Item: integer  := 0;
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   Grid = 10.0
   ENDDEF (*GridChild*);

SUBMODULES
   GridInst Invocation
      ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
       ) : GridChild;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
Two_Layers_ LayerLimit_ = 3.0

ENDDEF (*BasePicture*);
