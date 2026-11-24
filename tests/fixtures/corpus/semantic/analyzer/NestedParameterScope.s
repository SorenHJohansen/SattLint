"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: NestedParameterScope"
(* SEMANTIC: a nested module declares a parameter with the same name as the
   enclosing module's parameter, and the value is forwarded through a frame
   module. A parameter forwards the caller's variable instead of hiding it, so
   this is neither shadowing nor an unused parameter.
   Expected finding: none. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

MODULEPARAMETERS
   Setting: integer  := 0;

SUBMODULES
   Middle Invocation
      ( 0.1 , 0.1 , 0.0 , 0.8 , 0.8
       ) : MODULEDEFINITION DateCode_ 2
   MODULEPARAMETERS
      Setting: integer  := 1;
   SUBMODULES
      Panel Invocation
         ( 0.1 , 0.1 , 0.0 , 0.8 , 0.8
         IgnoreMaxModule ) : MODULEDEFINITION DateCode_ 3 ( Frame_Module )
      SUBMODULES
         Worker Invocation
            ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
             ) : MODULEDEFINITION DateCode_ 4
         MODULEPARAMETERS
            Setting: integer  := 2;

         ModuleDef
         ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
         ModuleCode
         EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
            Setting = Setting + Setting;

         ENDDEF (*Worker*) ( Setting => Setting );

      ModuleDef
      ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
      ENDDEF (*Panel*);

   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ENDDEF (*Middle*) ( Setting => Setting );

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
