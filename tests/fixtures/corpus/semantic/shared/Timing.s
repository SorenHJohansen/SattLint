"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: Timing"
(* Covers dataflow scan-cycle timing findings: scan-cycle-stale-read,
   scan-cycle-implicit-new, scan-cycle-temporal-misuse.
   Delegates to dataflow + scan_loop_resource_usage sub-analyzers. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1 (GroupConn=FastScan)

LOCALVARIABLES
   Raw: integer  := 0;
   Smoothed: integer State := 0;
   Accum: integer State := 0;
   PrevAccum: integer  := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Fast COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Smoothed = Raw * 2;
      Accum = Accum + Smoothed;
      PrevAccum = Accum:Old;

ENDDEF (*BasePicture*);
