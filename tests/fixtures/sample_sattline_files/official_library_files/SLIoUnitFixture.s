"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: SLIoUnitFixture"
(* Official library counterpart to SLIoUnitFixture.x.
   Defines I/O unit structure types. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   DigitalInput = RECORD DateCode_ 1
      Value: boolean := False;
      Tag: string := "";
   ENDDEF
    (*DigitalInput*);

   AnalogInput = RECORD DateCode_ 2
      Value: real := 0.0;
      ScaleMin: real := 0.0;
      ScaleMax: real := 100.0;
      Tag: string := "";
   ENDDEF
    (*AnalogInput*);

   DigitalOutput = RECORD DateCode_ 3
      Value: boolean := False;
      Tag: string := "";
   ENDDEF
    (*DigitalOutput*);

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

ENDDEF (*BasePicture*);
