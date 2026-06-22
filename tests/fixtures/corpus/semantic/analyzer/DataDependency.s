"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: DataDependency"
(* SEMANTIC: Data dependency path, initialization order violation,
   loop output that should be refactored.
   Expected: data-dependency-path, data-dependency-initialization-order,
   loop-output-refactor. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   A: integer  := 0;
   B: integer  := 0;
   C: integer  := 0;
   Acc: integer  := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Dep COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      C = A + B;
      A = B + 1;
      B = 10;
      Acc = Acc + 1;
      Acc = Acc + C;

ENDDEF (*BasePicture*);
