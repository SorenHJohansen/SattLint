"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: UnusedDatatypeField"
(* SEMANTIC: A RECORD type is declared with a field that is never accessed
   in any equation, sequence code, parameter mapping, or graphic binding.
   The record variable itself IS used (its UsedField is read and written),
   but UnusedField is never touched anywhere.
   Expected finding: semantic.unused-datatype-field for 'UnusedField' of 'SensorType'.
   Expected: strict syntax-check passes; variables analyzer reports UNUSED_DATATYPE_FIELD. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   SensorType = RECORD DateCode_ 1
      UsedField: real  := 0.0;
      UnusedField: real  := 0.0;
   ENDDEF
    (*SensorType*);

LOCALVARIABLES
   Sensor: SensorType ;
   Output: real  := 0.0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Sensor.UsedField = Sensor.UsedField + 1.0;
      Output = Sensor.UsedField;

ENDDEF (*BasePicture*);
