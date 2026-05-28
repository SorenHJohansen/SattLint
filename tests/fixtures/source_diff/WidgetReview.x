"Syntax version 2.23, date: 2026-05-28-10:00:00.000 N"
"Original file date: ---"
"Program date: 2026-05-28-10:00:00.000, name: WidgetReview"

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   Flag: integer := 1;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Flag = Flag + 2;

ENDDEF (*BasePicture*);
