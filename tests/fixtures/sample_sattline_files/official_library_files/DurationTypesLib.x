"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    Curve4Par = RECORD DateCode_ 2
        TimeRange: duration := Duration_Value "1h";
        Label: string := "Curve";
    ENDDEF (*Curve4Par*);

    JouReadTagType = RECORD DateCode_ 3
        StartTime: time := Time_Value "1984-01-01-00:00:00.000";
        EndTime: time := Time_Value "1984-01-01-01:00:00.000";
    ENDDEF (*JouReadTagType*);

    EventDurationSample = RECORD DateCode_ 4
        DelayWindow: duration := Duration_Value "590ms";
        Enabled: boolean := True;
    ENDDEF (*EventDurationSample*);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
