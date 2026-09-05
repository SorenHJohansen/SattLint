"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: EnableExpr"
(* Regression fixture: a module header enable clause with a compound boolean
   expression (Enable AND EnablePrivilege). The parser turns the
   enable_expression tail into a BoolOp, which the full analysis pipeline must
   traverse without raising. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   Enable: boolean := False;
   EnablePrivilege: boolean := False;

SUBMODULES
   Child Invocation
      ( 0.05 , 0.05 , 0.0 , 0.4 , 0.4 Enable_ = True : ( Enable AND EnablePrivilege )
       ) : MODULEDEFINITION DateCode_ 1
   LOCALVARIABLES
      Output: boolean := False;

   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

   ENDDEF (*Child*);

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

ENDDEF (*BasePicture*);
