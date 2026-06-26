"Syntax version 2.23, date: 2026-06-25-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-25-12:00:00.000, name: SpecOpSig"
(* Covers OPMESSAGE_USE_SIGNATURE. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   UseSig: boolean  := True;

SUBMODULES
   Prompt Invocation
      ( 0.0 , 0.0 , 0.0 , 0.4 , 0.4
       ) : OPMessage (
   UseSignature => UseSig);

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

ENDDEF (*BasePicture*);
