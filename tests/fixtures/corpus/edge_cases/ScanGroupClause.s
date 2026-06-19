"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: ScanGroupClause"
(* Edge case: SCAN_GROUP clause on an EQUATIONBLOCK.
   Grammar rule: scan_group. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   InputA: integer  := 0;
   OutputB: integer  := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Fast COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 SCAN_GROUP FastScan :
      OutputB = InputA + 1;

ENDDEF (*BasePicture*);
