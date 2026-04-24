"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: SeqForkUnknownTarget"
(* INVALID: SEQFORK to a step name that does not exist in the sequence.
   Post-transform validation rejects unknown SEQFORK targets; the named step
   'MissingTarget' is never defined as a SEQINITSTEP or SEQSTEP.
   Expected: strict syntax-check fails at stage "validation". *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   JumpCmd: boolean  := False;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   OPENSEQUENCE MainSeq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
      SEQINITSTEP Init
         ENTERCODE
            JumpCmd = False;
      SEQTRANSITION TrBegin WAIT_FOR True
      SEQSTEP Running
         ENTERCODE
            JumpCmd = False;
      ALTERNATIVESEQ
         SEQTRANSITION TrDone WAIT_FOR NOT JumpCmd
            SEQBREAK
      ALTERNATIVEBRANCH
         SEQTRANSITION TrJump WAIT_FOR JumpCmd
            SEQFORK MissingTarget
      ENDALTERNATIVE
   ENDOPENSEQUENCE

ENDDEF (*BasePicture*);
