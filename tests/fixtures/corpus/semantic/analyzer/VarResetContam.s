"Syntax version 2.23, date: 2026-06-25-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-25-12:00:00.000, name: VarResetContam"
(* Covers RESET_CONTAMINATION. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   ResetType = MODULEDEFINITION DateCode_ 1
   LOCALVARIABLES
      Counter: integer  := 0;
      Other: integer  := 0;
      ResetValue: integer  := 1;
      SeqResetOld: boolean  := False;
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ModuleCode
      EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
         IF NOT OpSeq.Reset THEN
            Counter = ResetValue;
         ELSIF NOT SeqResetOld THEN
            Other = ResetValue;
         ENDIF;
         SeqResetOld = OpSeq.Reset;

      SEQUENCE OpSeq (SeqControl, SeqTimer) COORD 0.0, 0.5 OBJSIZE 1.0, 0.5
         SEQINITSTEP Init
         SEQTRANSITION TrDone WAIT_FOR False
      ENDSEQUENCE
   ENDDEF (*ResetType*);

SUBMODULES
   ResetUnit Invocation
      ( 0.0 , 0.0 , 0.0 , 0.4 , 0.4
       ) : ResetType;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

ENDDEF (*BasePicture*);
