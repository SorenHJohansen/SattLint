"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: SeqLifetimeIssues"
(* Covers RESET_CONTAMINATION, IMPLICIT_LATCH, RECORD_COMPONENT_ORDER_DEPENDENCE.
   RECORD_COMPONENT_ORDER_DEPENDENCE has no semantic.* mapping — assert on IssueKind directly.
   Expected: strict syntax-check passes. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   MixRecord = RECORD DateCode_ 1
      IngredientA: real  := 0.0;
      IngredientB: real  := 0.0;
      Total: real  := 0.0;
   ENDDEF
    (*MixRecord*);

LOCALVARIABLES

   StartCmd: boolean  := False;
   MixDone: boolean  := False;
   ResetCmd: boolean  := False;
   StaleValue: integer  := 0;
   LatchValue: boolean  := False;
   Condition: boolean  := False;
   Batch: MixRecord ;
   BatchTotal: real  := 0.0;
   CleanValue: boolean  := False;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      BatchTotal = Batch.IngredientA + Batch.IngredientB;
      IF NOT ResetCmd THEN
         StaleValue = StaleValue + 1;
      ENDIF;
      IF Condition THEN
         LatchValue = True;
      ENDIF;
      CleanValue = Condition;

   SEQUENCE MixSeq (SeqControl, SeqTimer) COORD 0.0, 0.5 OBJSIZE 1.0, 0.5
      SEQINITSTEP Idle
         ENTERCODE
            MixDone = False;
      SEQTRANSITION TrStart WAIT_FOR StartCmd
      SEQSTEP Mixing
         ENTERCODE
            Batch.IngredientA = 10.0;
            Batch.IngredientB = 20.0;
            Batch.Total = Batch.IngredientA + Batch.IngredientB;
      SEQTRANSITION TrDone WAIT_FOR MixDone
      SEQSTEP Finish
         ENTERCODE
            MixDone = True;
      SEQTRANSITION TrReset WAIT_FOR ResetCmd
   ENDSEQUENCE

ENDDEF (*BasePicture*);
