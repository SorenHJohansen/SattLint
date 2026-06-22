"Syntax version 2.23, date: 2026-04-23-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-04-23-12:00:00.000, name: FaultHandling"
(* SEMANTIC: Fault handling coverage for the wave-2 analyzer.
   - HighFault is raised without a recovery write.
   - HighFault is not consumed by reachable handling logic.
   Expected findings include the fault-handling semantic rules. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   HighFault: boolean  := False;
   HandledFault: boolean  := False;
   Status: boolean  := False;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      HighFault = True;
      HandledFault = True;
      IF HandledFault THEN
         Status = True;
      ENDIF;
      HandledFault = False;
      IF Status THEN
         Status = False;
      ENDIF;

ENDDEF (*BasePicture*);
