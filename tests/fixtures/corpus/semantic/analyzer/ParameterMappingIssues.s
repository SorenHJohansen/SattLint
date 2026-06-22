"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: ParamMappingIssues"
(* Covers CONTRACT_MISMATCH, REQUIRED_PARAMETER_CONNECTION, MIN_MAX_MAPPING_MISMATCH.
   Expected: strict syntax-check passes. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   ValveType = MODULEDEFINITION DateCode_ 1
   MODULEPARAMETERS
      CmdOpen: boolean;
      CmdClose: boolean;
      Timeout: duration := Duration_Value "5s";
      LimitMin: real  := 0.0;
      LimitMax: real  := 100.0;
   LOCALVARIABLES
      Position: real  := 0.0;
      ValveState: boolean  := False;
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ModuleCode
   EQUATIONBLOCK Eq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      IF CmdOpen THEN
         ValveState = True;
      ENDIF;
      IF CmdClose THEN
         ValveState = False;
      ENDIF;
      Position = LimitMin + (LimitMax - LimitMin) * 0.5;
   ENDDEF (*ValveType*);

   SimpleValve = MODULEDEFINITION DateCode_ 1
   MODULEPARAMETERS
      Enable: boolean;
      Setpoint: real;
   LOCALVARIABLES
      OutVal: real  := 0.0;
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ModuleCode
   EQUATIONBLOCK Eq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      OutVal = Setpoint;
   ENDDEF (*SimpleValve*);

LOCALVARIABLES
   OpenCmd: boolean  := False;
   CloseCmd: boolean  := False;
   PosValue: real  := 0.0;
   RawValue: integer  := 0;

SUBMODULES
   ValveOk Invocation
      ( 0.0 , 0.0 , 0.0 , 0.4 , 0.4
       ) : ValveType (
      CmdOpen => OpenCmd,
      CmdClose => CloseCmd,
      Timeout => Duration_Value "10s",
      LimitMin => 5.0,
      LimitMax => 95.0);

   ValveMissing Invocation
      ( 0.5 , 0.0 , 0.0 , 0.4 , 0.4
       ) : ValveType (
      CmdOpen => OpenCmd);

   ValveTypeMismatch Invocation
      ( 0.0 , 0.5 , 0.0 , 0.4 , 0.4
       ) : SimpleValve (
      Enable => OpenCmd,
      Setpoint => RawValue);

   ValveMinMax Invocation
      ( 0.5 , 0.5 , 0.0 , 0.4 , 0.4
       ) : ValveType (
      CmdOpen => OpenCmd,
      CmdClose => CloseCmd,
      LimitMin => 200.0,
      LimitMax => -10.0);

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      PosValue = ValveOk.Position + 1.0;

ENDDEF (*BasePicture*);
