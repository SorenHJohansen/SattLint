"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: SeqParEdge"
(* Edge case: parallel branch with two simultaneous steps.
   Grammar rules: seqparallel / PARALLELBRANCH. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   SeqControl: integer  := 0;
   SeqTimer: integer  := 0;
   DoneA: boolean  := False;
   DoneB: boolean  := False;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   SEQUENCE Par (SeqControl, SeqTimer) COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
      SEQINITSTEP Init
      SEQTRANSITION TrGo WAIT_FOR True
      PARALLELSEQ
         SEQSTEP BranchA
         SEQTRANSITION TrA WAIT_FOR DoneA
      PARALLELBRANCH
         SEQSTEP BranchB
         SEQTRANSITION TrB WAIT_FOR DoneB
      ENDPARALLEL
      SEQSTEP Sync
   ENDSEQUENCE

ENDDEF (*BasePicture*);
