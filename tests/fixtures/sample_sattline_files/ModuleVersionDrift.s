"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: ModuleVersionDrift"
(* Covers semantic.module-version-drift.
   Two submodules share a moduletype name but resolve to different definitions. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   ValveV1 = MODULEDEFINITION DateCode_ 1
   MODULEPARAMETERS
      Timeout: integer  := 10;
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ENDDEF (*ValveV1*);

   ValveV2 = MODULEDEFINITION DateCode_ 2
   MODULEPARAMETERS
      Timeout: integer  := 20;
      Retry: integer  := 3;
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ENDDEF (*ValveV2*);

SUBMODULES
   OldValve Invocation
      ( 0.0 , 0.0 , 0.0 , 0.4 , 0.4
       ) : ValveV1;
   NewValve Invocation
      ( 0.5 , 0.0 , 0.0 , 0.4 , 0.4
       ) : ValveV2;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

ENDDEF (*BasePicture*);
