"Syntax version 2.23, date: 2026-06-25-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-25-12:00:00.000, name: SameCycRdWr"
(* Covers PARALLEL_READ_WRITE_HAZARD. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   StartCmd: boolean  := False;
   SharedValue: integer  := 0;
   Output: integer  := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   SEQUENCE SeqMain (SeqControl, SeqTimer) COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
      SEQINITSTEP Init
      SEQTRANSITION TrStart WAIT_FOR StartCmd
      PARALLELSEQ
         SEQSTEP Left
            ACTIVECODE
               Output = SharedValue;
         SEQTRANSITION TrLeftDone WAIT_FOR True
         SEQSTEP LeftJoined
      PARALLELBRANCH
         SEQSTEP Right
            ACTIVECODE
               SharedValue = 2;
         SEQTRANSITION TrRightDone WAIT_FOR True
         SEQSTEP RightJoined
      ENDPARALLEL
      SEQTRANSITION TrMerge WAIT_FOR True
   ENDSEQUENCE

ENDDEF (*BasePicture*);
