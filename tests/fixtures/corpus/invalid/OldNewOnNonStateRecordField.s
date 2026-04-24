"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: OldNewOnNonStateRecordField"
(* INVALID: :Old accessed on a record field that is NOT declared as State.
   Validation resolves the final leaf field's state flag before accepting :Old.
   CMD.Other is a plain boolean (no State modifier), so CMD.Other:Old is invalid
   even though CMD.WaterPipeFull is a State field in the same record.
   Expected: strict syntax-check fails at stage "validation". *)

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
   Output: boolean  := False;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      (* CMD.Other is not a State field - :Old is invalid here *)
      Output = CMD.Other:Old AND CMD.WaterPipeFull:New;

ENDDEF (*BasePicture*);
