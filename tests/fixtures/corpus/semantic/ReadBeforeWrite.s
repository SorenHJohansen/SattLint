"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: ReadBeforeWrite"
(* SEMANTIC: A variable is read in an expression before it has been assigned
   in the current scan cycle. The variable has no init value (:= ...), so
   its first read is before any write in the equation block.
   Expected finding: semantic.read-before-write for 'Uninitialized'.
   Expected: strict syntax-check passes; dataflow analyzer reports finding. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   Uninitialized: boolean;
   Output: boolean  := False;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Output = Uninitialized;

ENDDEF (*BasePicture*);
