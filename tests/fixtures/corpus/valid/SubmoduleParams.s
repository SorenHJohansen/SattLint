"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: SubmoduleParams"
(* Covers MODULEDEFINITION submodule types and module instantiation with
   parameter mappings including:
   - Inline MODULEDEFINITION type in TYPEDEFINITIONS
   - Parameters mapped by variable reference
   - Parameters mapped by literal value
   - Parameters mapped via GLOBAL keyword
   - Nested submodule (module inside a module)
   Expected: strict syntax-check passes. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   ControllerType = MODULEDEFINITION DateCode_ 1
   MODULEPARAMETERS
      Setpoint: real  := 0.0;
      Gain: real  := 1.0;
      EnableControl: boolean  := False;
   LOCALVARIABLES
      Error: real  := 0.0;
      Output: real  := 0.0;

   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ModuleCode
   EQUATIONBLOCK Ctrl COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      IF EnableControl THEN
         Error = Setpoint - Output;
         Output = Output + Gain * Error;
      ENDIF;

   ENDDEF (*ControllerType*);

LOCALVARIABLES
   ProcessSetpoint: real  := 75.0;
   ControlGain: real  := 0.5;
   ControlEnabled: boolean  := True;

SUBMODULES
   Controller1 Invocation
      ( 0.1 , 0.1 , 0.0 , 0.4 , 0.4
       ) : ControllerType (
      Setpoint => ProcessSetpoint,
      Gain => ControlGain,
      EnableControl => ControlEnabled);

   Controller2 Invocation
      ( 0.6 , 0.1 , 0.0 , 0.4 , 0.4
       ) : ControllerType (
      Setpoint => GLOBAL GlobalSetpoint,
      Gain => 2.0,
      EnableControl => False);

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

ENDDEF (*BasePicture*);
