"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: GlobalParameterMapping"
(* Covers mixed GLOBAL and non-global parameter mappings on the same submodule.
   Some parameters are mapped from the caller's local variables (normal mapping)
   while others are mapped from GLOBAL variables (GLOBAL keyword before the name).
   Both mapping styles appear in the same parameter list.
   Expected: strict syntax-check passes. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   ControllerType = MODULEDEFINITION DateCode_ 1
   MODULEPARAMETERS
      Setpoint: real  := 0.0;
      Gain: real  := 1.0;
      SharedBias: real  := 0.0;
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
         Output = Output + Gain * Error + SharedBias;
      ENDIF;

   ENDDEF (*ControllerType*);

LOCALVARIABLES
   LocalSetpoint: real  := 75.0;
   LocalGain: real  := 0.5;
   LocalEnable: boolean  := True;

SUBMODULES
   Ctrl Invocation
      ( 0.1 , 0.1 , 0.0 , 0.8 , 0.8
       ) : ControllerType (
      Setpoint => LocalSetpoint,
      Gain => LocalGain,
      SharedBias => GLOBAL GlobalBias,
      EnableControl => LocalEnable);

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      LocalSetpoint = LocalSetpoint + 0.1;

ENDDEF (*BasePicture*);
