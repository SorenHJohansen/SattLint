"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: PowerUp"
(* Covers semantic.missing-parameter-initial-value and semantic.unsafe-default-true.
   Delegates to initial_values + unsafe_defaults sub-analyzers. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   StartupBlock = MODULEDEFINITION DateCode_ 1
   MODULEPARAMETERS
      Delay: integer;
      Enabled: boolean  := True;
   LOCALVARIABLES
      Active: boolean  := False;
      Timer: integer  := 0;
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ModuleCode
   EQUATIONBLOCK Eq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      IF Enabled THEN
         Active = True;
      ENDIF;
   ENDDEF (*StartupBlock*);

SUBMODULES
   Starter Invocation
      ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
       ) : StartupBlock (
      Delay => 100,
      Enabled => True);

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

ENDDEF (*BasePicture*);
