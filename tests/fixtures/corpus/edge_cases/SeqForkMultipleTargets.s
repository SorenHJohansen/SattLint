"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: SeqForkMulti"
(* EDGE CASE: multi-target SEQFORK inside a strict single-file sequence.
   Grammar rule: seqfork: SEQFORK NAME ("," NAME)*
   This fixture documents the supported behavior: all listed targets are
   preserved through parse and must each resolve case-insensitively.
   Expected: strict syntax-check passes. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   OPENSEQUENCE ForkSeq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
      SEQINITSTEP Init
      SEQTRANSITION TrBegin WAIT_FOR True
      SEQSTEP PathA
      SEQTRANSITION TrAfterA WAIT_FOR True
      SEQSTEP PathB
      SEQTRANSITION TrAfterB WAIT_FOR True
      SEQSTEP Decide
      SEQTRANSITION TrFork WAIT_FOR True
         SEQFORK PathA, pathb
   ENDOPENSEQUENCE

ENDDEF (*BasePicture*);
