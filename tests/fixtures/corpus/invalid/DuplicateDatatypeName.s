"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: DuplicateDatatypeName"
(* INVALID: Two RECORD types defined with the same name in TYPEDEFINITIONS.
   Scope uniqueness validation rejects duplicate datatype names (case-insensitive).
   SensorType appears twice; this is rejected at the validation stage.
   Expected: strict syntax-check fails at stage "validation". *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   SensorType = RECORD DateCode_ 1
      RawValue: real  := 0.0;
      Valid: boolean  := False;
   ENDDEF
    (*SensorType*);
   SensorType = RECORD DateCode_ 2
      RawValue: real  := 0.0;
      Valid: boolean  := False;
      Tag: string  := "";
   ENDDEF
    (*SensorType*);

LOCALVARIABLES
   Sensor: SensorType ;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

ENDDEF (*BasePicture*);
