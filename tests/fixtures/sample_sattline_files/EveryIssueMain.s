"Syntax version 2.23, date: 2026-09-08-11:28:31.229 N"
"Original file date: ---"
"Program date: 2026-09-08-11:28:31.229, name: EveryIssueMain"
(* Denne programenhed er oprettet 2026-09-08 08:38 af sqhj. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 251150220
LOCALVARIABLES
   OpenCmd, CloseCmd: boolean  := False;
   PosValue: real  := 0.0;
   RawValue, MinValue: integer  := 0;
   MaxValue: integer  := 100;
   SourceValue: string  := "";
   HmiCmd: boolean  := False;
   DefaultPath: string Const := "+ToggleParWindow";
   PathOK: string  := "";
   si, si2, si3, si4: integer ;
   OprPathIndex: integer  := 0;
   setting: integer  := 42;
   Min_Output: integer  := 0;
   Max_Output: integer  := 10;
   Output, A, B: integer  := 0;
   TagVal: integer  := 0;
   OtherVal: real  := 0.0;
SUBMODULES
   InlineA Invocation
      ( -1.0 , -0.2 , 0.0 , 0.5 , 0.5
       ) : MODULEDEFINITION DateCode_ 200200001
   LOCALVARIABLES
      InputSignal: boolean ;
      OutputSignal: boolean  := False;
      Setpoint, Out: integer  := 0;


   ModuleDef
   ClippingBounds = ( -2.98023E-08 , 1.49012E-08 )
   ( 1.0 , 1.0 )

   ModuleCode
   EQUATIONBLOCK Logic COORD 0.0, 0.0 OBJSIZE 1.0, 0.5 :
      OutputSignal = InputSignal;
      InputSignal = True;
   EQUATIONBLOCK Control COORD 0.0, 0.5 OBJSIZE 1.0, 0.5 :
      Setpoint = 10;
      Setpoint = 20;
      Out = Setpoint;

   ENDDEF (*InlineA*);

   InlineB Invocation
      ( 0.2 , -0.6 , 0.0 , 0.4 , 0.5
       ) : MODULEDEFINITION DateCode_ 200200002
   LOCALVARIABLES
      InputSignal: boolean ;
      OutputSignal: boolean  := False;
      Setpoint, Out: integer  := 0;


   ModuleDef
   ClippingBounds = ( -5.96046E-08 , -1.41561E-07 )
   ( 1.0 , 1.0 )

   ModuleCode
   EQUATIONBLOCK Logic COORD 0.0, 0.0 OBJSIZE 1.0, 0.5 :
      OutputSignal = InputSignal;
      InputSignal = True;
   EQUATIONBLOCK Control COORD 0.0, 0.5 OBJSIZE 1.0, 0.5 :
      Setpoint = 10;
      Setpoint = 20;
      Out = Setpoint;

   ENDDEF (*InlineB*);

   InlineC Invocation
      ( -0.5 , 0.0999999 , 0.0 , 0.4 , 0.4
       ) : MODULEDEFINITION DateCode_ 200200003
   LOCALVARIABLES
      InputSignal: boolean ;
      OutputSignal: boolean  := False;
      Setpoint, Out: integer  := 0;


   ModuleDef
   ClippingBounds = ( -9.68575E-08 , 4.47035E-08 )
   ( 1.0 , 1.0 )

   ModuleCode
   EQUATIONBLOCK Logic COORD 0.0, 0.0 OBJSIZE 1.0, 0.5 :
      OutputSignal = InputSignal;
      InputSignal = True;
   EQUATIONBLOCK Control COORD 0.0, 0.5 OBJSIZE 1.0, 0.5 :
      Setpoint = 10;
      Setpoint = 20;
      Out = Setpoint;

   ENDDEF (*InlineC*);

   MixerV1 Invocation
      ( -0.2 , -0.6 , 0.0 , 0.4 , 0.4
       ) : MODULEDEFINITION DateCode_ 200200004
   LOCALVARIABLES
      Output: integer  := 0;


   ModuleDef
   ClippingBounds = ( -2.98023E-08 , 2.98023E-08 )
   ( 1.0 , 1.0 )

   ModuleCode
   EQUATIONBLOCK Logic COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Output = 1;

   ENDDEF (*MixerV1*);

   MixerV2 Invocation
      ( -1.0 , -0.6 , 0.0 , 0.4 , 0.4
       ) : MODULEDEFINITION DateCode_ 200200005
   LOCALVARIABLES
      Output: integer  := 0;


   ModuleDef
   ClippingBounds = ( -7.45058E-08 , -5.96046E-08 )
   ( 1.0 , 1.0 )

   ModuleCode
   EQUATIONBLOCK Logic COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Output = 2;

   ENDDEF (*MixerV2*);

   LoopType Invocation
      ( -0.5 , 0.48 , 0.0 , 0.4 , 0.4
       ) : LoopLogic;

   FaultType Invocation
      ( -0.78 , 0.3 , 0.0 , 0.28 , 0.4
       ) : FaultLogic;

   ResType Invocation
      ( -0.6 , -0.6 , 0.0 , 0.4 , 0.4
       ) : ResLogic;

   VarType Invocation
      ( 0.2 , -1.0 , 0.0 , 0.4 , 0.4
       ) : VarLogic;

   DepType Invocation
      ( 0.6 , -0.1 , 0.0 , 0.4 , 0.4
       ) : DepLogic;

   SeqType Invocation
      ( 0.6 , -1.0 , 0.0 , 0.4 , 0.36
       ) : SeqLogic;

   ComplexType Invocation
      ( 0.6 , 0.3 , 0.0 , 0.4 , 0.4
       ) : ComplexLogic;

   ValveOk Invocation
      ( -1.0 , -1.0 , 0.0 , 0.4 , 0.4
       ) : ValveType (
   CmdOpen => OpenCmd,
   CmdClose => CloseCmd,
   Timeout => Duration_Value "10s",
   LimitMin => 5.0,
   LimitMax => 95.0);

   ValveMissing Invocation
      ( -0.6 , -1.0 , 0.0 , 0.4 , 0.4
       ) : ValveType (
   CmdOpen => OpenCmd,
   CmdClose => CloseCmd,
   Timeout => Duration_Value "20s",
   LimitMin => 10.0,
   LimitMax => 90.0);

   ValveMismatch Invocation
      ( 0.2 , -0.1 , 0.0 , 0.4 , 0.4
       ) : SimpleValve (
   Enable => OpenCmd,
   Setpoint => PosValue);

   MinMaxChild Invocation
      ( 0.4 , 0.4 , 0.4 , 0.4 , 0.4
       ) : MinMaxType (
   MaxValue => MinValue);

   StringChild Invocation
      ( 0.0 , 0.8 , 0.4 , 0.4 , 0.4
       ) : StringType (
   TargetValue => SourceValue);

   ShadowChild Invocation
      ( -1.0 , 0.3 , 0.0 , 0.22 , 0.16
       ) : MODULEDEFINITION DateCode_ 200200006
   LOCALVARIABLES
      Setting, Mirror: integer  := 0;


   ModuleDef
   ClippingBounds = ( 5.96046E-08 , 1.49012E-08 )
   ( 1.0 , 1.0 )

   ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Mirror = Setting;

   ENDDEF (*ShadowChild*);

   DoseA Invocation
      ( 0.0 , 1.2 , 0.4 , 0.4 , 0.4
       ) : DoseValve (
   Timeout => 10);

   DoseB Invocation
      ( 0.4 , 1.2 , 0.4 , 0.4 , 0.4
       ) : DoseValve (
   Timeout => 15);

   GuardHmi Invocation
      ( -0.1 , 0.300001 , 0.0 , 0.3 , 0.199999
       ) : GuardType (
   InCommand => HmiCmd);

   ToggleParWindow Invocation
      ( -1.0 , 0.8 , 0.0 , 0.28 , 0.2
       ) : MODULEDEFINITION DateCode_ 217032156
   MODULEPARAMETERS
      Path "Path to pop-up module": string  := "--ParDisplay+++Form";
      RelativePos: boolean  := False;
      Info "IN Optional information (HMI only)": identstring  := "";
      WindowTitle "IN Optional WindowTitle": string  := "";
      xPos: real  := 0.3;
      yPos: real  := 0.2;
      xSize: real  := 0.33;
      Enable "IN Interaction possible on Enable AND EnablePrivilege": boolean
      := True;
   LOCALVARIABLES
      ShowInfo "Enable Info text on button", EnablePrivilege: boolean ;
   SUBMODULES
      FM1 Invocation
         ( 0.5 , 0.5 , 0.0 , 0.5 , 0.5
          ) : MODULEDEFINITION DateCode_ 307663975 ( Frame_Module )


      ModuleDef
      ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
      GraphObjects :
         TextObject ( -1.0 , -1.0 ) ( 1.0 , 0.3 )
            "Info" VarName Width_ = 5  ValueFraction = 2
            OutlineColour : Colour0 = -3

      ENDDEF (*FM1*);


   ModuleDef
   ClippingBounds = ( 0.0 , 1.49012E-08 ) ( 1.0 , 1.0 )
   GraphObjects :
      TextObject ( 0.035 , 0.035 ) ( 0.035 , 0.11 )
         "1" LeftAligned
         Enable_ = True : InVar_ False
         OutlineColour : Colour0 = -3
      RectangleObject ( 5.96046E-08 , 1.49012E-08 )
         ( 1.0 , 1.0 )
         OutlineColour : Colour0 = 5
   InteractObjects :
      ComButProc_ ( 1.49012E-08 , -2.98023E-08 )
         ( 1.0 , 1.0 )
         ToggleWindow
         "" : InVar_ "Path" "" : InVar_ "WindowTitle" False : InVar_
         "RelativePos" 0.0 : InVar_ "XPos" 0.0 : InVar_ "YPos" 0.0 : InVar_
         "XSize" 0.0 False 0 0 False 0
         Enable_ = True : (EnablePrivilege AND Enable) Variable = 0.0
         TextObject = "" : InVar_ LitString "+"


   ModuleCode
   EQUATIONBLOCK Start_Init COORD -1.60187E-07, 2.38419E-07 OBJSIZE 1.0, 0.14 :
      ShowInfo = StringLength(Info) > 0;

   ENDDEF (*ToggleParWindow*);

   Unit1 Invocation
      ( -0.17 , 1.25 , 0.0 , 0.27 , 0.27
       ) : MODULEDEFINITION DateCode_ 251128512
   LOCALVARIABLES
      Unit1InputVariable: integer ;
      Remsys: string ;
      RemoteSys1: string  := "172.18.72.54";
      RemoteSys2: String  := "172.18.72.55";
      RemoteSysSelect, Unit1OutputVariable, Unit1OutputVariableD: integer ;
      ProgramName: string  := "P1";
      si: integer ;
      RemoteVarName: string  := "Unit2VarIn";
      LocalVariable: integer ;
      Execute: boolean ;
      UnitSelect: integer ;
      Unit1Str: string  := "Unit1VarIn";
      Unit2Str: string  := "Unit2VarIn";
   SUBMODULES
      MMSWriteVar Invocation
         ( -0.41 , 0.46 , 0.0 , 0.08 , 0.08
          ) : MMSWriteVar (
      Remsys => Remsys,
      RemoteVarName => RemoteVarName,
      LocalVariable => LocalVariable,
      Execute => Execute);


   ModuleDef
   ClippingBounds = ( -0.777778 , -1.0 ) ( 0.777778 , 1.0 )
   InteractObjects :
      TextBox_ ( -0.52 , 0.34 ) ( 0.24 , 0.06 )
         Int_Value
         Variable = 0 : OutVar_ "LocalVariable" LeftAligned Abs_ Digits_

         FillColour : Colour0 = 9 Colour1 = -1
      OptBut_ ( -0.52 , -0.0399999 ) ( 0.22 , -0.2 )
         Int_Value
         Variable = 0 : OutVar_ "UnitSelect" Value_ = 0 : InVar_ 1
         TextObject = "" : InVar_ LitString "Unit1"

         FillColour : Colour1 = -1
      OptBut_ ( -0.52 , -0.22 ) ( 0.22 , -0.38 )
         Int_Value
         Variable = 0 : OutVar_ "UnitSelect" Value_ = 0 : InVar_ 2
         TextObject = "" : InVar_ LitString "Unit2"

         FillColour : Colour1 = -1
      OptBut_ ( -0.52 , -0.54 ) ( 0.22 , -0.7 )
         Int_Value
         Variable = 0 : OutVar_ "RemoteSysSelect" Value_ = 0 : InVar_ 1
         TextObject = "" : InVar_ LitString "RemoteSys1"

         FillColour : Colour1 = -1
      OptBut_ ( -0.52 , -0.72 ) ( 0.22 , -0.88 )
         Int_Value
         Variable = 0 : OutVar_ "RemoteSysSelect" Value_ = 0 : InVar_ 2
         TextObject = "" : InVar_ LitString "RemoteSys2"

         FillColour : Colour1 = -1

   ModuleCode
   EQUATIONBLOCK Start_Equa1 COORD 0.16, 0.6 OBJSIZE 0.54, 0.4 :
      CopyString(ProgramName, ProgramName, si);
   EQUATIONBLOCK UnitSelector COORD -0.78, 0.58 OBJSIZE 0.48, 0.32 :
      IF UnitSelect == 1 THEN
         CopyString(Unit1Str, RemoteVarName, si);
      ELSIF UnitSelect == 2 THEN
         CopyString(Unit2Str, RemoteVarName, si);
      ENDIF;
   EQUATIONBLOCK RemoteSysSelect COORD -0.32, 0.58 OBJSIZE 0.48, 0.32 :
      IF RemoteSysSelect == 1 THEN
         CopyString(RemoteSys1, Remsys, si);
      ELSIF RemoteSysSelect == 2 THEN
         CopyString(RemoteSys2, Remsys, si);
      ENDIF;

   ENDDEF (*Unit1*);

   Unit2 Invocation
      ( 0.29 , 1.25 , 0.0 , 0.2 , 0.2
       ) : MODULEDEFINITION DateCode_ 251128512
   LOCALVARIABLES
      Unit2InputVariable, Unit2OutputVariable, Unit2OutputVariableD: integer ;
      ProgramName: string  := "P2";
      si, LocalVar: integer ;
   SUBMODULES
      MMSVarGlobal Invocation
         ( 0.39 , -0.12 , 0.0 , 0.08 , 0.08
          ) : MMSVarGlobal (
      GlobalVarName => "Unit1VarIn",
      LocalVariable => LocalVar);


   ModuleDef
   ClippingBounds = ( -0.7 , -1.0 ) ( 0.7 , 1.0 )
   GraphObjects :
      TextObject ( -0.58 , 0.86 ) ( -0.58 , 0.54 )
         "Unit1" LeftAligned
         OutlineColour : Colour0 = -3
   InteractObjects :
      TextBox_ ( -0.45 , -0.4 ) ( 0.299999 , -0.65 )
         Int_Value
         Variable = 0 : OutVar_ "LocalVar" LeftAligned Abs_ Digits_

         FillColour : Colour0 = 9 Colour1 = -1

   ModuleCode
   EQUATIONBLOCK Start_Equa1 COORD 0.16, 0.6 OBJSIZE 0.54, 0.4 :
      CopyString(ProgramName, ProgramName, si);

   ENDDEF (*Unit2*);

   Unit3 Invocation
      ( 0.79 , 1.25 , 0.0 , 0.2 , 0.2
       ) : MODULEDEFINITION DateCode_ 251128512
   LOCALVARIABLES
      Unit2InputVariable, Unit2OutputVariable, Unit2OutputVariableD: integer ;
      ProgramName: string  := "P2";
      si, LocalVar: integer ;
   SUBMODULES
      MMSVarGlobal Invocation
         ( 0.39 , -0.12 , 0.0 , 0.08 , 0.08
          ) : MMSVarGlobal (
      GlobalVarName => "Unit2VarIn",
      LocalVariable => LocalVar);


   ModuleDef
   ClippingBounds = ( -0.7 , -1.0 ) ( 0.7 , 1.0 )
   GraphObjects :
      TextObject ( -0.58 , 0.86 ) ( -0.58 , 0.54 )
         "Unit2" LeftAligned
         OutlineColour : Colour0 = -3
   InteractObjects :
      TextBox_ ( -0.45 , -0.4 ) ( 0.299999 , -0.65 )
         Int_Value
         Variable = 0 : OutVar_ "LocalVar" LeftAligned Abs_ Digits_

         FillColour : Colour0 = 9 Colour1 = -1

   ModuleCode
   EQUATIONBLOCK Start_Equa1 COORD 0.16, 0.6 OBJSIZE 0.54, 0.4 :
      CopyString(ProgramName, ProgramName, si);

    ENDDEF (*Unit3*);

    MmsConflict1 Invocation
       ( 0.4 , 1.6 , 0.0 , 0.1 , 0.1
        ) : MMSWriteVar (
   LocalVariable => TagVal,
   RemoteVarName => "MV_1001");
    MmsConflict2 Invocation
       ( 0.6 , 1.6 , 0.0 , 0.1 , 0.1
        ) : MMSWriteVar (
   LocalVariable => OtherVal,
   RemoteVarName => "MV_1001");
    MmsConflict3 Invocation
       ( 0.8 , 1.6 , 0.0 , 0.1 , 0.1
        ) : MMSWriteVar (
   LocalVariable => TagVal,
   RemoteVarName => "MV-1001");
    MmsConflict4 Invocation
       ( 1.0 , 1.6 , 0.0 , 0.1 , 0.1
        ) : MMSWriteVar (
   LocalVariable => OtherVal,
   RemoteVarName => "AI_2001");


ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.66 )
GraphObjects :
   CompositeObject

ModuleCode
EQUATIONBLOCK Main COORD -0.5, -0.2 OBJSIZE 0.7, 0.3 :
   PosValue = RawValue + 1;
   HmiCmd = True;
EQUATIONBLOCK Start_SetStrings COORD 0.2, 0.3 OBJSIZE 0.4, 0.4 :
   (* Path NOT OK *);
   CopyString(DefaultPath, PathOK, si);
   SetStringPos(PathOK, 1, si2);
   InsertString(PathOK, DefaultPath, 2, si3);
   CutString(PathOK, 2, si4);
   OprPathIndex = 1;
EQUATIONBLOCK RefactorFeedback COORD -0.1, 0.1 OBJSIZE 0.3, 0.2 :
   B = A;
EQUATIONBLOCK Bounds COORD 0.64, 0.7 OBJSIZE 0.36, 0.24 :
   IF Output < Min_Output THEN
      Output = Min_Output;
   ENDIF;
   IF Output > Max_Output THEN
      Output = Max_Output;
   ENDIF;
   Output = 12;

ENDDEF (*BasePicture*);
