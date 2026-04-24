"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: DuplicateSiblingSubmodules"
(* INVALID: Two sibling submodule instances with the same name.
   Scope uniqueness validation rejects duplicate sibling submodule instance
   names within the same declaration scope (single-file strict check).
   Expected: strict syntax-check fails at stage "validation". *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   ChildType = MODULEDEFINITION DateCode_ 1
   MODULEPARAMETERS
      Value: integer  := 0;

   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ENDDEF (*ChildType*);

SUBMODULES
   SensorA Invocation
      ( 0.1 , 0.1 , 0.0 , 0.3 , 0.3
       ) : ChildType (
      Value => 1);

   SensorA Invocation
      ( 0.5 , 0.1 , 0.0 , 0.3 , 0.3
       ) : ChildType (
      Value => 2);

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

ENDDEF (*BasePicture*);
