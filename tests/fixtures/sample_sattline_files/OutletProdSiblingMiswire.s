"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: OutletProdMiswire"

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
   OutletProdState = RECORD DateCode_ 1
      Std: integer  := 0;
      Aux: integer  := 0;
   ENDDEF
    (*OutletProdState*);

   OutletProdPair = RECORD DateCode_ 1
      OutletProd_Def: OutletProdState ;
      OutletProd_X_Def: OutletProdState ;
   ENDDEF
    (*OutletProdPair*);

LOCALVARIABLES
   TransferInit: integer  := 1;
   SinkValue: integer  := 0;
   OutletConfig: OutletProdPair ;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      SinkValue = OutletConfig.OutletProd_Def.Std;
      OutletConfig.OutletProd_X_Def.Std = TransferInit;

ENDDEF (*BasePicture*);
