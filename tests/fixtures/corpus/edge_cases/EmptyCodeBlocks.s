"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: EmptyCodeBlocks"
(* Covers ENTERCODE / ACTIVECODE / EXITCODE blocks present with no statements.
   The grammar defines each code block as accepting zero or more statements
   so empty blocks are syntactically valid even though they produce no code.
   Expected: strict syntax-check passes. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   StartCmd: boolean  := False;
   Status: integer  := 0;
   SeqControl: integer  := 0;
   SeqTimer: integer  := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   SEQUENCE EmptyBlockSeq (SeqControl, SeqTimer) COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
      SEQINITSTEP Init
         ENTERCODE
         ACTIVECODE
         EXITCODE
      SEQTRANSITION TrStart WAIT_FOR StartCmd
      SEQSTEP StepA
         ENTERCODE
            Status = 1;
         ACTIVECODE
         EXITCODE
      SEQTRANSITION TrADone WAIT_FOR True
      SEQSTEP StepB
         ENTERCODE
         ACTIVECODE
            Status = 2;
         EXITCODE
            StartCmd = False;
      SEQTRANSITION TrEnd WAIT_FOR NOT StartCmd
   ENDSEQUENCE

ENDDEF (*BasePicture*);
