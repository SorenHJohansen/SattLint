"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: UnreachablSeqDatafl"
(* SEMANTIC: A sequence node that is never reached based on dataflow analysis
   (e.g., a step after an always-false guard).
   Expected: unreachable-sequence-node-dataflow. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   Dummy: boolean  := False;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   SEQUENCE DeadBranch (SeqControl, SeqTimer) COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
      SEQINITSTEP Init
      SEQTRANSITION TrGo WAIT_FOR True
      SEQSTEP Live
      SEQTRANSITION TrDead WAIT_FOR False AND True
      SEQSTEP NeverHere
      SEQTRANSITION TrDone WAIT_FOR True
   ENDSEQUENCE

ENDDEF (*BasePicture*);
