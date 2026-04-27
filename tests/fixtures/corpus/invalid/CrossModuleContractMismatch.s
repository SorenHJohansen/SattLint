"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: ContractMismatch"
(* SEMANTIC: A parameter mapping passes a variable whose datatype is incompatible
   with the declared parameter datatype.
   ChildType expects a boolean 'EnableFlag' parameter, but the caller maps an
   integer variable 'CounterValue' to it — integer is not compatible with boolean.
   Expected finding: semantic.cross-module-contract-mismatch.
   Expected: strict syntax-check passes; variables analyzer reports CONTRACT_MISMATCH. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   ChildType = MODULEDEFINITION DateCode_ 1
   MODULEPARAMETERS
      EnableFlag: boolean  := False;
   LOCALVARIABLES
      Active: boolean  := False;

   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Active = EnableFlag;

   ENDDEF (*ChildType*);

LOCALVARIABLES
   CounterValue: integer  := 0;

SUBMODULES
   Child Invocation
      ( 0.1 , 0.1 , 0.0 , 0.4 , 0.4
       ) : ChildType (
      EnableFlag => CounterValue);

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      CounterValue = CounterValue + 1;

ENDDEF (*BasePicture*);
