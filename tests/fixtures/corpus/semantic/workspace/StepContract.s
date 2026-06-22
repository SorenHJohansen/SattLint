"Syntax version 2.23, date: 2026-06-22-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-22-12:00:00.000, name: StepContract"
(* SEMANTIC: Run is configured with required enter/exit writes in the corpus
   manifest but reads step state written by Prime instead.
   Expected: semantic.missing-step-enter-contract,
   semantic.missing-step-exit-contract, semantic.step-state-leakage. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   StartCmd: boolean  := False;
   PrimeReady: boolean  := False;
   DoneCmd: boolean  := False;
   StepValue: integer  := 0;
   Output: integer  := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   SEQUENCE ContractSequence (SeqControl, SeqTimer) COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
      SEQINITSTEP Init
      SEQTRANSITION TrStart WAIT_FOR StartCmd
      SEQSTEP Prime
         ACTIVECODE
            StepValue = 1;
            PrimeReady = True;
      SEQTRANSITION TrRun WAIT_FOR PrimeReady
      SEQSTEP Run
         ACTIVECODE
            Output = StepValue;
      SEQTRANSITION TrDone WAIT_FOR DoneCmd
   ENDSEQUENCE

ENDDEF (*BasePicture*);
