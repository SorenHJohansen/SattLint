"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: SeqAltEdge"
(* Edge case: alternative branch with a single step and immediate transition.
   Grammar rules: seqalternative / ALTERNATIVEBRANCH. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   Sel: integer  := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   SEQUENCE Alt (SeqControl, SeqTimer) COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
      SEQINITSTEP Init
      SEQTRANSITION TrGo WAIT_FOR Sel > 0
      ALTERNATIVESEQ
         SEQTRANSITION TrA WAIT_FOR Sel == 1
         SEQSTEP OptA
         SEQTRANSITION TrDone WAIT_FOR True
      ALTERNATIVEBRANCH
         SEQTRANSITION TrB WAIT_FOR Sel == 2
         SEQSTEP OptB
         SEQTRANSITION TrDone2 WAIT_FOR True
      ENDALTERNATIVE
      SEQSTEP Finish
   ENDSEQUENCE

ENDDEF (*BasePicture*);
