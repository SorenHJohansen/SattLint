"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: ControlFlow"
(* Covers all imperative control-flow constructs:
   - IF / THEN / ENDIF (no else)
   - IF / THEN / ELSE / ENDIF
   - IF / THEN / ELSIF / THEN / ELSE / ENDIF (multi-branch)
   - Ternary IF expression: IF <cond> THEN <val> ELSE <val> ENDIF
   - Nested IF statements
   - Complex boolean expressions (AND, OR, NOT, comparison)
   Expected: strict syntax-check passes. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   A, B, C: integer  := 0;
   X, Y: real  := 0.0;
   Flag1, Flag2, Flag3: boolean  := False;
   Output: integer  := 0;
   Result: real  := 0.0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      (* IF with no ELSE *)
      IF Flag1 THEN
         A = 1;
      ENDIF;

      (* IF / THEN / ELSE *)
      IF Flag2 THEN
         B = 10;
      ELSE
         B = 20;
      ENDIF;

      (* Multi-branch ELSIF *)
      IF A == 0 THEN
         Output = 0;
      ELSIF A == 1 THEN
         Output = 1;
      ELSIF A == 2 THEN
         Output = 2;
      ELSE
         Output = -1;
      ENDIF;

      (* Ternary IF expression (lowest precedence) *)
      C = IF Flag3 THEN A ELSE B ENDIF;

      (* Ternary in arithmetic: ELSE branch is an addition *)
      Result = IF X > 0.0 THEN X ELSE X + Y ENDIF;

      (* Nested IF *)
      IF Flag1 AND Flag2 THEN
         IF A > B THEN
            Output = A;
         ELSE
            Output = B;
         ENDIF;
      ENDIF;

      (* Complex boolean expression *)
      Flag3 = (A > 0 AND B < 100) OR NOT Flag1 AND Flag2 OR C <> 0;

ENDDEF (*BasePicture*);
