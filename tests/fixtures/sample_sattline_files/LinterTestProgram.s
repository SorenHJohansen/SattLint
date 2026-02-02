"Syntax version 2.23, date: 2026-02-02-11:05:04.749 N"
"Original file date: ---"
"Program date: 2026-02-02-11:05:04.749, name: LinterTestProgram"
(* Denne programenhed er oprettet 2026-02-02 10:16 af sqhj. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0 
    ) : MODULEDEFINITION DateCode_ 143649108
TYPEDEFINITIONS
   ShadowType = RECORD DateCode_ 135614124
      Value "shadows variable Value": integer  := 1;
      rReadOnly: integer  := 10;
      rWriteOnly: integer  := 20;
      rUnused: integer  := 30;
   ENDDEF
    (*ShadowType*);
   
TYPEDEFINITIONS
   Linter_Test = MODULEDEFINITION DateCode_ 142590744
   MODULEPARAMETERS
      pReadOnly: integer  := 10;
      pWriteOnly: integer  := 20;
      pUnused: integer  := 30;
      pTransReadOnly: integer  := 10;
      pTransWriteOnly: integer  := 20;
      pTransUnused: integer  := 30;
   LOCALVARIABLES
      Value "shadows parameter Value", 'Value' "Quoted identifier shadow": 
      integer  := 1;
      Shadow "Shadow record": ShadowType ;
      vReadOnly: integer  := 10;
      vWriteOnly: integer  := 20;
      vUnused: integer  := 30;
      vTekst: string  := "Test";
      Enable, vIf, vTernary, vFunction: boolean ;
      vProcedure, vAssignment, vExpression, si: integer ;
   SUBMODULES
      FM1 Invocation
         ( 0.38 , 0.52 , 0.0 , 0.28 , 0.28 
          ) : MODULEDEFINITION DateCode_ 136356372 ( Frame_Module ) 
      SUBMODULES
         SM1 Invocation
            ( -0.4 , 0.4 , 0.0 , 0.42 , 0.42 
             ) : MODULEDEFINITION DateCode_ 143440668
         MODULEPARAMETERS
            pTransReadOnly, pTransWriteOnly, pTransUnused: integer ;
            pGlobalUsed, pGlobalUnused: boolean ;
         
         
         ModuleDef
         ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
         GraphObjects :
            RectangleObject ( -1.0 , 1.0 ) ( 1.0 , -1.0 ) 
               OutlineColour : Colour0 = 5 
         
         ModuleCode
         EQUATIONBLOCK Equa1 COORD -0.74, -0.12 OBJSIZE 1.08, 0.88 :
            pTransWriteOnly = IF pTransReadOnly == 1 THEN 2 ELSIF pGlobalUsed 
               THEN 3 ELSE 4 ENDIF;
         
         ENDDEF (*SM1*) (
         pTransReadOnly => pTransReadOnly, 
         pTransWriteOnly => pTransWriteOnly, 
         pTransUnused => pTransUnused, 
         pGlobalUsed => GLOBAL Used, 
         pGlobalUnused => GLOBAL Unused);
         
      
      ModuleDef
      ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
      GraphObjects :
         RectangleObject ( -1.0 , 1.0 ) ( 1.0 , -1.0 ) 
            OutlineColour : Colour0 = 5 
      
      ENDDEF (*FM1*);
      
   
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   Zoomable
   GraphObjects :
      RectangleObject ( -1.0 , 1.0 ) ( 1.0 , -1.0 ) 
         OutlineColour : Colour0 = 5 
      TextObject ( 0.12 , -0.04 ) ( 0.12 , -0.2 ) 
         "vTekst" VarName Width_ = 5  ValueFraction = 2  LeftAligned 
         Enable_ = True : InVar_ "Enable" 
         OutlineColour : Colour0 = -3 
   
   ModuleCode
   EQUATIONBLOCK Main COORD -0.9, 0.06 OBJSIZE 0.82, 0.72 :
      Value = Value + 1;
      Shadow.Value = Value + 1;
      'Value' = Value + 1;
      vWriteOnly = vReadOnly;
      IF vIf THEN
         
      ENDIF;
      vTernary = vTernary AND 1 <> 2;
      CopyVariable(vProcedure, vProcedure, si);
      vFunction = Equal(vFunction, vFunction);
      vExpression = 123;
   
   ENDDEF (*Linter_Test*);
   
LOCALVARIABLES
   Used, Unused: boolean ;
SUBMODULES
   VariableTest Invocation
      ( 0.16 , 0.54 , 0.0 , 0.06 , 0.06 
       ) : Linter_Test;
   

ModuleDef
ClippingBounds = ( -10.0 , -10.0 ) ( 10.0 , 10.0 )
ZoomLimits = 0.0 0.01

ENDDEF (*BasePicture*);

