"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: FaultAndConfig"
(* SEMANTIC: Unhandled fault path, missing initial value, config drift,
   conflicting loop setpoint.
   Expected: fault-unhandled-path, missing-parameter-initial-value,
   instance-configuration-drift, loop-conflicting-setpoint. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   ValveCfg = MODULEDEFINITION DateCode_ 1
   MODULEPARAMETERS
      Timeout: integer;
      Setpoint: real  := 50.0;
   LOCALVARIABLES
      Position: real  := 0.0;
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ModuleCode
   EQUATIONBLOCK Eq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Position = Setpoint;
   ENDDEF (*ValveCfg*);

LOCALVARIABLES
   FaultFlag: boolean  := False;
   Ack: boolean  := False;

SUBMODULES
   ValveA Invocation
      ( 0.0 , 0.0 , 0.0 , 0.4 , 0.4
       ) : ValveCfg (
      Timeout => 10,
      Setpoint => 50.0);

   ValveB Invocation
      ( 0.5 , 0.0 , 0.0 , 0.4 , 0.4
       ) : ValveCfg (
      Timeout => 15,
      Setpoint => 60.0);

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      FaultFlag = True;

ENDDEF (*BasePicture*);
