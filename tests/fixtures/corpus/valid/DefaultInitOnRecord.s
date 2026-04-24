"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: DefaultInitOnRecord"
(* Covers the Default init keyword on a record-typed variable.
   When a variable has a complex record type, its initial value can be set
   with ":= Default" meaning use the type's field-level default values.
   Expected: strict syntax-check passes. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   MeasurementType = RECORD DateCode_ 1
      Value: real  := 0.0;
      Valid: boolean  := False;
      Quality: integer  := 0;
   ENDDEF
    (*MeasurementType*);

LOCALVARIABLES
   Reading: MeasurementType  := Default;
   Backup: MeasurementType  := Default;
   Output: real  := 0.0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      IF Reading.Valid THEN
         Output = Reading.Value;
         Backup.Value = Reading.Value;
         Backup.Valid = True;
      ENDIF;

ENDDEF (*BasePicture*);
