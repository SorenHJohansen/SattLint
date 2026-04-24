"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: SeqForkMultipleTargets"
(* EDGE CASE: SEQFORK jump to a named step in an OPENSEQUENCE.
   Grammar rule: seqfork: SEQFORK NAME ("," NAME)*
   A single SEQFORK target is the common case. Multiple comma-separated
   targets are accepted by the grammar but the transformer currently
   handles single-target form only.
   This fixture tests the single-target jump-to-step form.
   Expected: strict syntax-check passes. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   UsePathA: boolean  := True;
   RetryCount: integer  := 0;
   Output: integer  := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   OPENSEQUENCE ForkSeq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
      SEQINITSTEP Init
         ENTERCODE
            RetryCount = 0;
            Output = 0;
      SEQTRANSITION TrBegin WAIT_FOR True
      SEQSTEP PathA
         ENTERCODE
            Output = 1;
      SEQTRANSITION TrAfterA WAIT_FOR True
      SEQSTEP PathB
         ENTERCODE
            Output = 2;
      SEQTRANSITION TrAfterB WAIT_FOR True
      SEQSTEP Decide
         ENTERCODE
            RetryCount = RetryCount + 1;
      ALTERNATIVESEQ
         SEQTRANSITION TrPickA WAIT_FOR UsePathA
            SEQFORK PathA
      ALTERNATIVEBRANCH
         SEQTRANSITION TrPickB WAIT_FOR NOT UsePathA
            SEQFORK PathB
      ENDALTERNATIVE
   ENDOPENSEQUENCE

ENDDEF (*BasePicture*);
