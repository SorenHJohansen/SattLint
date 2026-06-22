"Syntax version 2.23, date: 2026-04-22-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-22-12:00:00.000, name: ScanLoopCost"

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
   SysVarId: string := "ScanLoop.Cost";
   Value: string := "Active";
   Status: integer := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      AssignSystemString(SysVarId, Value, Status);

ENDDEF (*BasePicture*);
