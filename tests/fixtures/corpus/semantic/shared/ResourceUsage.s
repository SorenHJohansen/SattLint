"Syntax version 2.23, date: 2026-06-22-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-22-12:00:00.000, name: ResourceUsage"
(* Direct analyzer fixture for resource_usage.* findings. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   FileRef: tObject;
   FirstPath: string  := "";
   SecondPath: string  := "";
   AsyncOp: AsyncOperation;
   Status: integer  := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
   OpenReadFile(FileRef, FirstPath, AsyncOp, Status);
   OpenWriteFile(FileRef, SecondPath, AsyncOp, Status);

ENDDEF (*BasePicture*);
