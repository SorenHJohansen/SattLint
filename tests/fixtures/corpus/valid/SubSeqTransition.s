"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: SubSeqFlow"
(* Covers SUBSEQTRANSITION / ENDSUBSEQTRANSITION inside a SEQUENCE.
   A SUBSEQTRANSITION is a named sequence element that contains a full
   embedded sub-sequence body acting as a complex transition region.
   The embedded body enters through a transition before reaching a step.
   Expected: strict syntax-check passes. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   StartCmd: boolean  := False;
   CheckDone: boolean  := False;
   Ready: boolean  := False;
   Status: integer  := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   SEQUENCE MainSeq (SeqControl, SeqTimer) COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
      SEQINITSTEP Idle
         ENTERCODE
            Status = 0;
      SEQTRANSITION TrStart WAIT_FOR StartCmd
      SEQSTEP Check
         ENTERCODE
            Status = 1;
            CheckDone = False;
      SUBSEQTRANSITION TrCheckPhase
         SEQTRANSITION TrCheckEnter WAIT_FOR True
         SEQSTEP Checking
            ACTIVECODE
               CheckDone = Ready;
         SEQTRANSITION TrCheckOk WAIT_FOR CheckDone
      ENDSUBSEQTRANSITION
      SEQSTEP Active
         ACTIVECODE
            Status = 2;
      SEQTRANSITION TrDone WAIT_FOR NOT StartCmd
   ENDSEQUENCE

ENDDEF (*BasePicture*);
