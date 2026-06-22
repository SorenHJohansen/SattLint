"Syntax version 2.23, date: 2026-06-22-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-22-12:00:00.000, name: VersionDrift"
(* Direct analyzer fixture for module.version_drift. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

SUBMODULES
   Mixer Invocation
      ( 0.0 , 0.0 , 0.0 , 0.4 , 0.4
       ) : MODULEDEFINITION DateCode_ 1
   LOCALVARIABLES
      Output: integer  := 0;
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ModuleCode
      EQUATIONBLOCK Logic COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
         Output = 1;

   ENDDEF (*Mixer*);

   Mixer Invocation
      ( 0.5 , 0.0 , 0.0 , 0.4 , 0.4
       ) : MODULEDEFINITION DateCode_ 2
   LOCALVARIABLES
      Output: integer  := 0;
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ModuleCode
      EQUATIONBLOCK Logic COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
         Output = 2;

   ENDDEF (*Mixer*);

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

ENDDEF (*BasePicture*);
