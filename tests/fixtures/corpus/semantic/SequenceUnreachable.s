"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: SequenceUnreachable"
(* SEMANTIC: Unreachable sequence nodes, always-true/always-false transitions,
   and duplicate transition guards.
   Expected: unreachable-sequence-node, unreachable-transition,
   transition-always-true, transition-always-false, duplicate-transition-guard. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   SeqControl: integer  := 0;
   SeqTimer: integer  := 0;
   Start: boolean  := False;
   Done: boolean  := False;
   Flag: boolean  := False;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   SEQUENCE Sfc (SeqControl, SeqTimer) COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
      SEQINITSTEP Init
         ENTERCODE
            Flag = False;
      SEQTRANSITION TrGo WAIT_FOR Start
      SEQTRANSITION TrDead WAIT_FOR False
      SEQSTEP Unreachable
         ENTERCODE
            Flag = True;
      SEQTRANSITION TrDup WAIT_FOR Done
      SEQTRANSITION TrDup WAIT_FOR Done
   ENDSEQUENCE

ENDDEF (*BasePicture*);
