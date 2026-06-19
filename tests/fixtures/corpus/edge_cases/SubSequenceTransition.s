"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: SubSeqTransition"
(* Edge case: transition inside a subsequence referencing the parent step label.
   Grammar rule: seqtransitionsub. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   SeqControl: integer  := 0;
   SeqTimer: integer  := 0;
   Flag: boolean  := False;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   SEQUENCE Main (SeqControl, SeqTimer) COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
      SEQINITSTEP Start
         ENTERCODE
            Flag = False;
      SEQTRANSITION Tr1 WAIT_FOR Flag
      SEQSTEP StepA
         ENTERCODE
            Flag = False;
      SEQTRANSITION TrA WAIT_FOR Flag
   ENDSEQUENCE

ENDDEF (*BasePicture*);
