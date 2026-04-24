"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: SubsequenceBlock"
(* Covers SUBSEQUENCE / ENDSUBSEQUENCE inside a SEQUENCE.
   A SUBSEQUENCE groups a named block of steps and transitions that can be
   reused or jumped into via SEQFORK. The subsequence contains its own
   SEQSTEP + SEQTRANSITION elements.
   Expected: strict syntax-check passes. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   StartCmd: boolean  := False;
   DoneCmd: boolean  := False;
   Status: integer  := 0;
   SeqControl: integer  := 0;
   SeqTimer: integer  := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   SEQUENCE MainSeq (SeqControl, SeqTimer) COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
      SEQINITSTEP Idle
         ENTERCODE
            Status = 0;
      SEQTRANSITION TrStart WAIT_FOR StartCmd
      SEQSTEP Prepare
         ENTERCODE
            Status = 1;
      SEQTRANSITION TrReady WAIT_FOR True
      SUBSEQUENCE WorkPhase
         SEQSTEP WorkEntry
            ENTERCODE
               Status = 2;
         SEQTRANSITION TrWorkLoop WAIT_FOR True
         SEQSTEP WorkLoop
            ACTIVECODE
               Status = Status + 1;
         SEQTRANSITION TrWorkDone WAIT_FOR DoneCmd
      ENDSUBSEQUENCE
      SEQSTEP Cleanup
         ENTERCODE
            Status = -1;
         EXITCODE
            StartCmd = False;
            DoneCmd = False;
      SEQTRANSITION TrEnd WAIT_FOR NOT StartCmd
   ENDSEQUENCE

ENDDEF (*BasePicture*);
