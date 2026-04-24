"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: CommentInsideEquation"
(* EDGE CASE: Comments are allowed inside EQUATIONBLOCK and SEQUENCE bodies.
   Only freestanding comments directly inside ModuleCode (before the first
   EQUATIONBLOCK or SEQUENCE) are rejected.
   This fixture verifies that in-body comments do NOT trigger a validation error.
   Expected: strict syntax-check passes. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   A, B: integer  := 0;
   StartCmd: boolean  := False;
   Output: integer  := 0;
   SeqControl: integer  := 0;
   SeqTimer: integer  := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Calc COORD 0.0, 0.0 OBJSIZE 1.0, 0.5 :
      (* Comment before first statement in EQUATIONBLOCK - valid *)
      A = A + 1;
      (* Comment between statements - valid *)
      B = A * 2;
      (* Comment at end of block - valid *)

   SEQUENCE Seq (SeqControl, SeqTimer) COORD 0.0, 0.5 OBJSIZE 1.0, 0.5
      SEQINITSTEP Init
         ENTERCODE
            (* Comment in step ENTERCODE - valid *)
            Output = 0;
      SEQTRANSITION TrStart WAIT_FOR (* inline comment is stripped *) StartCmd
      SEQSTEP Running
         ACTIVECODE
            (* Comment in step ACTIVECODE - valid *)
            Output = Output + 1;
      SEQTRANSITION TrDone WAIT_FOR Output >= 10
   ENDSEQUENCE

ENDDEF (*BasePicture*);
