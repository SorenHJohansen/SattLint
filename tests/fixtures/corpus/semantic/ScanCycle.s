"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: ScanCycle"
(* SEMANTIC: Stale read, implicit new-value dependency, temporal misuse.
   Expected: scan-cycle-stale-read, scan-cycle-implicit-new,
   scan-cycle-temporal-misuse. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   Sensor: integer  := 0;
   Filtered: integer  := 0;
   Accum: integer  := 0;
   PrevAccum: integer  := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Cyclic COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Filtered = Sensor * 2;
      Accum = Accum + Filtered;
      Accum = Accum + 1;
      PrevAccum = Accum;

ENDDEF (*BasePicture*);
