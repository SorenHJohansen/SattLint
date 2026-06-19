"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: MmsTag"
(* SEMANTIC: Duplicate MMS tags, datatype mismatch, naming drift, dead tags.
   Expected: mms-duplicate-tag, mms-datatype-mismatch, mms-naming-drift,
   mms-dead-tag. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   TagVal: integer  := 0;
   OtherVal: real  := 0.0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Mms COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      MMS_WRITE "MV_1001" TagVal;
      MMS_WRITE "MV_1001" TagVal;
      MMS_WRITE "MV_1002" OtherVal;
      MMS_WRITE "AI_2001" TagVal;
      TagVal = TagVal + 1;

ENDDEF (*BasePicture*);
