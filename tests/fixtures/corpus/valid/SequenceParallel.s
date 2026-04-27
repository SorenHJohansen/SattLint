"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: SequenceParallel"
(* Covers PARALLELSEQ / PARALLELBRANCH / ENDPARALLEL for concurrent
   branches executing simultaneously inside a SEQUENCE.
   Both branches must complete before the sequence continues.
   Each parallel branch ends with a step before PARALLELBRANCH/ENDPARALLEL.
   A transition follows ENDPARALLEL before the sequence continues.
   Expected: strict syntax-check passes. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   StartCmd: boolean  := False;
   DoneA: boolean  := False;
   DoneB: boolean  := False;
   OutputA: integer  := 0;
   OutputB: integer  := 0;
   Combined: integer  := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   SEQUENCE ParSeq (SeqControl, SeqTimer) COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
      SEQINITSTEP Init
         ENTERCODE
            DoneA = False;
            DoneB = False;
      SEQTRANSITION TrStart WAIT_FOR StartCmd
      SEQSTEP Launch
         ENTERCODE
            OutputA = 0;
            OutputB = 0;
      SEQTRANSITION TrFork WAIT_FOR True
      PARALLELSEQ
         SEQSTEP BranchA
            ACTIVECODE
               OutputA = OutputA + 1;
         SEQTRANSITION TrDoneA WAIT_FOR OutputA >= 3
         SEQSTEP FinishA
            ENTERCODE
               DoneA = True;
         SEQTRANSITION TrExitA WAIT_FOR DoneA
         SEQSTEP JoinedA
      PARALLELBRANCH
         SEQSTEP BranchB
            ACTIVECODE
               OutputB = OutputB + 1;
         SEQTRANSITION TrDoneB WAIT_FOR OutputB >= 5
         SEQSTEP FinishB
            ENTERCODE
               DoneB = True;
         SEQTRANSITION TrExitB WAIT_FOR DoneB
         SEQSTEP JoinedB
      ENDPARALLEL
      SEQTRANSITION TrMerge WAIT_FOR DoneA AND DoneB
      SEQSTEP Merge
         ENTERCODE
            Combined = OutputA + OutputB;
      SEQTRANSITION TrReset WAIT_FOR NOT StartCmd
   ENDSEQUENCE

ENDDEF (*BasePicture*);
