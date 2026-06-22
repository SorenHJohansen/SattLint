"Syntax version 2.23, date: 2026-06-22-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-22-12:00:00.000, name: IllegalStateComb"
(* SEMANTIC: Parallel steps Idle and Running are configured as mutually
   exclusive in the corpus manifest.
   Expected: semantic.illegal-state-combination. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   StartCmd: boolean  := False;
   GoParallel: boolean  := False;
   MergeCmd: boolean  := False;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   SEQUENCE Conflict (SeqControl, SeqTimer) COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
      SEQINITSTEP Init
      SEQTRANSITION TrStart WAIT_FOR StartCmd
      SEQSTEP Fork
         ENTERCODE
            GoParallel = True;
      SEQTRANSITION TrFork WAIT_FOR GoParallel
      PARALLELSEQ
         SEQSTEP Idle
         SEQTRANSITION TrIdleDone WAIT_FOR MergeCmd
         SEQSTEP IdleDone
      PARALLELBRANCH
         SEQSTEP Running
         SEQTRANSITION TrRunDone WAIT_FOR MergeCmd
         SEQSTEP RunDone
      ENDPARALLEL
      SEQTRANSITION TrReset WAIT_FOR NOT MergeCmd
   ENDSEQUENCE

ENDDEF (*BasePicture*);
