"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: ConsecutiveSeqSteps"
(* INVALID: Two SEQSTEP nodes without an intervening SEQTRANSITION.
   Post-transform validation rejects consecutive SEQSTEPs with no transition
   between them. A SEQTRANSITION is required between every pair of steps.
   Expected: strict syntax-check fails at stage "validation". *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   Output: integer  := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   SEQUENCE BadSeq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
      SEQINITSTEP Init
         EXITCODE
            Output = 0;
      SEQTRANSITION TrStart WAIT_FOR True
      SEQSTEP Step1
         ACTIVECODE
            Output = 1;
      SEQSTEP Step2
         ACTIVECODE
            Output = 2;
      SEQTRANSITION TrDone WAIT_FOR True
   ENDSEQUENCE

ENDDEF (*BasePicture*);
