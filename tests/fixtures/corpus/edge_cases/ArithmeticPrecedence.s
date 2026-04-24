"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: ArithmeticPrecedence"
(* Covers arithmetic operator precedence and parenthesized sub-expressions.
   Verifies the parser correctly models:
   - Multiplication before addition (A + B * C means A + (B * C))
   - Parentheses override default precedence ((A + B) * C)
   - Unary minus on a variable (-A)
   - Unary minus on the right operand (A * -B)
   - Division and combined expressions
   Expected: strict syntax-check passes. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   A: real  := 2.0;
   B: real  := 3.0;
   C: real  := 4.0;
   R1: real  := 0.0;
   R2: real  := 0.0;
   R3: real  := 0.0;
   R4: real  := 0.0;
   R5: real  := 0.0;
   R6: real  := 0.0;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      R1 = A + B * C;
      R2 = (A + B) * C;
      R3 = -A + B;
      R4 = A * -B;
      R5 = A / B + C * -A;
      R6 = A + B * -C + A / (B + C);

ENDDEF (*BasePicture*);
