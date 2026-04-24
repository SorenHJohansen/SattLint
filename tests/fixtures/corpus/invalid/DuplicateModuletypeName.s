"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: DuplicateModuletypeName"
(* INVALID: Two MODULEDEFINITION types with the same name in TYPEDEFINITIONS.
   Scope uniqueness validation rejects duplicate moduletype names (case-insensitive).
   ControllerType appears twice; this is rejected at the validation stage.
   Expected: strict syntax-check fails at stage "validation". *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   ControllerType = MODULEDEFINITION DateCode_ 1
   MODULEPARAMETERS
      Setpoint: real  := 0.0;

   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ENDDEF (*ControllerType*);
   ControllerType = MODULEDEFINITION DateCode_ 2
   MODULEPARAMETERS
      Setpoint: real  := 0.0;
      Gain: real  := 1.0;

   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ENDDEF (*ControllerType*);

SUBMODULES
   Ctrl1 Invocation
      ( 0.1 , 0.1 , 0.0 , 0.4 , 0.4
       ) : ControllerType (
      Setpoint => 50.0);

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

ENDDEF (*BasePicture*);
