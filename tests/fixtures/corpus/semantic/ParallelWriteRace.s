"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: ParallelWriteRace"
(* SEMANTIC: Two branches of a PARALLELSEQ block both write to the same
   variable in their step code. Because parallel branches execute concurrently
   the scan outcome is non-deterministic — whichever branch runs last wins.
   Expected finding: semantic.parallel-write-race for 'SharedOutput'.
   Expected: strict syntax-check passes; SFC analyzer reports parallel-write-race. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   StartCmd: boolean  := False;
   SharedOutput: integer  := 0;
   SeqControl: integer  := 0;
   SeqTimer: integer  := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   SEQUENCE RaceSeq (SeqControl, SeqTimer) COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
      SEQINITSTEP Init
         ENTERCODE
            SharedOutput = 0;
      SEQTRANSITION TrStart WAIT_FOR StartCmd
      SEQSTEP Fork
         ENTERCODE
            SharedOutput = 0;
      SEQTRANSITION TrFork WAIT_FOR True
      PARALLELSEQ
         SEQSTEP BranchLeft
            ACTIVECODE
               SharedOutput = 1;
         SEQTRANSITION TrLeftDone WAIT_FOR True
      PARALLELBRANCH
         SEQSTEP BranchRight
            ACTIVECODE
               SharedOutput = 2;
         SEQTRANSITION TrRightDone WAIT_FOR True
      ENDPARALLEL
      SEQSTEP Merge
         ENTERCODE
            StartCmd = False;
      SEQTRANSITION TrReset WAIT_FOR NOT StartCmd
   ENDSEQUENCE

ENDDEF (*BasePicture*);
