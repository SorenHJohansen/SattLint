"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: SignalLifecycle"
(* SEMANTIC: Signal lifecycle coverage for the wave-2 analyzer.
   - InputSignal is consumed before any definite write in the scope.
   - NeverConsumed is written but never consumed later in the scope.
   Expected findings include the signal-lifecycle semantic rules. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   InputSignal: boolean;
   OutputSignal: boolean  := False;
   NeverConsumed: boolean  := False;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Logic COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      OutputSignal = InputSignal;
      InputSignal = True;
      OutputSignal = OutputSignal;
      NeverConsumed = False;

ENDDEF (*BasePicture*);
