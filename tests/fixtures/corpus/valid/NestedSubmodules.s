"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: NestedSubmodules"
(* Covers three levels of module nesting:
   Level 0 — BasePicture (outer program)
   Level 1 — MiddleType: a named module type defined in BasePicture's TYPEDEFINITIONS,
             instantiated as a submodule; it contains its own inline sub-submodule.
   Level 2 — InnerModule: an inline MODULEDEFINITION declared directly inside
             MiddleType's SUBMODULES using invocation_new_module syntax.
   Expected: strict syntax-check passes. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   MiddleType = MODULEDEFINITION DateCode_ 1
   LOCALVARIABLES
      MiddleVal: integer  := 0;

   SUBMODULES
      Inner Invocation
         ( 0.05 , 0.05 , 0.0 , 0.4 , 0.4
          ) : MODULEDEFINITION DateCode_ 1
      LOCALVARIABLES
         InnerVal: integer  := 0;
         Tick: boolean  := False;

      ModuleDef
      ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
      ModuleCode
      EQUATIONBLOCK InnerEq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
         InnerVal = InnerVal + 1;
         Tick = NOT Tick;

      ENDDEF (*Inner*);

   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ModuleCode
   EQUATIONBLOCK MiddleEq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      MiddleVal = MiddleVal + 1;

   ENDDEF (*MiddleType*);

SUBMODULES
   Middle Invocation
      ( 0.1 , 0.1 , 0.0 , 0.8 , 0.8
       ) : MiddleType;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

ENDDEF (*BasePicture*);
