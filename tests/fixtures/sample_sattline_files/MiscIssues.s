"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: MiscIssues"
(* Covers MAGIC_NUMBER, SHADOWING, LAYOUT_OVERLAP, DATATYPE_DUPLICATION.
   MAGIC_NUMBER has no semantic.* mapping — assert on IssueKind directly.
   Expected: strict syntax-check passes. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   RecipeType = RECORD DateCode_ 1
      Value: integer  := 0;
      Name: string  := "";
   ENDDEF
    (*RecipeType*);

TYPEDEFINITIONS
   ChildType = MODULEDEFINITION DateCode_ 1
   LOCALVARIABLES
      Temp: integer  := 0;
      Shadowed: integer  := 0;
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ModuleCode
   EQUATIONBLOCK Eq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Temp = Shadowed;
   ENDDEF (*ChildType*);

LOCALVARIABLES
   Shadowed: integer  := 100;
   Count: integer  := 0;
   Result: integer  := 0;

SUBMODULES
   Child Invocation
      ( 0.0 , 0.0 , 0.0 , 0.4 , 0.4
       ) : ChildType;

   ChildOverlap Invocation
      ( 0.0 , 0.0 , 0.0 , 0.4 , 0.4
       ) : ChildType;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Count = Count + 42;
      Shadowed = Count + 1;
      Result = Shadowed * 15;

ENDDEF (*BasePicture*);
