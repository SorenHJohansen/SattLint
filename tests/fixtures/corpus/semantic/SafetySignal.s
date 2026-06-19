"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: SafetySignal"
(* SEMANTIC: Unconsumed safety signal, external input feeding a critical sink.
   Expected: unconsumed-safety-signal, external-input-to-critical-sink. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   EStop: boolean  := False;
   GuardOpen: boolean  := False;
   MotorRun: boolean  := False;
   CmdRun: boolean  := False;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Safety COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      MotorRun = CmdRun AND NOT EStop;
      GuardOpen = True;

ENDDEF (*BasePicture*);
