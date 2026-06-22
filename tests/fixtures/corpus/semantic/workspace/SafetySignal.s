"Syntax version 2.23, date: 2026-06-22-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-22-12:00:00.000, name: SafetySignal"
(* SEMANTIC: OperatorCommand flows through a moduletype mapping into
   EmergencyShutdown, which is never consumed.
   Expected: semantic.external-input-to-critical-sink,
   semantic.unconsumed-safety-signal. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   GuardType = MODULEDEFINITION DateCode_ 1
   MODULEPARAMETERS
      InCommand: boolean  := False;
   LOCALVARIABLES
      EmergencyShutdown: boolean  := False;
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ModuleCode
      EQUATIONBLOCK GuardEq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
         EmergencyShutdown = InCommand;
   ENDDEF (*GuardType*);

LOCALVARIABLES
   OperatorCommand: boolean  := False;

SUBMODULES
   Guard Invocation
      ( 0.0 , 0.0 , 0.0 , 0.4 , 0.4
       ) : GuardType (
      InCommand => OperatorCommand);

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Safety COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
   OperatorCommand = True;

ENDDEF (*BasePicture*);
