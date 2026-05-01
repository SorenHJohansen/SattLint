"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    GetRemoteFile = MODULEDEFINITION DateCode_ 2
    LOCALVARIABLES
        ExecuteLocal: boolean State := False;
    ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    ENDDEF (*GetRemoteFile*);

    zRestoreStringList = MODULEDEFINITION DateCode_ 3
    LOCALVARIABLES
        ExecuteState: boolean State := False;
    ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    ENDDEF (*zRestoreStringList*);

    EventLogger2 = MODULEDEFINITION DateCode_ 4
    LOCALVARIABLES
        CurrentEventFinished: boolean State := False;
    ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    ENDDEF (*EventLogger2*);

    MMSWriteVar = MODULEDEFINITION DateCode_ 5
    LOCALVARIABLES
        Rdy: boolean State := False;
    ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    ENDDEF (*MMSWriteVar*);

    ReportGeneralTable = MODULEDEFINITION DateCode_ 6
    LOCALVARIABLES
        Ready: boolean State := False;
    ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    ENDDEF (*ReportGeneralTable*);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
