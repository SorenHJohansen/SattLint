"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: MultiTypedefBlocks"
(* Covers two separate TYPEDEFINITIONS blocks in one file.
   The grammar allows an optional first TYPEDEFINITIONS block containing only
   RECORD types, followed by an optional second TYPEDEFINITIONS block containing
   only MODULEDEFINITION types (base_module_body = datatype_typedefinitions?
   moduletype_definitions? module_body). Both can be present simultaneously.
   Expected: strict syntax-check passes. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   SensorData = RECORD DateCode_ 1
      Temperature: real  := 0.0;
      Pressure: real  := 0.0;
      Valid: boolean  := False;
   ENDDEF
    (*SensorData*);
   AlarmData = RECORD DateCode_ 1
      Active: boolean  := False;
      Count: integer  := 0;
   ENDDEF
    (*AlarmData*);

TYPEDEFINITIONS
   SensorDisplayType = MODULEDEFINITION DateCode_ 1
   MODULEPARAMETERS
      Data: SensorData ;
   LOCALVARIABLES
      Alarm: AlarmData ;

   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ModuleCode
   EQUATIONBLOCK Display COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      IF NOT Data.Valid THEN
         Alarm.Active = True;
         Alarm.Count = Alarm.Count + 1;
      ENDIF;

   ENDDEF (*SensorDisplayType*);

LOCALVARIABLES
   Sensor: SensorData  := Default;

SUBMODULES
   Display Invocation
      ( 0.1 , 0.1 , 0.0 , 0.8 , 0.8
       ) : SensorDisplayType (
      Data => Sensor);

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Sensor.Temperature = Sensor.Temperature + 0.1;
      Sensor.Valid = True;

ENDDEF (*BasePicture*);
