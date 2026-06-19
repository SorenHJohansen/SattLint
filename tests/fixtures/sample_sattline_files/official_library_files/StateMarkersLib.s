"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: StateMarkersLib"
(* Official library counterpart to StateMarkersLib.x.
   Defines state marker enumeration types. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   BatchPhase = RECORD DateCode_ 1
      Idle: boolean := True;
      Running: boolean := False;
      Complete: boolean := False;
      Aborted: boolean := False;
   ENDDEF
    (*BatchPhase*);

   ValveState = RECORD DateCode_ 2
      Open: boolean := False;
      Closed: boolean := True;
      Fault: boolean := False;
   ENDDEF
    (*ValveState*);

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

ENDDEF (*BasePicture*);
