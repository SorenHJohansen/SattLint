"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: AlarmIntegrity"
(* SEMANTIC: Duplicate alarm tags, duplicate conditions, conflicting priorities,
   never-cleared alarms.
   Expected: duplicate-alarm-tag, duplicate-alarm-condition,
   conflicting-alarm-priority, never-cleared-alarm. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   TempHigh: boolean  := False;
   PressHigh: boolean  := False;
   LevelLow: boolean  := False;
   Ack: boolean  := False;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Alarms COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      ALARM "TEMP_HIGH" PRIO 1 IF TempHigh;
      ALARM "TEMP_HIGH" PRIO 1 IF TempHigh;
      ALARM "PRESS_HIGH" PRIO 1 IF PressHigh;
      ALARM "PRESS_HIGH" PRIO 2 IF PressHigh;
      ALARM "LEVEL_LOW" PRIO 3 IF LevelLow;

ENDDEF (*BasePicture*);
