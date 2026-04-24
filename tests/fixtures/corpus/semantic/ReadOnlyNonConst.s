"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: ReadOnlyNonConst"
(* SEMANTIC: A local variable is only ever read; it is never written in any
   equation or sequence, has an init value that provides its only value.
   It is not declared Const, which it should be.
   Expected finding: semantic.read-only-non-const for 'FixedThreshold'.
   Expected: strict syntax-check passes; analyzer reports READ_ONLY_NON_CONST. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   FixedThreshold: integer  := 50;
   Input: integer  := 0;
   Output: boolean  := False;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Output = Input > FixedThreshold;

ENDDEF (*BasePicture*);
