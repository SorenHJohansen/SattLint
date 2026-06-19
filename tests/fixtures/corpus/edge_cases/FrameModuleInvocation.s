"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: FrameModuleInv"
(* Edge case: FRAME_MODULE invocation syntax.
   Grammar rule: frame_module. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   FrameChild = MODULEDEFINITION DateCode_ 1
   LOCALVARIABLES
      Value: integer  := 0;
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ENDDEF (*FrameChild*);

SUBMODULES
   FrameInst Invocation
      ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
       ) : FRAME_MODULE FrameChild;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

ENDDEF (*BasePicture*);
