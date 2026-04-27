"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: SequenceBasic"
(* Covers the core SEQUENCE constructs:
   - SEQINITSTEP with ENTERCODE and EXITCODE
   - SEQSTEP with ENTERCODE, ACTIVECODE, EXITCODE
   - SEQTRANSITION WAIT_FOR with a boolean expression
   - SeqControl and SeqTimer optional control parameters
   Expected: strict syntax-check passes. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   StartCmd: boolean  := False;
   StopCmd: boolean  := False;
   Output: integer  := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   SEQUENCE MainSeq (SeqControl, SeqTimer) COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
      SEQINITSTEP Idle
         ENTERCODE
            Output = 0;
         EXITCODE
            StartCmd = False;
      SEQTRANSITION TrStart WAIT_FOR StartCmd
      SEQSTEP Running
         ENTERCODE
            Output = 1;
         ACTIVECODE
            Output = Output + 1;
         EXITCODE
            Output = 0;
      SEQTRANSITION TrStop WAIT_FOR StopCmd OR Output > 100
      SEQSTEP Stopping
         ENTERCODE
            Output = -1;
         EXITCODE
            StopCmd = False;
      SEQTRANSITION TrDone WAIT_FOR NOT StopCmd
   ENDSEQUENCE

ENDDEF (*BasePicture*);
