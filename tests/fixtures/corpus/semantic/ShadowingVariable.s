"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: ShadowingVariable"
(* SEMANTIC: A submodule's local variable has the same name (case-insensitive)
   as a local variable in the parent BasePicture.
   The child type 'ChildType' declares a local variable 'Setting' and the
   parent declares 'setting' — these shadow each other.
   Expected finding: semantic.shadowing.
   Expected: strict syntax-check passes; shadowing analyzer reports SHADOWING. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   ChildType = MODULEDEFINITION DateCode_ 1
   LOCALVARIABLES
      Setting: integer  := 0;
      Mirror: integer  := 0;

   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Mirror = Setting;

   ENDDEF (*ChildType*);

LOCALVARIABLES
   setting: integer  := 42;

SUBMODULES
   Child Invocation
      ( 0.1 , 0.1 , 0.0 , 0.4 , 0.4
       ) : ChildType;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      setting = setting + 1;

ENDDEF (*BasePicture*);
