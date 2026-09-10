"Syntax version 2.23, date: 2026-09-08-11:20:02.340 N"
"Original file date: ---"
"Program date: 2026-09-08-11:08:26.345, name: EveryIssueLib"
(* Denne programenhed er oprettet 2026-09-08 08:38 af sqhj. *)

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 249443658
TYPEDEFINITIONS
   SensorType = RECORD DateCode_ 200100001
      UsedField, UnusedField: real  := 0.0;
   ENDDEF
    (*SensorType*);

TYPEDEFINITIONS
   InnerChild = MODULEDEFINITION DateCode_ 200100002
   LOCALVARIABLES
      Setting, Mirror: integer  := 0;


   ModuleDef
   ClippingBounds = ( 0.0 , -7.45058E-08 ) ( 1.0 , 1.0 )

   ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Mirror = Setting;

   ENDDEF (*InnerChild*);

   LoopLogic = MODULEDEFINITION DateCode_ 200100003
   LOCALVARIABLES
      InputSignal: boolean ;
      OutputSignal, NeverConsumed: boolean  := False;
      Setpoint, LoopOut: integer  := 0;


   ModuleDef
   ClippingBounds = ( -2.98023E-08 , 5.96046E-08 )
   ( 1.0 , 1.0 )

   ModuleCode
   EQUATIONBLOCK Logic COORD 0.0, 0.0 OBJSIZE 1.0, 0.5 :
      (* IF Running THEN
            OutputSignal = True;
         ENDIF; *);
      OutputSignal = InputSignal;
      InputSignal = True;
      OutputSignal = OutputSignal;
      NeverConsumed = False;
   EQUATIONBLOCK Control COORD 0.0, 0.5 OBJSIZE 1.0, 0.5 :
      Setpoint = 10;
      Setpoint = 20;
      LoopOut = Setpoint;

   ENDDEF (*LoopLogic*);

   DepLogic = MODULEDEFINITION DateCode_ 200100004
   LOCALVARIABLES
      A, B, C, Acc: integer  := 0;


   ModuleDef
   ClippingBounds = ( -1.11759E-08 , -1.49012E-08 )
   ( 1.0 , 1.0 )

   ModuleCode
   EQUATIONBLOCK Dep COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      C = A + B;
      A = B + 1;
      B = 10;
      Acc = Acc + 1;
      Acc = Acc + C;

   ENDDEF (*DepLogic*);

   FaultLogic = MODULEDEFINITION DateCode_ 200100005
   LOCALVARIABLES
      HighFault, HandledFault, Status: boolean  := False;
      AlwaysOne: integer  := 1;
      NeverZero: integer  := 0;
      Count: integer  := 5;


   ModuleDef
   ClippingBounds = ( 2.98023E-08 , -5.58794E-08 )
   ( 1.0 , 1.0 )

   ModuleCode
   EQUATIONBLOCK Faults COORD 0.0, 0.0 OBJSIZE 1.0, 0.5 :
      HighFault = True;
      HandledFault = True;
      IF HandledFault THEN
         Status = True;
      ENDIF;
      HandledFault = False;
      IF Status THEN
         Status = False;
      ENDIF;
   EQUATIONBLOCK Inferred COORD 0.0, 0.5 OBJSIZE 1.0, 0.5 :
      IF AlwaysOne == 1 THEN
         Status = True;
      ELSE
         Status = False;
      ENDIF;
      IF NeverZero == 1 THEN
         HighFault = True;
      ENDIF;
      IF Count < 0 THEN
         Status = False;
      ENDIF;
      Count = 5;

   ENDDEF (*FaultLogic*);

   ResLogic = MODULEDEFINITION DateCode_ 200100006
   LOCALVARIABLES
      FileRef: tObject ;
      FirstPath, SecondPath: string  := "";
      AsyncOp: AsyncOperation ;
      ResStatus: integer  := 0;
      SysVarId: string  := "ScanLoop.Cost";
      CostValue: string  := "Active";
      Raw: integer  := 0;
      Smoothed: integer State := 0;
      Flag: boolean State := False;


   ModuleDef
   ClippingBounds = ( 4.47035E-08 , -5.96046E-08 )
   ( 1.0 , 1.0 )

   ModuleCode
   EQUATIONBLOCK Resources COORD 0.0, 0.0 OBJSIZE 1.0, 0.32 :
      OpenReadFile(FileRef, FirstPath, AsyncOp, ResStatus);
      OpenWriteFile(FileRef, SecondPath, AsyncOp, ResStatus);
   EQUATIONBLOCK Cost COORD 0.0, 0.32 OBJSIZE 1.0, 0.3 :
      AssignSystemString(SysVarId, CostValue, ResStatus);
   EQUATIONBLOCK Timing COORD 0.0, 0.62 OBJSIZE 1.0, 0.38 :
      Smoothed = Smoothed:Old + Raw;
      Flag =  NOT Flag:Old;

   ENDDEF (*ResLogic*);

   VarLogic = MODULEDEFINITION DateCode_ 200100007
   LOCALVARIABLES
      UnusedLocal, WriteOnly, ReadOnly, LatchVar: integer  := 0;
      CondCmd: boolean  := False;
      DisplayValue: integer  := 0;
      Sensor: SensorType ;
      SensorOut: real  := 0.0;
      setting: integer  := 42;
      FanVar: integer  := 0;
   SUBMODULES
      Inner Invocation
         ( -1.0 , -5.96046E-08 , 0.0 , 1.0 , 1.0
          ) : InnerChild;


   ModuleDef
   ClippingBounds = ( -1.0 , -3.8743E-07 ) ( 1.0 , 1.0 )
   GraphObjects :
      TextObject ( 0.0 , 0.0 ) ( 1.0 , 0.2 )
         "DisplayValue" VarName Width_ = 5 : InVar_ 5  ValueFraction = 2
         OutlineColour : Colour0 = -3

   ModuleCode
   EQUATIONBLOCK Writes COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      WriteOnly = 5;
      Sensor.UsedField = Sensor.UsedField + 1.0;
      SensorOut = Sensor.UsedField;
      SensorOut = SensorOut + ReadOnly;
      IF CondCmd THEN
         LatchVar = 1;
      ENDIF;
      SensorOut = SensorOut + LatchVar;
      setting = setting + 1;
      FanVar = FanVar + 1;
      FanVar = FanVar + 1;
      FanVar = FanVar + 1;
      FanVar = FanVar + 1;
      FanVar = FanVar + 1;
      FanVar = FanVar + 1;
      FanVar = FanVar + 1;
      FanVar = FanVar + 1;
      FanVar = FanVar + 1;
      FanVar = FanVar + 1;
      SensorOut = SensorOut + FanVar;

   ENDDEF (*VarLogic*);

   ComplexLogic = MODULEDEFINITION DateCode_ 200100008
   LOCALVARIABLES
      Cond0, Cond1, Cond2, Cond3, Cond4, Cond5, Cond6, Cond7, Cond8, Cond9:
      boolean  := False;
      Output: integer  := 0;


   ModuleDef
   ClippingBounds = ( -1.04308E-07 , -1.78814E-07 )
   ( 1.0 , 1.0 )

   ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      IF Cond0 THEN
         Output = 0;
      ENDIF;
      IF Cond1 THEN
         Output = 1;
      ENDIF;
      IF Cond2 THEN
         Output = 2;
      ENDIF;
      IF Cond3 THEN
         Output = 3;
      ENDIF;
      IF Cond4 THEN
         Output = 4;
      ENDIF;
      IF Cond5 THEN
         Output = 5;
      ENDIF;
      IF Cond6 THEN
         Output = 6;
      ENDIF;
      IF Cond7 THEN
         Output = 7;
      ENDIF;
      IF Cond8 THEN
         Output = 8;
      ENDIF;
      IF Cond9 THEN
         Output = 9;
      ENDIF;

   ENDDEF (*ComplexLogic*);

   SeqLogic = MODULEDEFINITION DateCode_ 216565218
   LOCALVARIABLES
      StartCmd: boolean  := False;
      SharedValue, Output, SharedOutput, Counter, Other: integer  := 0;
      ResetValue: integer  := 1;
      SeqResetOld: boolean  := False;


   ModuleDef
   ClippingBounds = ( -4.47035E-08 , -4.47035E-08 )
   ( 1.0 , 2.5 )

   ModuleCode
   EQUATIONBLOCK Pre COORD 0.0, 0.0 OBJSIZE 1.0, 0.5 :
      IF  NOT OpSeq.Reset THEN
         Counter = ResetValue;
      ELSIF  NOT SeqResetOld THEN
         Other = ResetValue;
      ENDIF;
      SeqResetOld = OpSeq.Reset;

   SEQUENCE MixedSeq  (SeqControl,SeqTimer) COORD -5.55112E-17, 0.5 OBJSIZE 1.0
   , 0.5
      SEQINITSTEP MixedInit
      SEQTRANSITION MixedStart WAIT_FOR StartCmd
      SEQSTEP MixedLaunch
         ACTIVECODE
            Output = SharedValue;
      SEQTRANSITION MixedFork WAIT_FOR True
      PARALLELSEQ
         SEQSTEP MixedLeft
            ACTIVECODE
               Output = SharedValue;
         SEQTRANSITION MixedLeftDone WAIT_FOR Output > 0
         SEQSTEP MixedLeftMid
            ENTERCODE
               SharedValue = SharedValue + 1;
         SEQTRANSITION MixedLeftExit WAIT_FOR True
         SEQSTEP MixedLeftJoin
      PARALLELBRANCH
         SEQSTEP MixedRight
            ACTIVECODE
               SharedValue = 2;
         SEQTRANSITION MixedRightDone WAIT_FOR SharedValue > 0
         SEQSTEP MixedRightMid
            ENTERCODE
               Output = Output + 1;
         SEQTRANSITION MixedRightExit WAIT_FOR True
         SEQSTEP MixedRightJoin
      ENDPARALLEL
      SEQTRANSITION MixedMerge WAIT_FOR True
      SEQSTEP MixedMergeStep
         ENTERCODE
            StartCmd = False;
      SEQTRANSITION MixedReset WAIT_FOR  NOT StartCmd
   ENDSEQUENCE


   SEQUENCE RaceSeq  (SeqControl,SeqTimer) COORD -1.11022E-16, 1.0 OBJSIZE 1.0,
   0.5
      SEQINITSTEP RaceInit
         ENTERCODE
            SharedOutput = 0;
      SEQTRANSITION RaceStart WAIT_FOR StartCmd
      SEQSTEP RaceFork
         ENTERCODE
            SharedOutput = 0;
      SEQTRANSITION RaceForkTr WAIT_FOR True
      PARALLELSEQ
         SEQSTEP RaceLeft
            ACTIVECODE
               SharedOutput = 1;
         SEQTRANSITION RaceLeftDone WAIT_FOR SharedOutput > 0
         SEQSTEP RaceLeftMid
            ENTERCODE
               SharedOutput = SharedOutput + 10;
         SEQTRANSITION RaceLeftExit WAIT_FOR True
         SEQSTEP RaceLeftJoin
      PARALLELBRANCH
         SEQSTEP RaceRight
            ACTIVECODE
               SharedOutput = 2;
         SEQTRANSITION RaceRightDone WAIT_FOR SharedOutput > 0
         SEQSTEP RaceRightMid
            ENTERCODE
               SharedOutput = SharedOutput + 20;
         SEQTRANSITION RaceRightExit WAIT_FOR True
         SEQSTEP RaceRightJoin
      ENDPARALLEL
      SEQTRANSITION RaceMerge WAIT_FOR True
      SEQSTEP RaceMergeStep
         ENTERCODE
            StartCmd = False;
      SEQTRANSITION RaceReset WAIT_FOR  NOT StartCmd
   ENDSEQUENCE


   SEQUENCE OpSeq  (SeqControl,SeqTimer) COORD 0.0, 1.5 OBJSIZE 1.0, 0.5
      SEQINITSTEP OpInit
      SEQTRANSITION OpDone WAIT_FOR False
   ENDSEQUENCE


   SEQUENCE UnreachSeq  (SeqControl,SeqTimer) COORD 1.66533E-16, 2.0 OBJSIZE
   1.0, 0.5
      SEQINITSTEP UnreachInit
         ENTERCODE
            SharedValue = 0;
      SEQTRANSITION UnreachGo WAIT_FOR True
      SEQSTEP UnreachStepA
      SEQTRANSITION UnreachDead WAIT_FOR False
      SEQSTEP UnreachBlocked
         ENTERCODE
            SharedValue = 1;
      SEQTRANSITION UnreachDup WAIT_FOR StartCmd
      SEQSTEP UnreachDeadEnd
      SEQTRANSITION UnreachDup2 WAIT_FOR StartCmd
   ENDSEQUENCE


   ENDDEF (*SeqLogic*);

   ValveType = MODULEDEFINITION DateCode_ 200100010
   MODULEPARAMETERS
      CmdOpen, CmdClose: boolean ;
      Timeout: duration  := Duration_Value "5s";
      LimitMin: real  := 0.0;
      LimitMax: real  := 100.0;
   LOCALVARIABLES
      Position: real  := 0.0;
      ValveState: boolean  := False;


   ModuleDef
   ClippingBounds = ( 0.0 , 1.19209E-07 ) ( 1.0 , 1.0 )

   ModuleCode
   EQUATIONBLOCK Eq COORD 0.0, -2.77556E-17 OBJSIZE 1.0, 1.0 :
      IF CmdOpen THEN
         ValveState = True;
      ENDIF;
      IF CmdClose THEN
         ValveState = False;
      ENDIF;
      Position = LimitMin + (LimitMax - LimitMin)*0.5;

   ENDDEF (*ValveType*);

   SimpleValve = MODULEDEFINITION DateCode_ 200100011
   MODULEPARAMETERS
      Enable: boolean ;
      Setpoint: real ;
   LOCALVARIABLES
      OutVal: real  := 0.0;


   ModuleDef
   ClippingBounds = ( -8.9407E-08 , 1.49012E-08 )
   ( 1.0 , 1.0 )

   ModuleCode
   EQUATIONBLOCK Eq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      OutVal = Setpoint;

   ENDDEF (*SimpleValve*);

   MinMaxType = MODULEDEFINITION DateCode_ 200100012
   MODULEPARAMETERS
      MaxValue: integer ;


   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

   ENDDEF (*MinMaxType*);

   StringType = MODULEDEFINITION DateCode_ 200100013
   MODULEPARAMETERS
      TargetValue: identstring ;


   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

   ENDDEF (*StringType*);

   DoseValve = MODULEDEFINITION DateCode_ 200100014
   MODULEPARAMETERS
      Timeout: integer  := 10;


   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

   ENDDEF (*DoseValve*);

   GuardType = MODULEDEFINITION DateCode_ 200100015
   MODULEPARAMETERS
      InCommand: boolean  := False;
   LOCALVARIABLES
      EmergencyShutdown: boolean  := False;


   ModuleDef
   ClippingBounds = ( 4.47035E-08 , -2.98023E-08 )
   ( 1.0 , 1.0 )

   ModuleCode
   EQUATIONBLOCK GuardEq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      EmergencyShutdown = InCommand;

   ENDDEF (*GuardType*);

   MyAlarm = MODULEDEFINITION DateCode_ 200100016
   MODULEPARAMETERS
      Tag: string  := "";
      Priority: integer  := 0;
      Condition: boolean  := False;


   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

   ENDDEF (*MyAlarm*);

   OPMessage = MODULEDEFINITION DateCode_ 200100018
   MODULEPARAMETERS
      UseSignature: boolean  := False;


   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

   ENDDEF (*OPMessage*);

   MES_BatchControl = MODULEDEFINITION DateCode_ 200100019
   MODULEPARAMETERS
      BatchName: string  := "default_batch";
      MaxTry: integer  := 3;
      RepeatTry: boolean  := False;


   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

   ENDDEF (*MES_BatchControl*);

