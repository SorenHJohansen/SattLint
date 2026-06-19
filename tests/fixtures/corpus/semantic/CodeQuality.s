"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: CodeQuality"
(* SEMANTIC: Commented code, always-true/always-false conditions,
   unreachable branch, self-compare, unsafe default true.
   Expected: commented-code, condition-always-true, condition-always-false,
   unreachable-branch, self-compare-condition, unsafe-default-true. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   AlwaysOn: boolean  := True;
   OffFlag: boolean  := False;
   Input: integer  := 0;
   Output: integer  := 0;
   SelfCheck: integer  := 0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      IF True THEN
         Output = Input;
      ENDIF;
      IF False THEN
         Output = 0;
      ENDIF;
      IF SelfCheck = SelfCheck THEN
         Output = 1;
      ENDIF;
      (* IF Disabled THEN Output = 0; ENDIF; *)
      Output = Output + 1;

ENDDEF (*BasePicture*);
