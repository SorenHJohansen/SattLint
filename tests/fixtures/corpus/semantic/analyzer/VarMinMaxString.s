"Syntax version 2.23, date: 2026-06-25-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-25-12:00:00.000, name: VarMinMaxString"
(* Covers MIN_MAX_MAPPING_MISMATCH and STRING_MAPPING_MISMATCH. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   MinMaxType = MODULEDEFINITION DateCode_ 1
   MODULEPARAMETERS
      MaxValue: integer;
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ENDDEF (*MinMaxType*);

   StringType = MODULEDEFINITION DateCode_ 1
   MODULEPARAMETERS
      TargetValue: identstring;
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ENDDEF (*StringType*);

LOCALVARIABLES
   MinValue: integer  := 0;
   MaxValue: integer  := 100;
   SourceValue: string  := "";

SUBMODULES
   MinMaxChild Invocation
      ( 0.0 , 0.0 , 0.0 , 0.3 , 0.3
       ) : MinMaxType (
      MaxValue => MinValue);
   StringChild Invocation
      ( 0.4 , 0.0 , 0.0 , 0.3 , 0.3
       ) : StringType (
      TargetValue => SourceValue);

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

ENDDEF (*BasePicture*);
