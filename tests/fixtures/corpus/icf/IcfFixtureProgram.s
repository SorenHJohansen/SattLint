"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: IcfFixtureProgram"
(* Minimal SattLine program designed as a target for corpus ICF validation
   fixtures. The submodule structure mirrors the journal-oriented path
   patterns used in real IcfFixtureProgram.icf files:

     IcfFixtureProgram:BatchUnit.Operation.T.OPR_ID    (valid)
     IcfFixtureProgram:BatchUnit.Operation.S.RESULT_CODE (valid)
     IcfFixtureProgram:BatchUnit.Operation.J            (valid — single var)
     IcfFixtureProgram:BatchUnit.Param.Temperature      (valid — plain param)
     IcfFixtureProgram:BatchUnit.Param.MissingVar       (invalid path)
     WrongProgram:BatchUnit.Operation.T.OPR_ID          (program mismatch)

   Expected: strict syntax-check passes.
   ICF validation: 3 valid, 1 unresolved-path, 1 program-mismatch. *)

IcfFixtureProgram Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   JournalTType = RECORD DateCode_ 1
      OPR_ID: string  := "";
      CR_ID: string  := "";
      CYCLE: integer  := 0;
      SEQ: integer  := 0;
      TRY: integer  := 0;
      TIME: time  := "2000-01-01-00:00:00.000";
   ENDDEF
    (*JournalTType*);
   JournalSType = RECORD DateCode_ 1
      RESULT_CODE: integer  := 0;
      RESULT_TEXT: string  := "";
   ENDDEF
    (*JournalSType*);

TYPEDEFINITIONS
   OperationType = MODULEDEFINITION DateCode_ 1
   LOCALVARIABLES
      T: JournalTType ;
      S: JournalSType ;
      J: integer  := 0;

   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ModuleCode
   EQUATIONBLOCK Eq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      J = J + 1;

   ENDDEF (*OperationType*);
   ParamBlockType = MODULEDEFINITION DateCode_ 1
   LOCALVARIABLES
      Temperature: real  := 0.0;
      Pressure: real  := 0.0;
      Valid: boolean  := False;

   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ModuleCode
   EQUATIONBLOCK Eq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Valid = Temperature > 0.0;

   ENDDEF (*ParamBlockType*);
   BatchUnitType = MODULEDEFINITION DateCode_ 1
   SUBMODULES
      Operation Invocation
         ( 0.0 , 0.0 , 0.0 , 0.5 , 0.5
          ) : OperationType;
      Param Invocation
         ( 0.5 , 0.0 , 0.0 , 0.5 , 0.5
          ) : ParamBlockType;

   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ENDDEF (*BatchUnitType*);

SUBMODULES
   BatchUnit Invocation
      ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
       ) : BatchUnitType;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

ENDDEF (*IcfFixtureProgram*);
