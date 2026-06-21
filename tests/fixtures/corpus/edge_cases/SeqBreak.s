"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: SeqBreak"
(* Edge case: SEQBREAK used to exit a sequence early.
   Grammar rule: seqbreak. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   SeqControl: integer  := 0;
   SeqTimer: integer  := 0;
   Abort: boolean  := False;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   SEQUENCE Abortable (SeqControl, SeqTimer) COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
      SEQINITSTEP Init
         ENTERCODE
            Abort = False;
      SEQTRANSITION TrRun WAIT_FOR True
      SEQSTEP Working
      SEQTRANSITION TrCheck WAIT_FOR Abort
      SEQBREAK
      SEQTRANSITION TrDone WAIT_FOR NOT Abort
      SEQSTEP Finish
   ENDSEQUENCE

ENDDEF (*BasePicture*);
