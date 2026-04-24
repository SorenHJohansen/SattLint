"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: DeadOverwrite"
(* SEMANTIC: A variable is written twice in the same equation block without
   any intervening read. The first write is immediately overwritten, making
   that assignment dead — its result can never be observed.
   Expected finding: semantic.dead-overwrite for 'Flag'.
   Expected: strict syntax-check passes; dataflow analyzer reports finding. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   Flag: boolean  := False;
   Condition: boolean  := True;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Flag = True;
      Flag = Condition;

ENDDEF (*BasePicture*);
