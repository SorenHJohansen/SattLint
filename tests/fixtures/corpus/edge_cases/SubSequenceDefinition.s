"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: SubSeqDef"
(* Edge case: SUBSEQUENCE definition as a reusable block referenced by parent.
   Grammar rule: seqsub. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   Trigger: boolean  := False;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   SEQUENCE Main (SeqControl, SeqTimer) COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
      SEQINITSTEP Init
      SEQTRANSITION TrGo WAIT_FOR True
      SUBSEQUENCE SubBlock
         SEQSTEP SubStep
         SEQTRANSITION SubDone WAIT_FOR Trigger
      ENDSUBSEQUENCE
      SEQSTEP Finish
   ENDSEQUENCE

ENDDEF (*BasePicture*);
