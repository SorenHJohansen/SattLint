"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: ResourceLifecycle"
(* SEMANTIC: Resource leak, reacquire before release, release without acquire.
   Expected: resource-leak, resource-reacquire-before-release,
   resource-release-without-acquire. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   ResourceId: integer  := 0;
   Acquired: boolean  := False;
   Done: boolean  := False;
   Handle: integer  := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Res COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Acquired = True;
      Handle = ResourceId;
      Done = True;
      Acquired = True;
      Done = False;
      Handle = 0;
      Acquired = False;
      Handle = 0;
      Acquired = False;

ENDDEF (*BasePicture*);
