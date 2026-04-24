"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: DurationInParameterMapping"
(* Covers Duration_Value "..." used as the source value in a => parameter mapping.
   The grammar allows Duration_Value before the literal in a moduletype_par_transfer:
     variable_name "=>" GLOBAL_KW? DURATION_VALUE? (value | variable_name | time_value)
   This fixture uses Duration_Value literals to supply timeout constants to a
   timer module type's duration parameters.
   Expected: strict syntax-check passes. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   TimerType = MODULEDEFINITION DateCode_ 1
   MODULEPARAMETERS
      Timeout: duration  := "0";
      Delay: duration  := "0";
   LOCALVARIABLES
      Elapsed: duration  := "0";
      Expired: boolean  := False;

   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ModuleCode
   EQUATIONBLOCK TimerEq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Expired = Elapsed >= Timeout;

   ENDDEF (*TimerType*);

SUBMODULES
   FastTimer Invocation
      ( 0.1 , 0.1 , 0.0 , 0.4 , 0.4
       ) : TimerType (
      Timeout => Duration_Value "5m30s",
      Delay => Duration_Value "500ms");

   SlowTimer Invocation
      ( 0.6 , 0.1 , 0.0 , 0.4 , 0.4
       ) : TimerType (
      Timeout => Duration_Value "1h",
      Delay => Duration_Value "0");

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

ENDDEF (*BasePicture*);
