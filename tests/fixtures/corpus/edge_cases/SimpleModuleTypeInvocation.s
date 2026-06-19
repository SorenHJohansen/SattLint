"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: SimpleModuleTypeInv"
(* Edge case: moduletype (not MODULEDEFINITION) in submodule invocation.
   Grammar rule: invocation_module_type. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   PumpType = MODULEDEFINITION DateCode_ 1
   MODULEPARAMETERS
      Speed: real;
   LOCALVARIABLES
      Running: boolean  := False;
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ModuleCode
   EQUATIONBLOCK Eq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Running = Speed > 0.0;
   ENDDEF (*PumpType*);

LOCALVARIABLES
   SpeedRef: real  := 50.0;

SUBMODULES
   Pump Invocation
      ( 0.0 , 0.0 , 0.0 , 0.5 , 0.5
       ) : PumpType (
      Speed => SpeedRef);

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

ENDDEF (*BasePicture*);
