"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: DupSiblingName"
(* SEMANTIC: Duplicate sibling submodule names and unexpected submodule type.
   Expected: duplicate-sibling-name, unexpected-submodule-type. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   PumpType = MODULEDEFINITION DateCode_ 1
   LOCALVARIABLES
      Speed: integer  := 0;
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ENDDEF (*PumpType*);

SUBMODULES
   Pump Invocation
      ( 0.0 , 0.0 , 0.0 , 0.4 , 0.4
       ) : PumpType;
   Pump Invocation
      ( 0.5 , 0.0 , 0.0 , 0.4 , 0.4
       ) : PumpType;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

ENDDEF (*BasePicture*);
