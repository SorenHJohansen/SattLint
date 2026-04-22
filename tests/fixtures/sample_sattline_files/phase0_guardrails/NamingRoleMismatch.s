"Syntax version 2.23, date: 2026-04-22-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-22-12:00:00.000, name: NamingRoleMismatch"

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
   FlowRate: integer := 0;
   PumpSpeed: integer := 0;
   tank_level: integer := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);