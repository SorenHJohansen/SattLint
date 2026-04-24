"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: OldNewOnStateField"
(* Covers valid :Old and :New temporal access.
   :Old and :New are only valid on variables or record fields declared as State.
   Accessing a non-State variable with :Old must be rejected by validation.
   This fixture tests the valid case: a top-level State boolean and a
   State field inside a record.
   Expected: strict syntax-check passes. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   ValveType = RECORD DateCode_ 1
      IsOpen: boolean State  := False;
      Position: real  := 0.0;
   ENDDEF
    (*ValveType*);

LOCALVARIABLES
   RunFlag: boolean State  := False;
   Valve: ValveType ;
   OpenedThisScan: boolean  := False;
   ClosedThisScan: boolean  := False;
   ValveJustOpened: boolean  := False;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      (* Rising edge on top-level State variable *)
      OpenedThisScan = RunFlag:New AND NOT RunFlag:Old;

      (* Falling edge on top-level State variable *)
      ClosedThisScan = NOT RunFlag:New AND RunFlag:Old;

      (* :Old on a State field inside a record *)
      ValveJustOpened = Valve.IsOpen:New AND NOT Valve.IsOpen:Old;

ENDDEF (*BasePicture*);
