"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: RecordTypeAccess"
(* Exercises RECORD type definitions and field access including:
   - Single-level record field read and write
   - Nested record (record within a record)
   - Record variable with Default init
   - Mixed Const and State modifiers on record fields
   Expected: strict syntax-check passes. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   PositionType = RECORD DateCode_ 1
      X: real  := 0.0;
      Y: real  := 0.0;
      Valid: boolean State  := False;
   ENDDEF
    (*PositionType*);

   SensorType = RECORD DateCode_ 2
      RawValue: real  := 0.0;
      Calibrated: real  := 0.0;
      Position: PositionType ;
      Tag: string Const  := "Sensor";
   ENDDEF
    (*SensorType*);

LOCALVARIABLES
   Sensor: SensorType ;
   Scale: real  := 1.0;
   Output: real  := 0.0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Sensor.Calibrated = Sensor.RawValue * Scale;
      Sensor.Position.X = Sensor.Calibrated;
      Sensor.Position.Y = 0.0;
      Sensor.Position.Valid = Sensor.Calibrated > 0.0;
      Output = Sensor.Calibrated;

ENDDEF (*BasePicture*);
