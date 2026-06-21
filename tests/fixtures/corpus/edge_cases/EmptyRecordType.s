"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: EmptyRecordType"
(* Edge case: RECORD type with zero fields.
   Grammar rule: RECORD empty field list. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   EmptyRec = RECORD DateCode_ 1
   ENDDEF
    (*EmptyRec*);

   MarkerRec = RECORD DateCode_ 1
      Marker: boolean  := True;
      Count: integer  := 0;
   ENDDEF
    (*MarkerRec*);

LOCALVARIABLES
   Marker: MarkerRec ;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

ENDDEF (*BasePicture*);
