"Syntax version 2.23, date: 2026-04-22-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-22-12:00:00.000, name: RequiredParamConn"

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
   ChildType = MODULEDEFINITION DateCode_ 1
   MODULEPARAMETERS
      RequiredValue: integer;
   LOCALVARIABLES
      Mirror: integer := 0;

   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ModuleCode
   EQUATIONBLOCK UseParam COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Mirror = RequiredValue;

   ENDDEF (*ChildType*);

SUBMODULES
   Child Invocation
      ( 0.0 , 0.0 , 0.0 , 0.4 , 0.4
       ) : ChildType;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
