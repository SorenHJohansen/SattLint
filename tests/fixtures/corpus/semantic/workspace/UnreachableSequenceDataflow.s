"Syntax version 2.23, date: 2026-06-22-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-22-12:00:00.000, name: UnreachSeqFlow"
(* SEMANTIC: A sequence step appears after SEQBREAK in the same sequence.
   Expected: semantic.unreachable-sequence-node-dataflow. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   StartCmd: boolean  := False;
   AbortCmd: boolean  := False;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   SEQUENCE DeadBranch (SeqControl, SeqTimer) COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
      SEQINITSTEP Init
      SEQTRANSITION TrRun WAIT_FOR StartCmd
      SEQSTEP Working
      SEQTRANSITION TrAbort WAIT_FOR AbortCmd
      SEQBREAK
      SEQTRANSITION TrDone WAIT_FOR NOT AbortCmd
      SEQSTEP AfterBreak
   ENDSEQUENCE

ENDDEF (*BasePicture*);
