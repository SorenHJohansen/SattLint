"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: OpenSequenceSeqFork"
(* Covers SEQFORK patterns across OPENSEQUENCE and SEQUENCE:
   - SEQFORK after a SEQTRANSITION (fork on transition, intra-sequence)
   - SEQFORK after a SEQSTEP, with SEQBREAK
   - SEQFORK after a SEQSTEP, without SEQBREAK
   - SEQFORK with a cross-sequence target in the same module
   SEQBREAK is optional after SEQFORK.
   Expected: strict syntax-check passes. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   RestartCmd: boolean  := False;
   AbortCmd: boolean  := False;
   RetryCount: integer  := 0;
   Output: integer  := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   OPENSEQUENCE MainOpen COORD 0.0, 0.5 OBJSIZE 1.0, 0.5
      SEQINITSTEP Init
         ENTERCODE
            RetryCount = 0;
            Output = 0;
      SEQTRANSITION TrBegin WAIT_FOR True
      SEQSTEP Working
         ACTIVECODE
            Output = Output + 1;
      ALTERNATIVESEQ
         SEQTRANSITION TrDone WAIT_FOR Output >= 10
         SEQSTEP Done
            ENTERCODE
               Output = 0;
         SEQTRANSITION TrExit WAIT_FOR True
            SEQFORK Finished SEQBREAK
      ALTERNATIVEBRANCH
         SEQTRANSITION TrRetry WAIT_FOR RestartCmd
         SEQSTEP Retry
            ENTERCODE
               RetryCount = RetryCount + 1;
               Output = 0;
               RestartCmd = False;
         SEQFORK Working SEQBREAK
      ALTERNATIVEBRANCH
         SEQTRANSITION TrAbort WAIT_FOR AbortCmd
         SEQSTEP Abort
            ENTERCODE
               Output = -1;
         SEQTRANSITION TrAbortExit WAIT_FOR True
            SEQFORK Finished SEQBREAK
      ENDALTERNATIVE
   SEQSTEP Finished
   ENDOPENSEQUENCE

   SEQUENCE Helper COORD 0.0, 0.0 OBJSIZE 1.0, 0.5
      SEQINITSTEP HInit
      SEQFORK TrHelper
      SEQTRANSITION TrHelper WAIT_FOR True
         SEQFORK Working
   ENDSEQUENCE

ENDDEF (*BasePicture*);
