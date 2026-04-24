"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: SequenceAlternative"
(* Covers ALTERNATIVESEQ / ALTERNATIVEBRANCH / ENDALTERNATIVE for
   mutually-exclusive conditional branching inside a SEQUENCE.
   The first transition that is true determines which branch executes.
   Expected: strict syntax-check passes. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   StartCmd: boolean  := False;
   Mode: integer  := 0;
   OutputA: integer  := 0;
   OutputB: integer  := 0;
   OutputC: integer  := 0;
   Done: boolean  := False;
   SeqControl: integer  := 0;
   SeqTimer: integer  := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   SEQUENCE AltSeq (SeqControl, SeqTimer) COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
      SEQINITSTEP Init
         ENTERCODE
            Done = False;
      SEQTRANSITION TrBegin WAIT_FOR StartCmd
      SEQSTEP Dispatch
         ENTERCODE
            OutputA = 0;
            OutputB = 0;
            OutputC = 0;
      ALTERNATIVESEQ
         SEQTRANSITION TrModeA WAIT_FOR Mode == 1
         SEQSTEP ModeA
            ACTIVECODE
               OutputA = OutputA + 1;
         SEQTRANSITION DoneA WAIT_FOR OutputA >= 5
      ALTERNATIVEBRANCH
         SEQTRANSITION TrModeB WAIT_FOR Mode == 2
         SEQSTEP ModeB
            ACTIVECODE
               OutputB = OutputB + 1;
         SEQTRANSITION DoneB WAIT_FOR OutputB >= 3
      ALTERNATIVEBRANCH
         SEQTRANSITION TrDefault WAIT_FOR Mode <> 1 AND Mode <> 2
         SEQSTEP ModeDefault
            ENTERCODE
               OutputC = -1;
         SEQTRANSITION DoneDefault WAIT_FOR True
      ENDALTERNATIVE
      SEQSTEP Finish
         ENTERCODE
            Done = True;
      SEQTRANSITION TrReset WAIT_FOR NOT StartCmd
   ENDSEQUENCE

ENDDEF (*BasePicture*);
