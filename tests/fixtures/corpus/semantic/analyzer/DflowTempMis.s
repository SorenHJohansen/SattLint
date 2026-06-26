"Syntax version 2.23, date: 2026-06-25-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-25-12:00:00.000, name: DflowTempMis"
(* Covers SCAN_CYCLE_TEMPORAL_MISUSE. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   Flag: boolean State := False;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      MaxLim(1.0, 2.0, 0.1, Flag:Old);

ENDDEF (*BasePicture*);
