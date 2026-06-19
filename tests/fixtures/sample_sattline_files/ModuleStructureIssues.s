"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: ModuleStructureIssues"
(* Covers HIDDEN_GLOBAL_COUPLING, HIGH_FAN_IN_OUT, UNKNOWN_PARAMETER_TARGET, NAME_COLLISION.
   Expected: strict syntax-check passes. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   InnerType = MODULEDEFINITION DateCode_ 1
   LOCALVARIABLES
      Internal: integer  := 0;
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ModuleCode
   EQUATIONBLOCK Eq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Internal = Internal + 1;
   ENDDEF (*InnerType*);

   CleanType = MODULEDEFINITION DateCode_ 1
   MODULEPARAMETERS
      InputVal: integer;
   LOCALVARIABLES
      Internal: integer  := 0;
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ModuleCode
   EQUATIONBLOCK Eq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Internal = InputVal;
   ENDDEF (*CleanType*);

LOCALVARIABLES
   GlobalRef: integer  := 0;
   HeavyRead: integer  := 0;
   HeavyWrite: integer  := 0;
   FanSrc: integer  := 0;
   CollisionName: integer  := 0;
   CleanGlobal: integer  := 0;

SUBMODULES
   InnerBad Invocation
      ( 0.0 , 0.0 , 0.0 , 0.4 , 0.4
       ) : InnerType;
   CleanSub Invocation
      ( 0.5 , 0.0 , 0.0 , 0.4 , 0.4
       ) : CleanType (
      InputVal => CleanGlobal);
   UnknownParam Invocation
      ( 0.0 , 0.5 , 0.0 , 0.4 , 0.4
       ) : CleanType (
      InputVal => FanSrc,
      BogusParam => HeavyRead);

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      HeavyRead = HeavyRead + 1;
      HeavyWrite = HeavyWrite + 1;
      FanSrc = HeavyRead + HeavyWrite;
      GlobalRef = FanSrc;
      CollisionName = GlobalRef;
      CleanGlobal = CleanGlobal + 1;

ENDDEF (*BasePicture*);
