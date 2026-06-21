"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: MmsTag"
(* SEMANTIC: Duplicate MMS tags, datatype mismatch, naming drift, dead tags.
   Expected: mms-duplicate-tag, mms-datatype-mismatch, mms-naming-drift,
   mms-dead-tag. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   MMSWriteVar = MODULEDEFINITION DateCode_ 1
   MODULEPARAMETERS
      LocalVariable: integer := 0;
      RemoteVarName: string := "";
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ENDDEF (*MMSWriteVar*);

LOCALVARIABLES
   TagVal: integer  := 0;
   OtherVal: real  := 0.0;

SUBMODULES
   MMS1 Invocation
      ( 0.0 , 0.0 , 0.0 , 0.4 , 0.4
       ) : MMSWriteVar (LocalVariable => TagVal, RemoteVarName => "MV_1001");
   MMS2 Invocation
      ( 0.5 , 0.0 , 0.0 , 0.4 , 0.4
       ) : MMSWriteVar (LocalVariable => OtherVal, RemoteVarName => "MV_1001");
   MMS3 Invocation
      ( 0.0 , 0.5 , 0.0 , 0.4 , 0.4
       ) : MMSWriteVar (LocalVariable => TagVal, RemoteVarName => "MV-1001");
   MMS4 Invocation
      ( 0.5 , 0.5 , 0.0 , 0.4 , 0.4
       ) : MMSWriteVar (LocalVariable => OtherVal, RemoteVarName => "AI_2001");

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Mms COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      TagVal = TagVal + 1;

ENDDEF (*BasePicture*);
