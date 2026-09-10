"Syntax version 2.23, date: 2026-06-22-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-22-12:00:00.000, name: UnsafeDefaults"
(* Dedicated unsafe-defaults analyzer fixture.
   Expected: unsafe_defaults.true_boolean_default (EnablePump, SafetyBypass). *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   EnablePump: boolean  := True;
   SafetyBypass: boolean  := True;
   Stock: integer  := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Stock = 1;

ENDDEF (*BasePicture*);
