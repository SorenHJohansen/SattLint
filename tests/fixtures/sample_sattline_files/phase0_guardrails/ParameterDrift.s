"Syntax version 2.23, date: 2026-04-22-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-22-12:00:00.000, name: ParameterDrift"

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
   DoseValve = MODULEDEFINITION DateCode_ 1
   MODULEPARAMETERS
      Timeout: integer := 10;

   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ENDDEF (*DoseValve*);

SUBMODULES
   ValveA Invocation
      ( 0.0 , 0.0 , 0.0 , 0.4 , 0.4
       ) : DoseValve (
      Timeout => 10);
   ValveB Invocation
      ( 0.5 , 0.0 , 0.0 , 0.4 , 0.4
       ) : DoseValve (
      Timeout => 15);

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);