"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: MinimalSequence"
(* Covers the minimal valid SEQUENCE structure: SEQINITSTEP followed by a
   single SEQTRANSITION with no SEQSTEP.
   This is a one-shot immediate-transition pattern; the init step transitions
   immediately to done on the first scan.
   Expected: strict syntax-check passes (WARNING may appear for legacy form). *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   Done: boolean  := False;
   SeqControl: integer  := 0;
   SeqTimer: integer  := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   SEQUENCE Minimal (SeqControl, SeqTimer) COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
      SEQINITSTEP Init
         ENTERCODE
            Done = False;
      SEQTRANSITION TrDone WAIT_FOR Done
   ENDSEQUENCE

ENDDEF (*BasePicture*);
