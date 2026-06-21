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

TYPEDEFINITIONS
   MyAlarm = MODULEDEFINITION DateCode_ 1
   MODULEPARAMETERS
      Tag: string := "";
      Priority: integer := 0;
      Condition: boolean := False;
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ENDDEF (*MyAlarm*);

LOCALVARIABLES
   TempHigh: boolean  := False;
   PressHigh: boolean  := False;
   LevelLow: boolean  := False;
   Ack: boolean  := False;

SUBMODULES
   Alarm1 Invocation
      ( 0.0 , 0.0 , 0.0 , 0.4 , 0.4
       ) : MyAlarm (Tag => "TEMP_HIGH", Priority => 1, Condition => TempHigh);
   Alarm2 Invocation
      ( 0.5 , 0.0 , 0.0 , 0.4 , 0.4
       ) : MyAlarm (Tag => "TEMP_HIGH", Priority => 1, Condition => TempHigh);
   Alarm3 Invocation
      ( 0.0 , 0.5 , 0.0 , 0.4 , 0.4
       ) : MyAlarm (Tag => "PRESS_HIGH", Priority => 1, Condition => PressHigh);
   Alarm4 Invocation
      ( 0.5 , 0.5 , 0.0 , 0.4 , 0.4
       ) : MyAlarm (Tag => "PRESS_HIGH", Priority => 2, Condition => PressHigh);
   Alarm5 Invocation
      ( 0.0 , 0.0 , 0.5 , 0.4 , 0.4
       ) : MyAlarm (Tag => "LEVEL_LOW", Priority => 3, Condition => LevelLow);

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Alarms COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      TempHigh = True;
      PressHigh = PressHigh OR Ack;

ENDDEF (*BasePicture*);
