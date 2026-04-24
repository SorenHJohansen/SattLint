"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: OldNewOnDottedStateField"
(* EDGE CASE: :Old accessed on a dotted record field that is declared State.
   Validation must resolve the final field's state flag, not just the root
   record variable. CMD.WaterPipeFull:Old is valid because the leaf field
   WaterPipeFull is declared with the State modifier.
   CMD.Other:Old is invalid because Other is not a State field (see invalid fixture).
   Expected: strict syntax-check passes. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   CmdType = RECORD DateCode_ 1
      WaterPipeFull: boolean State  := False;
      Other: boolean  := False;
   ENDDEF
    (*CmdType*);

LOCALVARIABLES
   CMD: CmdType ;
   PipeJustFull: boolean  := False;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      (* Rising edge on a State field accessed through a record variable *)
      PipeJustFull = CMD.WaterPipeFull:New AND NOT CMD.WaterPipeFull:Old;

ENDDEF (*BasePicture*);
