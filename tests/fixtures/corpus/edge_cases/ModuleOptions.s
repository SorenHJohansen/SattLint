"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: ModuleOptions"
(* Edge case: MODULEDEFINITION with TWOLAYERS and GRID options.
   Grammar rule: moduledef_opts. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1 TWOLAYERS

TYPEDEFINITIONS
   GridChild = MODULEDEFINITION DateCode_ 1 GRID
   LOCALVARIABLES
      Item: integer  := 0;
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ENDDEF (*GridChild*);

SUBMODULES
   GridInst Invocation
      ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
       ) : GridChild;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

ENDDEF (*BasePicture*);