LOCALVARIABLES
   TempHigh, PressHigh, LevelLow, Ack, AlarmTrip: boolean  := False;
   TagVal: integer  := 0;
   OtherVal: real  := 0.0;
   OperatorCommand, Cmd, Done: boolean  := False;
   StrVal: string  := "TestVal";
SUBMODULES
   Alarm1 Invocation
      ( 0.0 , 0.0 , 0.0 , 0.4 , 0.4
       ) : MyAlarm (
   Tag => "TEMP_HIGH",
   Priority => 1,
   Condition => TempHigh);

   Alarm2 Invocation
      ( 0.5 , 0.0 , 0.0 , 0.4 , 0.4
       ) : MyAlarm (
   Tag => "TEMP_HIGH",
   Priority => 1,
   Condition => TempHigh);

   Alarm3 Invocation
      ( 0.0 , 0.5 , 0.0 , 0.4 , 0.4
       ) : MyAlarm (
   Tag => "PRESS_HIGH",
   Priority => 1,
   Condition => PressHigh);

   Alarm4 Invocation
      ( 0.5 , 0.52 , 0.0 , 0.4 , 0.4
       ) : MyAlarm (
   Tag => "PRESS_HIGH",
   Priority => 2,
   Condition => PressHigh);

   Alarm5 Invocation
      ( 0.0 , 0.0 , 0.5 , 0.4 , 0.4
       ) : MyAlarm (
   Tag => "LEVEL_LOW",
   Priority => 3,
   Condition => LevelLow);

   Guard Invocation
      ( -0.6 , -0.2 , 0.0 , 0.4 , 0.4
       ) : GuardType (
   InCommand => OperatorCommand);

   OPMsg Invocation
      ( 0.0 , 0.0 , 0.0 , 0.4 , 0.4
       ) : OPMessage (
   UseSignature => True);

   MESBC Invocation
      ( 0.5 , 0.0 , 0.0 , 0.4 , 0.4
       ) : MES_BatchControl;

   LoopLogic Invocation
      ( -1.0 , -1.0 , 0.0 , 0.4 , 0.4
       ) : LoopLogic;

   DepLogic Invocation
      ( -0.6 , -1.0 , 0.0 , 0.4 , 0.4
       ) : DepLogic;

   FaultLogic Invocation
      ( -0.2 , -1.0 , 0.0 , 0.4 , 0.4
       ) : FaultLogic;

   ResLogic Invocation
      ( 0.2 , -1.0 , 0.0 , 0.4 , 0.4
       ) : ResLogic;

   VarLogic Invocation
      ( 0.2 , -0.6 , 0.0 , 0.4 , 0.4
       ) : VarLogic;

   ComplexLogic Invocation
      ( -1.0 , -0.6 , 0.0 , 0.4 , 0.4
       ) : ComplexLogic;

   SeqLogic Invocation
      ( -0.199999 , -0.2 , 0.0 , 0.4 , 0.4
       ) : SeqLogic;

   ValveType Invocation
      ( -1.0 , -0.2 , 0.0 , 0.4 , 0.4
       ) : ValveType (
   CmdOpen => Cmd,
   CmdClose => OperatorCommand);

   SimpleValve Invocation
      ( 0.2 , -0.2 , 0.0 , 0.4 , 0.4
       ) : SimpleValve (
   Enable => Cmd,
   Setpoint => OtherVal);

   MinMaxType Invocation
      ( -0.5 , 1.0 , 0.0 , 0.4 , 0.4
       ) : MinMaxType (
   MaxValue => TagVal);

   StringType Invocation
      ( 0.0 , 1.0 , 0.0 , 0.4 , 0.4
       ) : StringType (
   TargetValue => StrVal);

   DoseValve Invocation
      ( 0.5 , 1.0 , 0.0 , 0.4 , 0.4
       ) : DoseValve (
   Timeout => 5);


ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

ModuleCode
EQUATIONBLOCK Fix COORD -0.6, -0.6 OBJSIZE 0.4, 0.4 :
   AlarmTrip = True;
   PressHigh = PressHigh OR Ack;
   TagVal = TagVal + 1;
   OperatorCommand = True;

SEQUENCE BatchSeq  (SeqControl,SeqTimer) COORD -1.0, 0.2 OBJSIZE 0.8, 0.5
   SEQINITSTEP Init
   SEQTRANSITION TrGo WAIT_FOR Cmd
   SEQSTEP step_mix
   SEQTRANSITION  WAIT_FOR Done
   SEQSTEP Finish
   SEQTRANSITION MyTrans WAIT_FOR Done
ENDSEQUENCE


ENDDEF (*BasePicture*);
