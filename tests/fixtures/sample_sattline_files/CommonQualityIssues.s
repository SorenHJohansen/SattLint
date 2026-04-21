"Syntax version 2.23, date: 2026-04-20-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-20-12:00:00.000, name: CommonQualityIssues"

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
   QualityRecord = RECORD DateCode_ 1
      UsedField: integer  := 10;
      UnusedField: integer  := 20;
   ENDDEF
    (*QualityRecord*);

LOCALVARIABLES
   ReadOnlyValue: integer  := 10;
   UnusedValue: integer  := 20;
   NeverReadValue: integer  := 0;
   SinkValue: integer  := 0;
   RecordValue: QualityRecord ;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      SinkValue = ReadOnlyValue + RecordValue.UsedField;
      NeverReadValue = SinkValue + ReadOnlyValue;

ENDDEF (*BasePicture*);