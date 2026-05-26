"Syntax version 2.23, date: 2026-05-21-13:47:13.935 N"
"Original file date: ---"
"Program date: 2026-05-21-13:47:13.935, name: TestGraphicsParse"
(* Denne programenhed er oprettet 2026-05-21 13:36 af sqhj. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 218346700
LOCALVARIABLES
   areacolorvar, textcolorvar: integer ;
   minlimitvar, maxlimitvar, barvariable: real ;
   resetvar: integer ;
   helplinevar: boolean ;
   unitvar: string ;
   minscalevar, maxscalevar: real ;
   LineColorVar: integer ;
   EnableVar, ZoomableVar: boolean ;
   DefaultPathVar: string ;
   IndexVar: integer ;
   index1pathvar, index2parthvar: string ;
   enablejourvar: boolean ;
   maxvar, minvar: real ;
   controlscalevar: boolean ;


ModuleDef
ClippingBounds = ( -10.0 , -10.0 ) ( 10.0 , 10.0 )
ZoomLimits = 0.0 0.01
GraphObjects :
   CompositeObject
   CompositeObject
   CompositeObject
   CompositeObject
   CompositeObject

ENDDEF (*BasePicture*);
