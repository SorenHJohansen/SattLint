"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: ParallelHazard"
(* SEMANTIC: Parallel read-write hazard, same-cycle shared access, write race.
   Expected: parallel-read-write-hazard, same-cycle-shared-access,
   parallel-write-race. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   SharedType = MODULEDEFINITION DateCode_ 1
   LOCALVARIABLES
      SharedVal: integer  := 0;
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ModuleCode
   EQUATIONBLOCK Eq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      SharedVal = SharedVal + 1;
   ENDDEF (*SharedType*);

SUBMODULES
   A Invocation
      ( 0.0 , 0.0 , 0.0 , 0.4 , 0.4
       ) : SharedType;
   B Invocation
      ( 0.5 , 0.0 , 0.0 , 0.4 , 0.4
       ) : SharedType;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

ENDDEF (*BasePicture*);
