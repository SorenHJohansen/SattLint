"Syntax version 2.23, date: 2026-06-25-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-25-12:00:00.000, name: VarStructCover"
(* Covers HIDDEN_GLOBAL_COUPLING, HIGH_FAN_IN_OUT, NAME_COLLISION,
   DATATYPE_DUPLICATION. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   WorkerType = MODULEDEFINITION DateCode_ 1
   MODULEPARAMETERS
      Shared: integer;
   LOCALVARIABLES
      Shared: integer  := 0;
      PhaseTimer: Timer ;
      PhaseTimerCopy: Timer ;
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ENDDEF (*WorkerType*);

   WriterType = MODULEDEFINITION DateCode_ 1
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ModuleCode
   EQUATIONBLOCK Eq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      SharedValue = 1;
   ENDDEF (*WriterType*);

   ReaderAType = MODULEDEFINITION DateCode_ 1
   LOCALVARIABLES
      Observed: integer  := 0;
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ModuleCode
   EQUATIONBLOCK Eq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Observed = SharedValue;
   ENDDEF (*ReaderAType*);

   ReaderBType = MODULEDEFINITION DateCode_ 1
   LOCALVARIABLES
      Observed: integer  := 0;
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ModuleCode
   EQUATIONBLOCK Eq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Observed = SharedValue;
   ENDDEF (*ReaderBType*);

   ReaderCType = MODULEDEFINITION DateCode_ 1
   LOCALVARIABLES
      Observed: integer  := 0;
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ModuleCode
   EQUATIONBLOCK Eq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Observed = SharedValue;
   ENDDEF (*ReaderCType*);

LOCALVARIABLES
   SharedValue: integer  := 0;

SUBMODULES
   Worker Invocation
      ( 0.0 , 0.0 , 0.0 , 0.2 , 0.2
       ) : WorkerType (
      Shared => SharedValue);
   Writer Invocation
      ( 0.3 , 0.0 , 0.0 , 0.2 , 0.2
       ) : WriterType;
   ReaderA Invocation
      ( 0.0 , 0.3 , 0.0 , 0.2 , 0.2
         ) : ReaderAType;
   ReaderB Invocation
      ( 0.3 , 0.3 , 0.0 , 0.2 , 0.2
         ) : ReaderBType;
   ReaderC Invocation
      ( 0.6 , 0.3 , 0.0 , 0.2 , 0.2
         ) : ReaderCType;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

ENDDEF (*BasePicture*);
