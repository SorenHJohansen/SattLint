"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: StepContract"
(* SEMANTIC: Missing enter/exit contracts on sequence steps and state leakage.
   Expected: missing-step-enter-contract, missing-step-exit-contract,
   step-state-leakage. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   SeqControl: integer  := 0;
   SeqTimer: integer  := 0;
   Go: boolean  := False;
   Done: boolean  := False;
   Shared: integer  := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   SEQUENCE ContractTest (SeqControl, SeqTimer) COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
      SEQINITSTEP Init
         ENTERCODE
            Shared = 0;
      SEQTRANSITION TrGo WAIT_FOR Go
      SEQSTEP Leaky
         ENTERCODE
            Shared = 1;
         EXITCODE
            Shared = Shared + 1;
      SEQTRANSITION TrDone WAIT_FOR Done
   ENDSEQUENCE

ENDDEF (*BasePicture*);
