"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: SpecComplianceIssues"
(* Covers the spec.* finding IDs: sequence_step_prefix,
   transition_name_missing, transition_prefix. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   Cmd: boolean  := False;
   Done: boolean  := False;
   BatchStep: integer  := 0;
   TryCount: integer  := 0;

SUBMODULES
   OPMsg Invocation
      ( 0.0 , 0.0 , 0.0 , 0.4 , 0.4
       ) : OPMessage (UseSignature => True);
   MESBC Invocation
      ( 0.5 , 0.0 , 0.0 , 0.4 , 0.4
       ) : MES_BatchControl;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Dummy = Cmd;

   SEQUENCE BatchSeq (SeqControl, SeqTimer) COORD 0.0, 0.5 OBJSIZE 1.0, 0.5
      SEQINITSTEP Init
      SEQTRANSITION TrGo WAIT_FOR Cmd
      SEQSTEP step_mix
      SEQTRANSITION WAIT_FOR Done
      SEQSTEP Finish
      SEQTRANSITION MyTrans WAIT_FOR Done
   ENDSEQUENCE

ENDDEF (*BasePicture*);
