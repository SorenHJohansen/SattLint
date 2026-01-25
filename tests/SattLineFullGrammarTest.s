"Syntax version 2.23, date: 1998-05-28-08:31:41.769 N"
"Original file date: 1998-05-28-08:31:41.769"
"Program date: 1998-05-28-08:31:41.769, name: BatchDemo"
(* 1997-03-19 11:49 Alfa Laval Automation
   5139 Graphical connections moved in GraphDoc
   modules
   
   1997-11-07 13:02 Alfa Laval Automation
   12903 - Change "Empty" to "Dummy"
   
   1997-11-20 12:16 Alfa Laval Automation
   12903 Change "Empty" to "Dummy"
   
   1997-12-16 10:13 Alfa Laval Automation
   13180 RecipeDocMaster problems
   
   1997-12-17 12:53 Alfa Laval Automation
   13176 EnableEdit problems
   
   1998-01-16 09:48 Alfa Laval Automation
   13308 PageLength problems in RecipeDocControl
   
   1998-05-14 17:29 Alfa Laval Automation
   13671 Update Batchdemo because of changes in
   BatchLib
   
   1998-05-28 08:36 Alfa Laval Automation
   13709 - DirectoryList problems *)

BasePicture
(* Demo picture for BatchLib.
   --------------------------
   
   It includes a RecipeManager, a ProcessManager and two groups of
   process units.
   
   The RecipeManager is used to create, edit and document master recipes and
   master operation recipes.
   
   The ProcessManager is used to create, edit, document, download and
   start master recipes and master operation recipes.
   
   The RecipeManager and the ProcessManager include modules for editing
   and documenting recipes.
   
   Finally, there are two groups of three process units each. The units are
   identical and called Tank1 - Tank6.
   
   The program has three different scangroups, apart from "Prog" scangroups.
   RecipeManager executes in the "Prog" scangroup of the surounding module.
   ProcessManager must execute in a specific operator station. The address
   is specified as the initial value of the component OpName in the
   datatype SysListType.
   
   The units Tank1, Tank2 and Tank3 belong to another scangroup. This should
   normally execute in a control system, but may execute in the same operator
   station as RecipeManager and ProcessManager. The address is specified as
   the initial value of the component Slc1Name in the datatype SysListType.
   
   Tank4, Tank5 and Tank6 belong to a third scangroup. The address is specified as
   the initial value of the component Slc2Name in the datatype SysListType.
   
   The initial values of the components OpName, Slc1Name and Slc2Name
   must be changed to appropriate values. Otherwise it is not possible to run
   the program.
   
   Set a initial value to the variable RecipeRevServer in BasePicture to activate the
   revision handling of recipes and operation recipes.
   
   The program uses "program external communication" services. Therefore,
   it will not work properly in "simulate" mode. "Run" mode must thus be used
   even if all scangroups execute in the same operator station.
   
   The program also contains an MmsDiagnostics module. This should be used
   to specify the cycle time of the "Picture string" communication to
   e.g. 2000 ms. If the "Picture string" communication is too slow it will be
   almost impossible to edit control operation recipes, which are downloaded
   to a control system. A alternative is to set the system variable
   "EnableStringTransfer".
   
   There are five different privileges for interaction. These may be switched
   on and off via the interaction buttons at the bottom of the picture.
   
   During the execution of a batch the operator's interation will be logged
   in a journal, with a name equal to the BatchID, specified when the control
   recipe is created in ProcessManager. The contents of the journal may be
   inspected via the JouListEventLog module.
   
   
   Running the demo program.
   -------------------------
   
   Master recipes may be created, edited, documented and saved in the RecipeManager.
   The main recipe and the operation recipe are treated separately. The
   system and the directory, where the recipes are saved, are specified to the
   right of the ProcessManager.
   
   The RecipeManager executes in a "Prog" scangroup. This means that different
   recipes may for instance be edited simultaneously in different workstations.
   Observe, however, that there is no facility for reservation of recipes. This
   means that the same recipe may be edited simultaneously by two different
   operators at two different workstations. The last one to save overwrites
   the other.
   
   A batch may be started in two different ways, from the ProcessManager or
   from a unit.
   
   o Starting and running the batch from the ProcessManager.
   
   Selection of the ProcessManager displays a window with four rows. The rows are
   BatchManager modules. Select a BatchManager and enter the BatchId, master
   recipe and control recipe name. Select the RecipeEditor to the left in the
   BatchManager row.
   
   Select an operation by entering its name at the top of the editor window.
   Then select the "Allocate unit" button. A unit will then be allocated
   according to the equipment requirements in the recipe. If the recipe is
   configured to start automatically it will do so. Otherwise the
   "Start operation" button has to be selected.
   
   The execution of the recipe may now be supervised from the editor window.
   The colours of the different operations indicate the states of the operations.
   
   Other operations in the recipe may be started in the same way while the
   recipe is running. In fact, any operation may be started at any time by
   the operator. This gives a lot of flexibility, but it also requires a lot
   of care.
   
   When the recipe has finished executing "Terminate batch" and then
   "Cancel recipe" should be selected in the BatchManager.
   
   The main recipe can be edited during the execution of the batch. To do so
   select "Inhibit allocation" in the editor window. The "Inhibit allocation"
   command is then distributed to all units currently involved in the batch.
   When a confirmation has been received from the units it is possible to
   edit the part of the recipe that has not already executed.
   
   The modifications of the recipe are distributed to the units when
   "Allow allocation" is selected or when the editor window is deleted.
   
   Observe that no new units are allocated when allocation is inhibited,
   but the operation recipes continue to execute. This means that the
   alocation points, i.e. the specified allocation phase and phase state,
   may be passed. In such a case the operator must start the allocation
   manually. This is done from the pop-up window of the unit.
   
   o Starting and running the batch from the units.
   
   Recipes may alternatively be started and run from the units. In such a
   case pop up the window of the unit and enter the master recipe, the
   control recipe name and the batch id and select "Execute". When the
   recipe is received activate the desired operation. The corresponding
   operation recipe will then be requested. It will also be started if
   the parameter "Autostart" of the recipe is true.
   
   The execution of the operation recipe may be supervised from the
   operation recipe editor of the unit. This editor may also be used to
   edit the running operation recipe. To do so manual mode must first
   be selected for the operation recipe.
   
   The succeeding operations to be allocated are shown in the window of
   the unit. If "Auto allocation" is specified in the recipe the
   allocation will start when the point of allocation, i.e. the
   allocation phase and phase state, is reached. The allocation may,
   however, be started earlier or be ommitted, if the operator selects the
   the start or stop button to the right of the name of the operation.
   
   When allocation has started the operator may pop up the window of the
   allocator and supervise or interfer with the automatic allocation.
   The allocator window is reached via the symbol to the right of the
   button for omitting the allocation.
   
   If the automatic allocation fails for some reason the operator may
   allocate a unit manually from the allocator window.
   
   o Starting and running an independant operation recipe.
   
   An operation recipe may be run as an autonomous recipe without a
   main recipe. It may be started and subervised from the ProcessManager
   or from the unit.
   
   To start an operation recipe from the ProcessManager display the window
   with the six units. Then display the parameter window for the seleceted
   unit and enter the master recipe, the control recipe name and the
   batch id and select "Execute". Then select "Send" from the control window
   and, when the operation recipe is present in the unit, select "Start".
   
   The operation recipe may be started analogously from the window of the unit. 
*)
 Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0 
    IgnoreMaxModule ) : MODULEDEFINITION DateCode_ 544742943 ( GroupConn = 
ProgStationData.GroupProgFast ) 
TYPEDEFINITIONS
   SystListType = RECORD DateCode_ 139204234
      OpName """X""": string Const := "X";
      Slc1Name """Y""": string Const := "Y";
      Slc2Name """Z""": string Const := "Z";
   ENDDEF
    (*SystListType*);
   
   TestProcManType = RECORD DateCode_ 627226725
      BatchControl1: BatchControlType ;
      BatchStatus1: BatchStatusType ;
      BatchControl2: BatchControlType ;
      BatchStatus2: BatchStatusType ;
      BatchControl3: BatchControlType ;
      BatchStatus3: BatchStatusType ;
      BatchControl4: BatchControlType ;
      BatchStatus4: BatchStatusType ;
      BatchControl5: BatchControlType ;
      BatchStatus5: BatchStatusType ;
      BatchControl6: BatchControlType ;
      BatchStatus6: BatchStatusType ;
      OperationControl1: OperationControlType ;
      OperationStatus1: OperationStatusType ;
      OperationControl2: OperationControlType ;
      OperationStatus2: OperationStatusType ;
      OperationControl3: OperationControlType ;
      OperationStatus3: OperationStatusType ;
      OperationControl4: OperationControlType ;
      OperationStatus4: OperationStatusType ;
      OperationControl5: OperationControlType ;
      OperationStatus5: OperationStatusType ;
      OperationControl6: OperationControlType ;
      OperationStatus6: OperationStatusType ;
   ENDDEF
    (*TestProcManType*);
   
TYPEDEFINITIONS
   SLC = MODULEDEFINITION DateCode_ 430773634 ( GroupConn = ScanGroup ) 
   MODULEPARAMETERS
      Unit1Name: string  := "Unit1";
      Unit2Name: string  := "Unit2";
      Unit3Name: string  := "Unit3";
      SlcName, JournalSystem: string ;
      ProcessManagerNumber: integer ;
      ScanGroup: GroupData  := Default;
      EnableInteraction, EnableEdit, EnableEditRestricted, EnableControl: 
      boolean ;
   SUBMODULES
      Unit1 Invocation
         ( 0.21667 , 0.30222 , 0.0 , 0.13889 , 0.13889 
          ) : Tank (
      UnitName => Unit1Name, 
      JournalSystem => JournalSystem, 
      ProcessManagerNumber => ProcessManagerNumber, 
      EnableControl => EnableControl, 
      EnableEdit => EnableEdit, 
      EnableEditRestricted => EnableEditRestricted);
      
      Unit2 Invocation
         ( 0.55667 , 0.30222 , 0.0 , 0.13889 , 0.13889 
          ) : Tank (
      UnitName => Unit2Name, 
      JournalSystem => JournalSystem, 
      ProcessManagerNumber => ProcessManagerNumber, 
      EnableControl => EnableControl, 
      EnableEdit => EnableEdit, 
      EnableEditRestricted => EnableEditRestricted);
      
      Unit3 Invocation
         ( 0.89667 , 0.30222 , 0.0 , 0.13889 , 0.13889 
          ) : Tank (
      UnitName => Unit3Name, 
      JournalSystem => JournalSystem, 
      ProcessManagerNumber => ProcessManagerNumber, 
      EnableControl => EnableControl, 
      EnableEdit => EnableEdit, 
      EnableEditRestricted => EnableEditRestricted);
      
   
   ModuleDef
   ClippingBounds = ( 0.0 , 0.0 ) ( 1.1 , 0.7 )
   GraphObjects :
      TextObject ( 0.4 , 0.62 ) ( 0.7 , 0.68 ) 
         "SlcName" VarName Width_ = 5 : InVar_ 5  ValueFraction = 2  
         OutlineColour : Colour0 = -3 
      RectangleObject ( 1.86265E-08 , 1.86265E-08 ) 
         ( 1.1 , 0.7 ) 
         OutlineColour : Colour0 = -3 
      TextObject ( 0.08 , 0.46 ) ( 0.36 , 0.52 ) 
         "Unit1Name" VarName Width_ = 5 : InVar_ 5  ValueFraction = 2  
         OutlineColour : Colour0 = -3 
      TextObject ( 0.42 , 0.46 ) ( 0.7 , 0.52 ) 
         "Unit2Name" VarName Width_ = 5 : InVar_ 5  ValueFraction = 2  
         OutlineColour : Colour0 = -3 
      TextObject ( 0.76 , 0.46 ) ( 1.04 , 0.52 ) 
         "Unit3Name" VarName Width_ = 5 : InVar_ 5  ValueFraction = 2  
         OutlineColour : Colour0 = -3 
   
   ENDDEF (*SLC*);
   
   Heating
   (* 1. Function
      
      2. Relation to other modules
      
      3. Comments on connection list
      
      4. Operators interface
      4.1 Pop-up windows
      
      4.2 Logging of operator interaction
      
      4.3 Modules accessable through pathstring
      "ModuleName*SelectButton"
      "ModuleName*Info"
      
      5. Scangroups
      Inherit/ProgStationData.GroupProg
      
      6. Opsave and secure
      
      7. Advice for usage *)
    = MODULEDEFINITION DateCode_ 552011451
   MODULEPARAMETERS
      PhaseName "IN Module instance name": string  := "Phase name";
      UnitName "IN Unit name": string  := "UnitName";
      EnableEdit "IN Enable editing", EnableEditRestricted 
      "IN Enable restricted editing", EnableControl "IN Enable control": 
      boolean  := True;
      InteractionSeverity "IN interaction severity": integer  := 0;
      InteractionClass "IN interaction class": integer  := 1;
      Error "OUT": boolean  := Default;
   LOCALVARIABLES
      FormulaDisplay: Formula1DisplayType ;
      PhaseControl: PhaseControlType ;
      PhaseStatus: PhaseStatusType ;
      ScaleFactor: real ;
      UnitFound1, UnitFound2, UnitFound3, UnitFound4, UnitFound5, UnitFound6: 
      string ;
      Ready: boolean ;
      PrgStep, PrgStepOld: integer ;
      Started: boolean ;
      StartString: string  := "Starting";
      OperationString: string  := "Operating";
      PauseString: string  := "Pause";
      ContinueString: string  := "Continue";
      StopString: string  := "Stopping";
      DebugStatus: integer ;
      Init: boolean  := True;
      CounterInit "for test/demo purpose only": integer  := 10;
      Counter "for test/demo purpose only": integer ;
      Result: integer  := 1;
      AllocatorAtConnNo1, AllocatorAtConnNo2, AllocatorAtConnNo3, 
      AllocatorAtConnNo4, AllocatorAtConnNo5, AllocatorAtConnNo6: integer  := 
      -1;
      UnitCounter, AllocConnCounter: integer  := 1;
   SUBMODULES
      Icon Invocation
         ( -1.0 , -1.0 , 0.0 , 2.0 , 2.0 
          Layer_ = 1
          ) : PhaseIcon;
      
      Info Invocation
         ( -0.96 , 0.76 , 0.0 , 0.68 , 0.68 
          Layer_ = 2
          ) : MODULEDEFINITION DateCode_ 681181221 ( Frame_Module ) 
      
      
      ModuleDef
      ClippingBounds = ( 0.0 , -1.16 ) ( 2.0 , 0.0 )
      GraphObjects :
         RectangleObject ( 0.0 , -1.16 ) ( 2.0 , 0.0 ) 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.0 , -0.16 ) ( 2.0 , -0.02 ) 
            "PhaseName" VarName Width_ = 5 : InVar_ 5  ValueFraction = 3  
            OutlineColour : Colour0 = -3 
         CompositeObject 
         TextObject ( 0.02 , -0.66 ) ( 0.36 , -0.56 ) 
            "Mode" RightAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.36 , -0.66 ) ( 0.98 , -0.56 ) 
            "PhaseStatus.Mode" VarName Width_ = 5 : InVar_ 5  ValueFraction = 2  
            OutlineColour : Colour0 = -3 
         TextObject ( 0.02 , -0.96 ) ( 0.36 , -0.86 ) 
            "Error" RightAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.02 , -0.76 ) ( 0.36 , -0.66 ) 
            "Result" RightAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.02 , -0.86 ) ( 0.36 , -0.76 ) 
            "Delay" RightAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.98 , -0.66 ) ( 1.48 , -0.56 ) 
            "Phase state" RightAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 1.48 , -0.66 ) ( 1.62 , -0.56 ) 
            "PhaseStatus.PhaseState" VarName Width_ = 5 : InVar_ 5  
            ValueFraction = 2  LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.02 , -0.28 ) ( 0.7 , -0.18 ) 
            "RecipePhase:" RightAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.7 , -0.28 ) ( 1.98 , -0.18 ) 
            "PhaseControl.RecipePhase" VarName Width_ = 5  ValueFraction = 2  
            LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.6 , -0.86 ) ( 1.1 , -0.76 ) 
            "Found units:" LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.62 , -0.76 ) ( 1.12 , -0.66 ) 
            "Allocators:" RightAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.6 , -0.96 ) ( 1.3 , -0.86 ) 
            "UnitFound1" VarName Width_ = 5  ValueFraction = 2  LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 1.3 , -0.96 ) ( 2.0 , -0.86 ) 
            "UnitFound4" VarName Width_ = 5  ValueFraction = 2  LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.6 , -1.06 ) ( 1.3 , -0.96 ) 
            "UnitFound2" VarName Width_ = 5  ValueFraction = 2  LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.6 , -1.16 ) ( 1.3 , -1.06 ) 
            "UnitFound3" VarName Width_ = 5  ValueFraction = 2  LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 1.3 , -1.06 ) ( 2.0 , -0.96 ) 
            "UnitFound5" VarName Width_ = 5  ValueFraction = 2  LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 1.3 , -1.16 ) ( 2.0 , -1.06 ) 
            "UnitFound6" VarName Width_ = 5  ValueFraction = 2  LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 1.12 , -0.76 ) ( 1.26 , -0.66 ) 
            "AllocatorAtConnNo1" VarName Width_ = 5 : InVar_ 5  ValueFraction = 
            2  
            OutlineColour : Colour0 = -3 
         TextObject ( 1.26 , -0.76 ) ( 1.4 , -0.66 ) 
            "AllocatorAtConnNo2" VarName Width_ = 5 : InVar_ 5  ValueFraction = 
            2  
            OutlineColour : Colour0 = -3 
         TextObject ( 1.4 , -0.76 ) ( 1.54 , -0.66 ) 
            "AllocatorAtConnNo3" VarName Width_ = 5 : InVar_ 5  ValueFraction = 
            2  
            OutlineColour : Colour0 = -3 
         TextObject ( 1.54 , -0.76 ) ( 1.68 , -0.66 ) 
            "AllocatorAtConnNo4" VarName Width_ = 5 : InVar_ 5  ValueFraction = 
            2  
            OutlineColour : Colour0 = -3 
         TextObject ( 1.68 , -0.76 ) ( 1.82 , -0.66 ) 
            "AllocatorAtConnNo5" VarName Width_ = 5 : InVar_ 5  ValueFraction = 
            2  
            OutlineColour : Colour0 = -3 
         TextObject ( 1.82 , -0.76 ) ( 1.96 , -0.66 ) 
            "AllocatorAtConnNo6" VarName Width_ = 5 : InVar_ 5  ValueFraction = 
            2  
            OutlineColour : Colour0 = -3 
      InteractObjects :
         ComBut_ ( 0.36 , -0.96 ) ( 0.46 , -0.86 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "PhaseStatus.Error" ToggleAction
            Abs_ SetApp_
            
         TextBox_ ( 0.36 , -0.86 ) ( 0.6 , -0.76 ) 
            Int_Value
            Enable_ = True : InVar_ "EnableControl" Variable = 0 : OutVar_ 
            "CounterInit" OpMin = 0 : InVar_ 0 CenterAligned Abs_ Digits_
            
            FillColour : Colour0 = 9 Colour1 = -1 
         TextBox_ ( 0.36 , -0.76 ) ( 0.6 , -0.66 ) 
            Int_Value
            Enable_ = True : InVar_ "EnableControl" Variable = 0 : OutVar_ 
            "Result" OpMin = 0 : InVar_ 0 CenterAligned Abs_ Digits_
            
            FillColour : Colour0 = 9 Colour1 = -1 
      
      ENDDEF (*Info*);
      
      PhaseModes Invocation
         ( 0.52 , -0.8 , 0.0 , 0.12 , 0.12 
          Layer_ = 2
          ) : PhaseModes (
      UnitName => UnitName, 
      PhaseName => PhaseName, 
      PhaseStatus => PhaseStatus, 
      Ready => Ready, 
      PhaseControl => PhaseControl, 
      Formula => FormulaDisplay.Formula, 
      ScaleFactor => ScaleFactor);
      
      PhaseDisplay Invocation
         ( 0.24 , -0.8 , 0.0 , 0.12 , 0.12 
          Layer_ = 2
          ) : HeaterDisplay (
      FormulaDisplay => FormulaDisplay);
      
      Prog Invocation
         ( 0.64 , -0.64 , 0.0 , 0.32 , 0.32 
          Layer_ = 2
          ) : MODULEDEFINITION DateCode_ 681149108 ( GroupConn = 
      ProgStationData.GroupProg ) 
      MODULEPARAMETERS
         FormulaDisplay: Formula1DisplayType ;
         EnableEdit, EnableEditRestricted: boolean ;
         ProgStationData: ProgStationData ;
      
      
      ModuleDef
      ClippingBounds = ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
      GraphObjects :
         RectangleObject ( 3.72529E-08 , 0.0 ) ( 1.0 , 1.0 ) 
            OutlineColour : Colour0 = -3 Colour1 = -3 
      
      ModuleCode
      EQUATIONBLOCK Prog COORD 0.1, 0.1 OBJSIZE 0.8, 0.8 :
         FormulaDisplay.EnableEdit = EnableEdit;
         FormulaDisplay.EnableEditRestricted = EnableEditRestricted;
      
      ENDDEF (*Prog*) (
      FormulaDisplay => FormulaDisplay, 
      EnableEdit => EnableEdit, 
      EnableEditRestricted => EnableEditRestricted, 
      ProgStationData => GLOBAL ProgStationData);
      
   
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   Two_Layers_ LayerLimit_ = 0.95
   Zoomable
   GraphObjects :
      RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      TextObject ( -1.0 , 0.8 ) ( 1.0 , 0.96 ) 
         "PhaseName" VarName Width_ = 5 : InVar_ 5  ValueFraction = 2  
         Layer_ = 2
         OutlineColour : Colour0 = -3 
   InteractObjects :
      ProcedureInteract ( -0.8 , -0.8 ) ( 0.8 , 0.8 ) 
         ToggleWindow
         "" : InVar_ LitString "+Info" "" False : InVar_ True 0.0 : InVar_ 0.1 
         0.0 : InVar_ -0.1 0.0 : InVar_ 0.48 0.0 False 0 0 False 0 
         Layer_ = 1
         Variable = 0.0 
   
   ModuleCode
   EQUATIONBLOCK sys COORD 0.68, -0.92 OBJSIZE 0.26, 0.24
   Layer_ = 2 :
      (* Read and reset commands from UnitManager *);
      IF PhaseControl.Start THEN
         PhaseControl.Start = False;
         Counter = CounterInit;
         (* Check if the phase already has been started *);
         IF Started THEN
            Error = True;
            PrgStep = 900;
         ELSE
            Started = True;
            PrgStep = 200;
         ENDIF;
      ENDIF;
      IF PhaseControl.Continue THEN
         PhaseControl.Continue = False;
         PrgStep = 300;
      ENDIF;
      IF PhaseControl.Pause THEN
         PhaseControl.Pause = False;
         PrgStep = 500;
      ENDIF;
      IF PhaseControl.Stop THEN
         PhaseControl.Stop = False;
         PrgStep = 600;
      ENDIF;
      (* Idle *);
      IF PrgStep == 100 THEN
         PhaseStatus.PhaseState = 1;
         ClearString(UnitFound1);
         ClearString(UnitFound2);
         ClearString(UnitFound3);
         ClearString(UnitFound4);
         ClearString(UnitFound5);
         ClearString(UnitFound6);
         ClearString(PhaseControl.RecipePhase);
         AllocatorAtConnNo1 =  -1;
         AllocatorAtConnNo2 =  -1;
         AllocatorAtConnNo3 =  -1;
         AllocatorAtConnNo4 =  -1;
         AllocatorAtConnNo5 =  -1;
         AllocatorAtConnNo6 =  -1;
         UnitCounter = 1;
         AllocConnCounter = 1;
         (* Insert code for idle state *);
      ENDIF;
      (* Start *);
      IF PrgStep == 200 THEN
         PhaseStatus.PhaseState = 2;
         IF PrgStepOld <> 200 THEN
            CopyVariable(StartString, PhaseStatus.Mode, DebugStatus);
            PrgStepOld = 200;
         ENDIF;
         (* Insert code for startup procedure.
            End with PrgStep=400. *);
         Counter = Counter - 1;
         IF Counter <= 0 THEN
            Counter = CounterInit;
            PrgStep = 400;
         ENDIF;
      ENDIF;
      (* Continue *);
      IF PrgStep == 300 THEN
         PhaseStatus.PhaseState = 3;
         IF PrgStepOld <> 300 THEN
            CopyVariable(ContinueString, PhaseStatus.Mode, DebugStatus);
            PrgStepOld = 300;
         ENDIF;
         (* Insert code for continue procedure.
            End with PrgStep=400. *);
         PrgStep = 400;
      ENDIF;
      (* Operation *);
      IF PrgStep == 400 THEN
         PhaseStatus.PhaseState = 4;
         IF PrgStepOld <> 400 THEN
            CopyVariable(OperationString, PhaseStatus.Mode, DebugStatus);
            PrgStepOld = 400;
         ENDIF;
         (* Insert code for normal operation
            End with PrgStep=600 *);
         Counter = Counter - 1;
         IF Counter <= 0 THEN
            Counter = CounterInit;
            PrgStep = 600;
         ENDIF;
      ENDIF;
      (* Pause *);
      IF PrgStep == 500 THEN
         PhaseStatus.PhaseState = 5;
         IF PrgStepOld <> 500 THEN
            CopyVariable(PauseString, PhaseStatus.Mode, DebugStatus);
            PrgStepOld = 500;
         ENDIF;
         (* Insert code for pause *);
      ENDIF;
      (* Stop *);
      IF PrgStep == 600 THEN
         PhaseStatus.PhaseState = 6;
         IF PrgStepOld <> 600 THEN
            CopyVariable(StopString, PhaseStatus.Mode, DebugStatus);
            PrgStepOld = 600;
         ENDIF;
         (* Insert code for stopping
            If OK then End with PrgStep=700
            If Error then ? *);
         Counter = Counter - 1;
         PhaseStatus.Result = Result;
         IF Counter <= 0 THEN
            Counter = CounterInit;
            PrgStep = 700;
         ENDIF;
      ENDIF;
      (* Ready *);
      IF PrgStep == 700 THEN
         PhaseStatus.PhaseState = 7;
         Ready = True;
         Started = False;
         PrgStep = 100;
      ENDIF;
      (* Error *);
      IF PrgStep == 900 THEN
         PhaseStatus.PhaseState = 9;
         Error = True;
         PhaseStatus.Error = True;
         PrgStep = 600;
      ENDIF;
      IF PhaseControl.UnitFound.Execute THEN
         PhaseControl.UnitFound.Execute = False;
         IF UnitCounter == 1 THEN
            CopyVariable(PhaseControl.UnitFound.Name, UnitFound1, DebugStatus);
            UnitCounter = 2;
         ELSIF UnitCounter == 2 THEN
            CopyVariable(PhaseControl.UnitFound.Name, UnitFound2, DebugStatus);
            UnitCounter = 3;
         ELSIF UnitCounter == 3 THEN
            CopyVariable(PhaseControl.UnitFound.Name, UnitFound3, DebugStatus);
            UnitCounter = 4;
         ELSIF UnitCounter == 4 THEN
            CopyVariable(PhaseControl.UnitFound.Name, UnitFound4, DebugStatus);
            UnitCounter = 5;
         ELSIF UnitCounter == 5 THEN
            CopyVariable(PhaseControl.UnitFound.Name, UnitFound5, DebugStatus);
            UnitCounter = 6;
         ELSIF UnitCounter == 6 THEN
            CopyVariable(PhaseControl.UnitFound.Name, UnitFound6, DebugStatus);
            UnitCounter = 1;
         ENDIF;
      ENDIF;
      IF PhaseControl.AllocConnFound.Execute THEN
         PhaseControl.AllocConnFound.Execute = False;
         IF AllocConnCounter == 1 THEN
            AllocatorAtConnNo1 = PhaseControl.AllocConnFound.AllocatorAtConnNo;
            AllocConnCounter = 2;
         ELSIF AllocConnCounter == 2 THEN
            AllocatorAtConnNo2 = PhaseControl.AllocConnFound.AllocatorAtConnNo;
            AllocConnCounter = 3;
         ELSIF AllocConnCounter == 3 THEN
            AllocatorAtConnNo3 = PhaseControl.AllocConnFound.AllocatorAtConnNo;
            AllocConnCounter = 4;
         ELSIF AllocConnCounter == 4 THEN
            AllocatorAtConnNo4 = PhaseControl.AllocConnFound.AllocatorAtConnNo;
            AllocConnCounter = 5;
         ELSIF AllocConnCounter == 5 THEN
            AllocatorAtConnNo5 = PhaseControl.AllocConnFound.AllocatorAtConnNo;
            AllocConnCounter = 6;
         ELSIF AllocConnCounter == 6 THEN
            AllocatorAtConnNo6 = PhaseControl.AllocConnFound.AllocatorAtConnNo;
            AllocConnCounter = 1;
         ENDIF;
      ENDIF;
   
   ENDDEF (*Heating*);
   
   Agitation1
   (* 1. Function
      
      2. Relation to other modules
      
      3. Comments on connection list
      
      4. Operators interface
      4.1 Pop-up windows
      
      4.2 Logging of operator interaction
      
      4.3 Modules accessable through pathstring
      "ModuleName*SelectButton"
      "ModuleName*Info"
      
      5. Scangroups
      Inherit/ProgStationData.GroupProg
      
      6. Opsave and secure
      
      7. Advice for usage *)
    = MODULEDEFINITION DateCode_ 552993624
   MODULEPARAMETERS
      PhaseName "IN Module instance name": string  := "Phase name";
      UnitName "IN Unit name": string  := "UnitName";
      EnableEdit "IN Enable editing", EnableEditRestricted 
      "IN Enable restricted editing", EnableControl "IN Enable control": 
      boolean  := True;
      InteractionSeverity "IN interaction severity": integer  := 0;
      InteractionClass "IN interaction class": integer  := 1;
      Error "OUT": boolean  := Default;
   LOCALVARIABLES
      FormulaDisplay: Formula1DisplayType ;
      PhaseControl: PhaseControlType ;
      PhaseStatus: PhaseStatusType ;
      ScaleFactor: real ;
      UnitFound1, UnitFound2, UnitFound3, UnitFound4, UnitFound5, UnitFound6: 
      string ;
      Ready: boolean ;
      PrgStep, PrgStepOld: integer ;
      Started: boolean ;
      StartString: string  := "Starting";
      OperationString: string  := "Operating";
      PauseString: string  := "Pause";
      ContinueString: string  := "Continue";
      StopString: string  := "Stopping";
      DebugStatus: integer ;
      Init: boolean  := True;
      CounterInit "for test/demo purpose only": integer  := 10;
      Counter "for test/demo purpose only": integer ;
      Result: integer  := 1;
      AllocatorAtConnNo1, AllocatorAtConnNo2, AllocatorAtConnNo3, 
      AllocatorAtConnNo4, AllocatorAtConnNo5, AllocatorAtConnNo6: integer  := 
      -1;
      UnitCounter, AllocConnCounter: integer  := 1;
   SUBMODULES
      Icon Invocation
         ( -1.0 , -1.0 , 0.0 , 2.0 , 2.0 
          Layer_ = 1
          ) : PhaseIcon;
      
      Info Invocation
         ( -0.96 , 0.76 , 0.0 , 0.68 , 0.68 
          Layer_ = 2
          ) : MODULEDEFINITION DateCode_ 681200080 ( Frame_Module ) 
      
      
      ModuleDef
      ClippingBounds = ( 0.0 , -1.16 ) ( 2.0 , 0.0 )
      GraphObjects :
         RectangleObject ( 0.0 , -1.16 ) ( 2.0 , 0.0 ) 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.0 , -0.16 ) ( 2.0 , -0.02 ) 
            "PhaseName" VarName Width_ = 5 : InVar_ 5  ValueFraction = 3  
            OutlineColour : Colour0 = -3 
         CompositeObject 
         TextObject ( 0.02 , -0.66 ) ( 0.36 , -0.56 ) 
            "Mode" RightAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.36 , -0.66 ) ( 0.98 , -0.56 ) 
            "PhaseStatus.Mode" VarName Width_ = 5 : InVar_ 5  ValueFraction = 2  
            OutlineColour : Colour0 = -3 
         TextObject ( 0.02 , -0.96 ) ( 0.36 , -0.86 ) 
            "Error" RightAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.02 , -0.76 ) ( 0.36 , -0.66 ) 
            "Result" RightAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.02 , -0.86 ) ( 0.36 , -0.76 ) 
            "Delay" RightAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.98 , -0.66 ) ( 1.48 , -0.56 ) 
            "Phase state" RightAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 1.48 , -0.66 ) ( 1.62 , -0.56 ) 
            "PhaseStatus.PhaseState" VarName Width_ = 5 : InVar_ 5  
            ValueFraction = 2  LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.02 , -0.28 ) ( 0.7 , -0.18 ) 
            "RecipePhase:" RightAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.7 , -0.28 ) ( 1.98 , -0.18 ) 
            "PhaseControl.RecipePhase" VarName Width_ = 5  ValueFraction = 2  
            LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.6 , -0.86 ) ( 1.1 , -0.76 ) 
            "Found units:" LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.62 , -0.76 ) ( 1.12 , -0.66 ) 
            "Allocators:" RightAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.6 , -0.96 ) ( 1.3 , -0.86 ) 
            "UnitFound1" VarName Width_ = 5  ValueFraction = 2  LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 1.3 , -0.96 ) ( 2.0 , -0.86 ) 
            "UnitFound4" VarName Width_ = 5  ValueFraction = 2  LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.6 , -1.06 ) ( 1.3 , -0.96 ) 
            "UnitFound2" VarName Width_ = 5  ValueFraction = 2  LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.6 , -1.16 ) ( 1.3 , -1.06 ) 
            "UnitFound3" VarName Width_ = 5  ValueFraction = 2  LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 1.3 , -1.06 ) ( 2.0 , -0.96 ) 
            "UnitFound5" VarName Width_ = 5  ValueFraction = 2  LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 1.3 , -1.16 ) ( 2.0 , -1.06 ) 
            "UnitFound6" VarName Width_ = 5  ValueFraction = 2  LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 1.12 , -0.76 ) ( 1.26 , -0.66 ) 
            "AllocatorAtConnNo1" VarName Width_ = 5 : InVar_ 5  ValueFraction = 
            2  
            OutlineColour : Colour0 = -3 
         TextObject ( 1.26 , -0.76 ) ( 1.4 , -0.66 ) 
            "AllocatorAtConnNo2" VarName Width_ = 5 : InVar_ 5  ValueFraction = 
            2  
            OutlineColour : Colour0 = -3 
         TextObject ( 1.4 , -0.76 ) ( 1.54 , -0.66 ) 
            "AllocatorAtConnNo3" VarName Width_ = 5 : InVar_ 5  ValueFraction = 
            2  
            OutlineColour : Colour0 = -3 
         TextObject ( 1.54 , -0.76 ) ( 1.68 , -0.66 ) 
            "AllocatorAtConnNo4" VarName Width_ = 5 : InVar_ 5  ValueFraction = 
            2  
            OutlineColour : Colour0 = -3 
         TextObject ( 1.68 , -0.76 ) ( 1.82 , -0.66 ) 
            "AllocatorAtConnNo5" VarName Width_ = 5 : InVar_ 5  ValueFraction = 
            2  
            OutlineColour : Colour0 = -3 
         TextObject ( 1.82 , -0.76 ) ( 1.96 , -0.66 ) 
            "AllocatorAtConnNo6" VarName Width_ = 5 : InVar_ 5  ValueFraction = 
            2  
            OutlineColour : Colour0 = -3 
      InteractObjects :
         ComBut_ ( 0.36 , -0.96 ) ( 0.46 , -0.86 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "PhaseStatus.Error" ToggleAction
            Abs_ SetApp_
            
         TextBox_ ( 0.36 , -0.86 ) ( 0.6 , -0.76 ) 
            Int_Value
            Enable_ = True : InVar_ "EnableControl" Variable = 0 : OutVar_ 
            "CounterInit" OpMin = 0 : InVar_ 0 CenterAligned Abs_ Digits_
            
            FillColour : Colour0 = 9 Colour1 = -1 
         TextBox_ ( 0.36 , -0.76 ) ( 0.6 , -0.66 ) 
            Int_Value
            Enable_ = True : InVar_ "EnableControl" Variable = 0 : OutVar_ 
            "Result" OpMin = 0 : InVar_ 0 CenterAligned Abs_ Digits_
            
            FillColour : Colour0 = 9 Colour1 = -1 
      
      ENDDEF (*Info*);
      
      PhaseModes Invocation
         ( 0.56 , -0.8 , 0.0 , 0.12 , 0.12 
          Layer_ = 2
          ) : PhaseModes (
      UnitName => UnitName, 
      PhaseName => PhaseName, 
      PhaseStatus => PhaseStatus, 
      Ready => Ready, 
      PhaseControl => PhaseControl, 
      Formula => FormulaDisplay.Formula, 
      ScaleFactor => ScaleFactor);
      
      PhaseDisplay Invocation
         ( 0.28 , -0.8 , 0.0 , 0.12 , 0.12 
          Layer_ = 2
          ) : Agitation1Display (
      FormulaDisplay => FormulaDisplay);
      
      Prog Invocation
         ( 0.68 , -0.64 , 0.0 , 0.32 , 0.32 
          Layer_ = 2
          ) : MODULEDEFINITION DateCode_ 681204204 ( GroupConn = 
      ProgStationData.GroupProg ) 
      MODULEPARAMETERS
         FormulaDisplay: Formula1DisplayType ;
         EnableEdit, EnableEditRestricted: boolean ;
         ProgStationData: ProgStationData ;
      
      
      ModuleDef
      ClippingBounds = ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
      GraphObjects :
         RectangleObject ( 3.72529E-08 , 0.0 ) ( 1.0 , 1.0 ) 
            OutlineColour : Colour0 = -3 Colour1 = -3 
      
      ModuleCode
      EQUATIONBLOCK Prog COORD 0.1, 0.1 OBJSIZE 0.8, 0.8 :
         FormulaDisplay.EnableEdit = EnableEdit;
         FormulaDisplay.EnableEditRestricted = EnableEditRestricted;
      
      ENDDEF (*Prog*) (
      FormulaDisplay => FormulaDisplay, 
      EnableEdit => EnableEdit, 
      EnableEditRestricted => EnableEditRestricted, 
      ProgStationData => GLOBAL ProgStationData);
      
   
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   Two_Layers_ LayerLimit_ = 0.95
   Zoomable
   GraphObjects :
      RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      TextObject ( -1.0 , 0.8 ) ( 1.0 , 0.96 ) 
         "PhaseName" VarName Width_ = 5 : InVar_ 5  ValueFraction = 2  
         Layer_ = 2
         OutlineColour : Colour0 = -3 
   InteractObjects :
      ProcedureInteract ( -0.8 , -0.8 ) ( 0.8 , 0.8 ) 
         ToggleWindow
         "" : InVar_ LitString "+Info" "" False : InVar_ True 0.0 : InVar_ 0.1 
         0.0 : InVar_ -0.1 0.0 : InVar_ 0.48 0.0 False 0 0 False 0 
         Layer_ = 1
         Variable = 0.0 
   
   ModuleCode
   EQUATIONBLOCK sys COORD 0.7, -0.92 OBJSIZE 0.26, 0.24
   Layer_ = 2 :
      (* Read and reset commands from UnitManager *);
      IF PhaseControl.Start THEN
         PhaseControl.Start = False;
         Counter = CounterInit;
         (* Check if the phase already has been started *);
         IF Started THEN
            Error = True;
            PrgStep = 900;
         ELSE
            Started = True;
            PrgStep = 200;
         ENDIF;
      ENDIF;
      IF PhaseControl.Continue THEN
         PhaseControl.Continue = False;
         PrgStep = 300;
      ENDIF;
      IF PhaseControl.Pause THEN
         PhaseControl.Pause = False;
         PrgStep = 500;
      ENDIF;
      IF PhaseControl.Stop THEN
         PhaseControl.Stop = False;
         PrgStep = 600;
      ENDIF;
      (* Idle *);
      IF PrgStep == 100 THEN
         PhaseStatus.PhaseState = 1;
         ClearString(UnitFound1);
         ClearString(UnitFound2);
         ClearString(UnitFound3);
         ClearString(UnitFound4);
         ClearString(UnitFound5);
         ClearString(UnitFound6);
         ClearString(PhaseControl.RecipePhase);
         AllocatorAtConnNo1 =  -1;
         AllocatorAtConnNo2 =  -1;
         AllocatorAtConnNo3 =  -1;
         AllocatorAtConnNo4 =  -1;
         AllocatorAtConnNo5 =  -1;
         AllocatorAtConnNo6 =  -1;
         UnitCounter = 1;
         AllocConnCounter = 1;
         (* Insert code for idle state *);
      ENDIF;
      (* Start *);
      IF PrgStep == 200 THEN
         PhaseStatus.PhaseState = 2;
         IF PrgStepOld <> 200 THEN
            CopyVariable(StartString, PhaseStatus.Mode, DebugStatus);
            PrgStepOld = 200;
         ENDIF;
         (* Insert code for startup procedure.
            End with PrgStep=400. *);
         Counter = Counter - 1;
         IF Counter <= 0 THEN
            Counter = CounterInit;
            PrgStep = 400;
         ENDIF;
      ENDIF;
      (* Continue *);
      IF PrgStep == 300 THEN
         PhaseStatus.PhaseState = 3;
         IF PrgStepOld <> 300 THEN
            CopyVariable(ContinueString, PhaseStatus.Mode, DebugStatus);
            PrgStepOld = 300;
         ENDIF;
         (* Insert code for continue procedure.
            End with PrgStep=400. *);
         PrgStep = 400;
      ENDIF;
      (* Operation *);
      IF PrgStep == 400 THEN
         PhaseStatus.PhaseState = 4;
         IF PrgStepOld <> 400 THEN
            CopyVariable(OperationString, PhaseStatus.Mode, DebugStatus);
            PrgStepOld = 400;
         ENDIF;
         (* Insert code for normal operation
            End with PrgStep=600 *);
         Counter = Counter - 1;
         IF Counter <= 0 THEN
            Counter = CounterInit;
            PrgStep = 600;
         ENDIF;
      ENDIF;
      (* Pause *);
      IF PrgStep == 500 THEN
         PhaseStatus.PhaseState = 5;
         IF PrgStepOld <> 500 THEN
            CopyVariable(PauseString, PhaseStatus.Mode, DebugStatus);
            PrgStepOld = 500;
         ENDIF;
         (* Insert code for pause *);
      ENDIF;
      (* Stop *);
      IF PrgStep == 600 THEN
         PhaseStatus.PhaseState = 6;
         IF PrgStepOld <> 600 THEN
            CopyVariable(StopString, PhaseStatus.Mode, DebugStatus);
            PrgStepOld = 600;
         ENDIF;
         (* Insert code for stopping
            If OK then End with PrgStep=700
            If Error then ? *);
         Counter = Counter - 1;
         PhaseStatus.Result = Result;
         IF Counter <= 0 THEN
            Counter = CounterInit;
            PrgStep = 700;
         ENDIF;
      ENDIF;
      (* Ready *);
      IF PrgStep == 700 THEN
         PhaseStatus.PhaseState = 7;
         Ready = True;
         Started = False;
         PrgStep = 100;
      ENDIF;
      (* Error *);
      IF PrgStep == 900 THEN
         PhaseStatus.PhaseState = 9;
         Error = True;
         PhaseStatus.Error = True;
         PrgStep = 600;
      ENDIF;
      IF PhaseControl.UnitFound.Execute THEN
         PhaseControl.UnitFound.Execute = False;
         IF UnitCounter == 1 THEN
            CopyVariable(PhaseControl.UnitFound.Name, UnitFound1, DebugStatus);
            UnitCounter = 2;
         ELSIF UnitCounter == 2 THEN
            CopyVariable(PhaseControl.UnitFound.Name, UnitFound2, DebugStatus);
            UnitCounter = 3;
         ELSIF UnitCounter == 3 THEN
            CopyVariable(PhaseControl.UnitFound.Name, UnitFound3, DebugStatus);
            UnitCounter = 4;
         ELSIF UnitCounter == 4 THEN
            CopyVariable(PhaseControl.UnitFound.Name, UnitFound4, DebugStatus);
            UnitCounter = 5;
         ELSIF UnitCounter == 5 THEN
            CopyVariable(PhaseControl.UnitFound.Name, UnitFound5, DebugStatus);
            UnitCounter = 6;
         ELSIF UnitCounter == 6 THEN
            CopyVariable(PhaseControl.UnitFound.Name, UnitFound6, DebugStatus);
            UnitCounter = 1;
         ENDIF;
      ENDIF;
      IF PhaseControl.AllocConnFound.Execute THEN
         PhaseControl.AllocConnFound.Execute = False;
         IF AllocConnCounter == 1 THEN
            AllocatorAtConnNo1 = PhaseControl.AllocConnFound.AllocatorAtConnNo;
            AllocConnCounter = 2;
         ELSIF AllocConnCounter == 2 THEN
            AllocatorAtConnNo2 = PhaseControl.AllocConnFound.AllocatorAtConnNo;
            AllocConnCounter = 3;
         ELSIF AllocConnCounter == 3 THEN
            AllocatorAtConnNo3 = PhaseControl.AllocConnFound.AllocatorAtConnNo;
            AllocConnCounter = 4;
         ELSIF AllocConnCounter == 4 THEN
            AllocatorAtConnNo4 = PhaseControl.AllocConnFound.AllocatorAtConnNo;
            AllocConnCounter = 5;
         ELSIF AllocConnCounter == 5 THEN
            AllocatorAtConnNo5 = PhaseControl.AllocConnFound.AllocatorAtConnNo;
            AllocConnCounter = 6;
         ELSIF AllocConnCounter == 6 THEN
            AllocatorAtConnNo6 = PhaseControl.AllocConnFound.AllocatorAtConnNo;
            AllocConnCounter = 1;
         ENDIF;
      ENDIF;
   
   ENDDEF (*Agitation1*);
   
   Agitation2
   (* 1. Function
      
      2. Relation to other modules
      
      3. Comments on connection list
      
      4. Operators interface
      4.1 Pop-up windows
      
      4.2 Logging of operator interaction
      
      4.3 Modules accessable through pathstring
      "ModuleName*SelectButton"
      "ModuleName*Info"
      
      5. Scangroups
      Inherit/ProgStationData.GroupProg
      
      6. Opsave and secure
      
      7. Advice for usage *)
    = MODULEDEFINITION DateCode_ 553838622
   MODULEPARAMETERS
      PhaseName "IN Module instance name": string  := "Phase name";
      UnitName "IN Unit name": string  := "UnitName";
      EnableEdit "IN Enable editing", EnableEditRestricted 
      "IN Enable restricted editing", EnableControl "IN Enable control": 
      boolean  := True;
      InteractionSeverity "IN interaction severity": integer  := 0;
      InteractionClass "IN interaction class": integer  := 1;
      Error "OUT": boolean  := Default;
   LOCALVARIABLES
      FormulaDisplay: Formula2DisplayType ;
      PhaseControl: PhaseControlType ;
      PhaseStatus: PhaseStatusType ;
      ScaleFactor: real ;
      UnitFound1, UnitFound2, UnitFound3, UnitFound4, UnitFound5, UnitFound6: 
      string ;
      Ready: boolean ;
      PrgStep, PrgStepOld: integer ;
      Started: boolean ;
      StartString: string  := "Starting";
      OperationString: string  := "Operating";
      PauseString: string  := "Pause";
      ContinueString: string  := "Continue";
      StopString: string  := "Stopping";
      DebugStatus: integer ;
      Init: boolean  := True;
      CounterInit "for test/demo purpose only": integer  := 10;
      Counter "for test/demo purpose only": integer ;
      Result: integer  := 1;
      AllocatorAtConnNo1, AllocatorAtConnNo2, AllocatorAtConnNo3, 
      AllocatorAtConnNo4, AllocatorAtConnNo5, AllocatorAtConnNo6: integer  := 
      -1;
      UnitCounter, AllocConnCounter: integer  := 1;
   SUBMODULES
      Icon Invocation
         ( -1.0 , -1.0 , 0.0 , 2.0 , 2.0 
          Layer_ = 1
          ) : PhaseIcon;
      
      Info Invocation
         ( -0.96 , 0.76 , 0.0 , 0.68 , 0.68 
          Layer_ = 2
          ) : MODULEDEFINITION DateCode_ 681202063 ( Frame_Module ) 
      
      
      ModuleDef
      ClippingBounds = ( 0.0 , -1.9 ) ( 2.0 , 0.0 )
      GraphObjects :
         RectangleObject ( 0.0 , -1.9 ) ( 2.0 , 0.0 ) 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.0 , -0.16 ) ( 2.0 , -0.02 ) 
            "PhaseName" VarName Width_ = 5 : InVar_ 5  ValueFraction = 3  
            OutlineColour : Colour0 = -3 
         CompositeObject 
         TextObject ( 0.0 , -1.4 ) ( 0.34 , -1.3 ) 
            "Mode" RightAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.34 , -1.4 ) ( 0.96 , -1.3 ) 
            "PhaseStatus.Mode" VarName Width_ = 5 : InVar_ 5  ValueFraction = 2  
            OutlineColour : Colour0 = -3 
         TextObject ( 0.0 , -1.7 ) ( 0.34 , -1.6 ) 
            "Error" RightAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.0 , -1.5 ) ( 0.34 , -1.4 ) 
            "Result" RightAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.0 , -1.6 ) ( 0.34 , -1.5 ) 
            "Delay" RightAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.96 , -1.4 ) ( 1.46 , -1.3 ) 
            "Phase state" RightAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 1.46 , -1.4 ) ( 1.6 , -1.3 ) 
            "PhaseStatus.PhaseState" VarName Width_ = 5 : InVar_ 5  
            ValueFraction = 2  LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.02 , -0.28 ) ( 0.7 , -0.18 ) 
            "RecipePhase:" RightAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.7 , -0.28 ) ( 1.98 , -0.18 ) 
            "PhaseControl.RecipePhase" VarName Width_ = 5  ValueFraction = 2  
            LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.6 , -1.6 ) ( 1.1 , -1.5 ) 
            "Found units:" LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.62 , -1.5 ) ( 1.12 , -1.4 ) 
            "Allocators:" RightAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.6 , -1.7 ) ( 1.3 , -1.6 ) 
            "UnitFound1" VarName Width_ = 5  ValueFraction = 2  LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 1.3 , -1.7 ) ( 2.0 , -1.6 ) 
            "UnitFound4" VarName Width_ = 5  ValueFraction = 2  LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.6 , -1.8 ) ( 1.3 , -1.7 ) 
            "UnitFound2" VarName Width_ = 5  ValueFraction = 2  LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.6 , -1.9 ) ( 1.3 , -1.8 ) 
            "UnitFound3" VarName Width_ = 5  ValueFraction = 2  LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 1.3 , -1.8 ) ( 2.0 , -1.7 ) 
            "UnitFound5" VarName Width_ = 5  ValueFraction = 2  LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 1.3 , -1.9 ) ( 2.0 , -1.8 ) 
            "UnitFound6" VarName Width_ = 5  ValueFraction = 2  LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 1.12 , -1.5 ) ( 1.26 , -1.4 ) 
            "AllocatorAtConnNo1" VarName Width_ = 5 : InVar_ 5  ValueFraction = 
            2  
            OutlineColour : Colour0 = -3 
         TextObject ( 1.26 , -1.5 ) ( 1.4 , -1.4 ) 
            "AllocatorAtConnNo2" VarName Width_ = 5 : InVar_ 5  ValueFraction = 
            2  
            OutlineColour : Colour0 = -3 
         TextObject ( 1.4 , -1.5 ) ( 1.54 , -1.4 ) 
            "AllocatorAtConnNo3" VarName Width_ = 5 : InVar_ 5  ValueFraction = 
            2  
            OutlineColour : Colour0 = -3 
         TextObject ( 1.54 , -1.5 ) ( 1.68 , -1.4 ) 
            "AllocatorAtConnNo4" VarName Width_ = 5 : InVar_ 5  ValueFraction = 
            2  
            OutlineColour : Colour0 = -3 
         TextObject ( 1.68 , -1.5 ) ( 1.82 , -1.4 ) 
            "AllocatorAtConnNo5" VarName Width_ = 5 : InVar_ 5  ValueFraction = 
            2  
            OutlineColour : Colour0 = -3 
         TextObject ( 1.82 , -1.5 ) ( 1.96 , -1.4 ) 
            "AllocatorAtConnNo6" VarName Width_ = 5 : InVar_ 5  ValueFraction = 
            2  
            OutlineColour : Colour0 = -3 
      InteractObjects :
         ComBut_ ( 0.34 , -1.7 ) ( 0.44 , -1.6 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "PhaseStatus.Error" ToggleAction
            Abs_ SetApp_
            
         TextBox_ ( 0.34 , -1.6 ) ( 0.58 , -1.5 ) 
            Int_Value
            Enable_ = True : InVar_ "EnableControl" Variable = 0 : OutVar_ 
            "CounterInit" OpMin = 0 : InVar_ 0 CenterAligned Abs_ Digits_
            
            FillColour : Colour0 = 9 Colour1 = -1 
         TextBox_ ( 0.34 , -1.5 ) ( 0.58 , -1.4 ) 
            Int_Value
            Enable_ = True : InVar_ "EnableControl" Variable = 0 : OutVar_ 
            "Result" OpMin = 0 : InVar_ 0 CenterAligned Abs_ Digits_
            
            FillColour : Colour0 = 9 Colour1 = -1 
      
      ENDDEF (*Info*);
      
      PhaseModes Invocation
         ( 0.52 , -0.8 , 0.0 , 0.12 , 0.12 
          Layer_ = 2
          ) : PhaseModes (
      UnitName => UnitName, 
      PhaseName => PhaseName, 
      PhaseStatus => PhaseStatus, 
      Ready => Ready, 
      PhaseControl => PhaseControl, 
      Formula => FormulaDisplay.Formula, 
      ScaleFactor => ScaleFactor);
      
      PhaseDisplay Invocation
         ( 0.24 , -0.8 , 0.0 , 0.12 , 0.12 
          Layer_ = 2
          ) : Agitation2Display (
      FormulaDisplay => FormulaDisplay);
      
      Prog Invocation
         ( 0.64 , -0.64 , 0.0 , 0.32 , 0.32 
          Layer_ = 2
          ) : MODULEDEFINITION DateCode_ 681239601 ( GroupConn = 
      ProgStationData.GroupProg ) 
      MODULEPARAMETERS
         FormulaDisplay: Formula2DisplayType ;
         EnableEdit, EnableEditRestricted: boolean ;
         ProgStationData: ProgStationData ;
      
      
      ModuleDef
      ClippingBounds = ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
      GraphObjects :
         RectangleObject ( 3.72529E-08 , 0.0 ) ( 1.0 , 1.0 ) 
            OutlineColour : Colour0 = -3 Colour1 = -3 
      
      ModuleCode
      EQUATIONBLOCK Prog COORD 0.1, 0.1 OBJSIZE 0.8, 0.8 :
         FormulaDisplay.EnableEdit = EnableEdit;
         FormulaDisplay.EnableEditRestricted = EnableEditRestricted;
      
      ENDDEF (*Prog*) (
      FormulaDisplay => FormulaDisplay, 
      EnableEdit => EnableEdit, 
      EnableEditRestricted => EnableEditRestricted, 
      ProgStationData => GLOBAL ProgStationData);
      
   
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   Two_Layers_ LayerLimit_ = 0.95
   Zoomable
   GraphObjects :
      RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      TextObject ( -1.0 , 0.8 ) ( 1.0 , 0.96 ) 
         "PhaseName" VarName Width_ = 5 : InVar_ 5  ValueFraction = 2  
         Layer_ = 2
         OutlineColour : Colour0 = -3 
   InteractObjects :
      ProcedureInteract ( -0.8 , -0.8 ) ( 0.8 , 0.8 ) 
         ToggleWindow
         "" : InVar_ LitString "+Info" "" False : InVar_ True 0.0 : InVar_ 0.1 
         0.0 : InVar_ -0.1 0.0 : InVar_ 0.48 0.0 False 0 0 False 0 
         Layer_ = 1
         Variable = 0.0 
   
   ModuleCode
   EQUATIONBLOCK sys COORD 0.68, -0.92 OBJSIZE 0.26, 0.24
   Layer_ = 2 :
      (* Read and reset commands from UnitManager *);
      IF PhaseControl.Start THEN
         PhaseControl.Start = False;
         Counter = CounterInit;
         (* Check if the phase already has been started *);
         IF Started THEN
            Error = True;
            PrgStep = 900;
         ELSE
            Started = True;
            PrgStep = 200;
         ENDIF;
      ENDIF;
      IF PhaseControl.Continue THEN
         PhaseControl.Continue = False;
         PrgStep = 300;
      ENDIF;
      IF PhaseControl.Pause THEN
         PhaseControl.Pause = False;
         PrgStep = 500;
      ENDIF;
      IF PhaseControl.Stop THEN
         PhaseControl.Stop = False;
         PrgStep = 600;
      ENDIF;
      (* Idle *);
      IF PrgStep == 100 THEN
         PhaseStatus.PhaseState = 1;
         ClearString(UnitFound1);
         ClearString(UnitFound2);
         ClearString(UnitFound3);
         ClearString(UnitFound4);
         ClearString(UnitFound5);
         ClearString(UnitFound6);
         ClearString(PhaseControl.RecipePhase);
         AllocatorAtConnNo1 =  -1;
         AllocatorAtConnNo2 =  -1;
         AllocatorAtConnNo3 =  -1;
         AllocatorAtConnNo4 =  -1;
         AllocatorAtConnNo5 =  -1;
         AllocatorAtConnNo6 =  -1;
         UnitCounter = 1;
         AllocConnCounter = 1;
         (* Insert code for idle state *);
      ENDIF;
      (* Start *);
      IF PrgStep == 200 THEN
         PhaseStatus.PhaseState = 2;
         IF PrgStepOld <> 200 THEN
            CopyVariable(StartString, PhaseStatus.Mode, DebugStatus);
            PrgStepOld = 200;
         ENDIF;
         (* Insert code for startup procedure.
            End with PrgStep=400. *);
         Counter = Counter - 1;
         IF Counter <= 0 THEN
            Counter = CounterInit;
            PrgStep = 400;
         ENDIF;
      ENDIF;
      (* Continue *);
      IF PrgStep == 300 THEN
         PhaseStatus.PhaseState = 3;
         IF PrgStepOld <> 300 THEN
            CopyVariable(ContinueString, PhaseStatus.Mode, DebugStatus);
            PrgStepOld = 300;
         ENDIF;
         (* Insert code for continue procedure.
            End with PrgStep=400. *);
         PrgStep = 400;
      ENDIF;
      (* Operation *);
      IF PrgStep == 400 THEN
         PhaseStatus.PhaseState = 4;
         IF PrgStepOld <> 400 THEN
            CopyVariable(OperationString, PhaseStatus.Mode, DebugStatus);
            PrgStepOld = 400;
         ENDIF;
         (* Insert code for normal operation
            End with PrgStep=600 *);
         Counter = Counter - 1;
         IF Counter <= 0 THEN
            Counter = CounterInit;
            PrgStep = 600;
         ENDIF;
      ENDIF;
      (* Pause *);
      IF PrgStep == 500 THEN
         PhaseStatus.PhaseState = 5;
         IF PrgStepOld <> 500 THEN
            CopyVariable(PauseString, PhaseStatus.Mode, DebugStatus);
            PrgStepOld = 500;
         ENDIF;
         (* Insert code for pause *);
      ENDIF;
      (* Stop *);
      IF PrgStep == 600 THEN
         PhaseStatus.PhaseState = 6;
         IF PrgStepOld <> 600 THEN
            CopyVariable(StopString, PhaseStatus.Mode, DebugStatus);
            PrgStepOld = 600;
         ENDIF;
         (* Insert code for stopping
            If OK then End with PrgStep=700
            If Error then ? *);
         Counter = Counter - 1;
         PhaseStatus.Result = Result;
         IF Counter <= 0 THEN
            Counter = CounterInit;
            PrgStep = 700;
         ENDIF;
      ENDIF;
      (* Ready *);
      IF PrgStep == 700 THEN
         PhaseStatus.PhaseState = 7;
         Ready = True;
         Started = False;
         PrgStep = 100;
      ENDIF;
      (* Error *);
      IF PrgStep == 900 THEN
         PhaseStatus.PhaseState = 9;
         Error = True;
         PhaseStatus.Error = True;
         PrgStep = 600;
      ENDIF;
      IF PhaseControl.UnitFound.Execute THEN
         PhaseControl.UnitFound.Execute = False;
         IF UnitCounter == 1 THEN
            CopyVariable(PhaseControl.UnitFound.Name, UnitFound1, DebugStatus);
            UnitCounter = 2;
         ELSIF UnitCounter == 2 THEN
            CopyVariable(PhaseControl.UnitFound.Name, UnitFound2, DebugStatus);
            UnitCounter = 3;
         ELSIF UnitCounter == 3 THEN
            CopyVariable(PhaseControl.UnitFound.Name, UnitFound3, DebugStatus);
            UnitCounter = 4;
         ELSIF UnitCounter == 4 THEN
            CopyVariable(PhaseControl.UnitFound.Name, UnitFound4, DebugStatus);
            UnitCounter = 5;
         ELSIF UnitCounter == 5 THEN
            CopyVariable(PhaseControl.UnitFound.Name, UnitFound5, DebugStatus);
            UnitCounter = 6;
         ELSIF UnitCounter == 6 THEN
            CopyVariable(PhaseControl.UnitFound.Name, UnitFound6, DebugStatus);
            UnitCounter = 1;
         ENDIF;
      ENDIF;
      IF PhaseControl.AllocConnFound.Execute THEN
         PhaseControl.AllocConnFound.Execute = False;
         IF AllocConnCounter == 1 THEN
            AllocatorAtConnNo1 = PhaseControl.AllocConnFound.AllocatorAtConnNo;
            AllocConnCounter = 2;
         ELSIF AllocConnCounter == 2 THEN
            AllocatorAtConnNo2 = PhaseControl.AllocConnFound.AllocatorAtConnNo;
            AllocConnCounter = 3;
         ELSIF AllocConnCounter == 3 THEN
            AllocatorAtConnNo3 = PhaseControl.AllocConnFound.AllocatorAtConnNo;
            AllocConnCounter = 4;
         ELSIF AllocConnCounter == 4 THEN
            AllocatorAtConnNo4 = PhaseControl.AllocConnFound.AllocatorAtConnNo;
            AllocConnCounter = 5;
         ELSIF AllocConnCounter == 5 THEN
            AllocatorAtConnNo5 = PhaseControl.AllocConnFound.AllocatorAtConnNo;
            AllocConnCounter = 6;
         ELSIF AllocConnCounter == 6 THEN
            AllocatorAtConnNo6 = PhaseControl.AllocConnFound.AllocatorAtConnNo;
            AllocConnCounter = 1;
         ENDIF;
      ENDIF;
   
   ENDDEF (*Agitation2*);
   
   Ramping
   (* 1. Function
      
      2. Relation to other modules
      
      3. Comments on connection list
      
      4. Operators interface
      4.1 Pop-up windows
      
      4.2 Logging of operator interaction
      
      4.3 Modules accessable through pathstring
      "ModuleName*SelectButton"
      "ModuleName*Info"
      
      5. Scangroups
      Inherit/ProgStationData.GroupProg
      
      6. Opsave and secure
      
      7. Advice for usage *)
    = MODULEDEFINITION DateCode_ 553337352
   MODULEPARAMETERS
      PhaseName "IN Module instance name": string  := "Phase name";
      UnitName "IN Unit name": string  := "UnitName";
      EnableEdit "IN Enable editing", EnableEditRestricted 
      "IN Enable restricted editing", EnableControl "IN Enable control": 
      boolean  := True;
      InteractionSeverity "IN interaction severity": integer  := 0;
      InteractionClass "IN interaction class": integer  := 1;
      Error "OUT": boolean  := Default;
   LOCALVARIABLES
      FormulaDisplay: Formula2DisplayType ;
      PhaseControl: PhaseControlType ;
      PhaseStatus: PhaseStatusType ;
      ScaleFactor: real ;
      UnitFound1, UnitFound2, UnitFound3, UnitFound4, UnitFound5, UnitFound6: 
      string ;
      Ready: boolean ;
      PrgStep, PrgStepOld: integer ;
      Started: boolean ;
      StartString: string  := "Starting";
      OperationString: string  := "Operating";
      PauseString: string  := "Pause";
      ContinueString: string  := "Continue";
      StopString: string  := "Stopping";
      DebugStatus: integer ;
      Init: boolean  := True;
      CounterInit "for test/demo purpose only": integer  := 10;
      Counter "for test/demo purpose only": integer ;
      Result: integer  := 1;
      AllocatorAtConnNo1, AllocatorAtConnNo2, AllocatorAtConnNo3, 
      AllocatorAtConnNo4, AllocatorAtConnNo5, AllocatorAtConnNo6: integer  := 
      -1;
      UnitCounter, AllocConnCounter: integer  := 1;
   SUBMODULES
      Icon Invocation
         ( -1.0 , -1.0 , 0.0 , 2.0 , 2.0 
          Layer_ = 1
          ) : PhaseIcon;
      
      Info Invocation
         ( -0.96 , 0.76 , 0.0 , 0.68 , 0.68 
          Layer_ = 2
          ) : MODULEDEFINITION DateCode_ 681340504 ( Frame_Module ) 
      
      
      ModuleDef
      ClippingBounds = ( 0.0 , -1.9 ) ( 2.0 , 0.0 )
      GraphObjects :
         RectangleObject ( 0.0 , -1.9 ) ( 2.0 , 0.0 ) 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.0 , -0.16 ) ( 2.0 , -0.02 ) 
            "PhaseName" VarName Width_ = 5 : InVar_ 5  ValueFraction = 3  
            OutlineColour : Colour0 = -3 
         CompositeObject 
         TextObject ( 0.02 , -1.4 ) ( 0.36 , -1.3 ) 
            "Mode" RightAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.36 , -1.4 ) ( 0.98 , -1.3 ) 
            "PhaseStatus.Mode" VarName Width_ = 5 : InVar_ 5  ValueFraction = 2  
            OutlineColour : Colour0 = -3 
         TextObject ( 0.02 , -1.7 ) ( 0.36 , -1.6 ) 
            "Error" RightAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.02 , -1.5 ) ( 0.36 , -1.4 ) 
            "Result" RightAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.02 , -1.6 ) ( 0.36 , -1.5 ) 
            "Delay" RightAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.98 , -1.4 ) ( 1.48 , -1.3 ) 
            "Phase state" RightAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 1.48 , -1.4 ) ( 1.62 , -1.3 ) 
            "PhaseStatus.PhaseState" VarName Width_ = 5 : InVar_ 5  
            ValueFraction = 2  LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.02 , -0.28 ) ( 0.7 , -0.18 ) 
            "RecipePhase:" RightAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.7 , -0.28 ) ( 1.98 , -0.18 ) 
            "PhaseControl.RecipePhase" VarName Width_ = 5  ValueFraction = 2  
            LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.6 , -1.6 ) ( 1.1 , -1.5 ) 
            "Found units:" LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.62 , -1.5 ) ( 1.12 , -1.4 ) 
            "Allocators:" RightAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.6 , -1.7 ) ( 1.3 , -1.6 ) 
            "UnitFound1" VarName Width_ = 5  ValueFraction = 2  LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 1.3 , -1.7 ) ( 2.0 , -1.6 ) 
            "UnitFound4" VarName Width_ = 5  ValueFraction = 2  LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.6 , -1.8 ) ( 1.3 , -1.7 ) 
            "UnitFound2" VarName Width_ = 5  ValueFraction = 2  LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.6 , -1.9 ) ( 1.3 , -1.8 ) 
            "UnitFound3" VarName Width_ = 5  ValueFraction = 2  LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 1.3 , -1.8 ) ( 2.0 , -1.7 ) 
            "UnitFound5" VarName Width_ = 5  ValueFraction = 2  LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 1.3 , -1.9 ) ( 2.0 , -1.8 ) 
            "UnitFound6" VarName Width_ = 5  ValueFraction = 2  LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 1.12 , -1.5 ) ( 1.26 , -1.4 ) 
            "AllocatorAtConnNo1" VarName Width_ = 5 : InVar_ 5  ValueFraction = 
            2  
            OutlineColour : Colour0 = -3 
         TextObject ( 1.26 , -1.5 ) ( 1.4 , -1.4 ) 
            "AllocatorAtConnNo2" VarName Width_ = 5 : InVar_ 5  ValueFraction = 
            2  
            OutlineColour : Colour0 = -3 
         TextObject ( 1.4 , -1.5 ) ( 1.54 , -1.4 ) 
            "AllocatorAtConnNo3" VarName Width_ = 5 : InVar_ 5  ValueFraction = 
            2  
            OutlineColour : Colour0 = -3 
         TextObject ( 1.54 , -1.5 ) ( 1.68 , -1.4 ) 
            "AllocatorAtConnNo4" VarName Width_ = 5 : InVar_ 5  ValueFraction = 
            2  
            OutlineColour : Colour0 = -3 
         TextObject ( 1.68 , -1.5 ) ( 1.82 , -1.4 ) 
            "AllocatorAtConnNo5" VarName Width_ = 5 : InVar_ 5  ValueFraction = 
            2  
            OutlineColour : Colour0 = -3 
         TextObject ( 1.82 , -1.5 ) ( 1.96 , -1.4 ) 
            "AllocatorAtConnNo6" VarName Width_ = 5 : InVar_ 5  ValueFraction = 
            2  
            OutlineColour : Colour0 = -3 
      InteractObjects :
         ComBut_ ( 0.36 , -1.7 ) ( 0.46 , -1.6 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "PhaseStatus.Error" ToggleAction
            Abs_ SetApp_
            
         TextBox_ ( 0.36 , -1.6 ) ( 0.6 , -1.5 ) 
            Int_Value
            Enable_ = True : InVar_ "EnableControl" Variable = 0 : OutVar_ 
            "CounterInit" OpMin = 0 : InVar_ 0 CenterAligned Abs_ Digits_
            
            FillColour : Colour0 = 9 Colour1 = -1 
         TextBox_ ( 0.36 , -1.5 ) ( 0.6 , -1.4 ) 
            Int_Value
            Enable_ = True : InVar_ "EnableControl" Variable = 0 : OutVar_ 
            "Result" OpMin = 0 : InVar_ 0 CenterAligned Abs_ Digits_
            
            FillColour : Colour0 = 9 Colour1 = -1 
      
      ENDDEF (*Info*);
      
      PhaseModes Invocation
         ( 0.52 , -0.8 , 0.0 , 0.12 , 0.12 
          Layer_ = 2
          ) : PhaseModes (
      UnitName => UnitName, 
      PhaseName => PhaseName, 
      PhaseStatus => PhaseStatus, 
      Ready => Ready, 
      PhaseControl => PhaseControl, 
      Formula => FormulaDisplay.Formula, 
      ScaleFactor => ScaleFactor);
      
      PhaseDisplay Invocation
         ( 0.24 , -0.8 , 0.0 , 0.12 , 0.12 
          Layer_ = 2
          ) : RampingDisplay (
      FormulaDisplay => FormulaDisplay);
      
      Prog Invocation
         ( 0.64 , -0.64 , 0.0 , 0.32 , 0.32 
          Layer_ = 2
          ) : MODULEDEFINITION DateCode_ 681314852 ( GroupConn = 
      ProgStationData.GroupProg ) 
      MODULEPARAMETERS
         FormulaDisplay: Formula2DisplayType ;
         EnableEdit, EnableEditRestricted: boolean ;
         ProgStationData: ProgStationData ;
      
      
      ModuleDef
      ClippingBounds = ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
      GraphObjects :
         RectangleObject ( 3.72529E-08 , 0.0 ) ( 1.0 , 1.0 ) 
            OutlineColour : Colour0 = -3 Colour1 = -3 
      
      ModuleCode
      EQUATIONBLOCK Prog COORD 0.1, 0.1 OBJSIZE 0.8, 0.8 :
         FormulaDisplay.EnableEdit = EnableEdit;
         FormulaDisplay.EnableEditRestricted = EnableEditRestricted;
      
      ENDDEF (*Prog*) (
      FormulaDisplay => FormulaDisplay, 
      EnableEdit => EnableEdit, 
      EnableEditRestricted => EnableEditRestricted, 
      ProgStationData => GLOBAL ProgStationData);
      
   
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   Two_Layers_ LayerLimit_ = 0.95
   Zoomable
   GraphObjects :
      RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      TextObject ( -1.0 , 0.8 ) ( 1.0 , 0.96 ) 
         "PhaseName" VarName Width_ = 5 : InVar_ 5  ValueFraction = 2  
         Layer_ = 2
         OutlineColour : Colour0 = -3 
   InteractObjects :
      ProcedureInteract ( -0.8 , -0.8 ) ( 0.8 , 0.8 ) 
         ToggleWindow
         "" : InVar_ LitString "+Info" "" False : InVar_ True 0.0 : InVar_ 0.1 
         0.0 : InVar_ -0.1 0.0 : InVar_ 0.48 0.0 False 0 0 False 0 
         Layer_ = 1
         Variable = 0.0 
   
   ModuleCode
   EQUATIONBLOCK sys COORD 0.68, -0.92 OBJSIZE 0.26, 0.24
   Layer_ = 2 :
      (* Read and reset commands from UnitManager *);
      IF PhaseControl.Start THEN
         PhaseControl.Start = False;
         Counter = CounterInit;
         (* Check if the phase already has been started *);
         IF Started THEN
            Error = True;
            PrgStep = 900;
         ELSE
            Started = True;
            PrgStep = 200;
         ENDIF;
      ENDIF;
      IF PhaseControl.Continue THEN
         PhaseControl.Continue = False;
         PrgStep = 300;
      ENDIF;
      IF PhaseControl.Pause THEN
         PhaseControl.Pause = False;
         PrgStep = 500;
      ENDIF;
      IF PhaseControl.Stop THEN
         PhaseControl.Stop = False;
         PrgStep = 600;
      ENDIF;
      (* Idle *);
      IF PrgStep == 100 THEN
         PhaseStatus.PhaseState = 1;
         ClearString(UnitFound1);
         ClearString(UnitFound2);
         ClearString(UnitFound3);
         ClearString(UnitFound4);
         ClearString(UnitFound5);
         ClearString(UnitFound6);
         ClearString(PhaseControl.RecipePhase);
         AllocatorAtConnNo1 =  -1;
         AllocatorAtConnNo2 =  -1;
         AllocatorAtConnNo3 =  -1;
         AllocatorAtConnNo4 =  -1;
         AllocatorAtConnNo5 =  -1;
         AllocatorAtConnNo6 =  -1;
         UnitCounter = 1;
         AllocConnCounter = 1;
         (* Insert code for idle state *);
      ENDIF;
      (* Start *);
      IF PrgStep == 200 THEN
         PhaseStatus.PhaseState = 2;
         IF PrgStepOld <> 200 THEN
            CopyVariable(StartString, PhaseStatus.Mode, DebugStatus);
            PrgStepOld = 200;
         ENDIF;
         (* Insert code for startup procedure.
            End with PrgStep=400. *);
         Counter = Counter - 1;
         IF Counter <= 0 THEN
            Counter = CounterInit;
            PrgStep = 400;
         ENDIF;
      ENDIF;
      (* Continue *);
      IF PrgStep == 300 THEN
         PhaseStatus.PhaseState = 3;
         IF PrgStepOld <> 300 THEN
            CopyVariable(ContinueString, PhaseStatus.Mode, DebugStatus);
            PrgStepOld = 300;
         ENDIF;
         (* Insert code for continue procedure.
            End with PrgStep=400. *);
         PrgStep = 400;
      ENDIF;
      (* Operation *);
      IF PrgStep == 400 THEN
         PhaseStatus.PhaseState = 4;
         IF PrgStepOld <> 400 THEN
            CopyVariable(OperationString, PhaseStatus.Mode, DebugStatus);
            PrgStepOld = 400;
         ENDIF;
         (* Insert code for normal operation
            End with PrgStep=600 *);
         Counter = Counter - 1;
         IF Counter <= 0 THEN
            Counter = CounterInit;
            PrgStep = 600;
         ENDIF;
      ENDIF;
      (* Pause *);
      IF PrgStep == 500 THEN
         PhaseStatus.PhaseState = 5;
         IF PrgStepOld <> 500 THEN
            CopyVariable(PauseString, PhaseStatus.Mode, DebugStatus);
            PrgStepOld = 500;
         ENDIF;
         (* Insert code for pause *);
      ENDIF;
      (* Stop *);
      IF PrgStep == 600 THEN
         PhaseStatus.PhaseState = 6;
         IF PrgStepOld <> 600 THEN
            CopyVariable(StopString, PhaseStatus.Mode, DebugStatus);
            PrgStepOld = 600;
         ENDIF;
         (* Insert code for stopping
            If OK then End with PrgStep=700
            If Error then ? *);
         Counter = Counter - 1;
         PhaseStatus.Result = Result;
         IF Counter <= 0 THEN
            Counter = CounterInit;
            PrgStep = 700;
         ENDIF;
      ENDIF;
      (* Ready *);
      IF PrgStep == 700 THEN
         PhaseStatus.PhaseState = 7;
         Ready = True;
         Started = False;
         PrgStep = 100;
      ENDIF;
      (* Error *);
      IF PrgStep == 900 THEN
         PhaseStatus.PhaseState = 9;
         Error = True;
         PhaseStatus.Error = True;
         PrgStep = 600;
      ENDIF;
      IF PhaseControl.UnitFound.Execute THEN
         PhaseControl.UnitFound.Execute = False;
         IF UnitCounter == 1 THEN
            CopyVariable(PhaseControl.UnitFound.Name, UnitFound1, DebugStatus);
            UnitCounter = 2;
         ELSIF UnitCounter == 2 THEN
            CopyVariable(PhaseControl.UnitFound.Name, UnitFound2, DebugStatus);
            UnitCounter = 3;
         ELSIF UnitCounter == 3 THEN
            CopyVariable(PhaseControl.UnitFound.Name, UnitFound3, DebugStatus);
            UnitCounter = 4;
         ELSIF UnitCounter == 4 THEN
            CopyVariable(PhaseControl.UnitFound.Name, UnitFound4, DebugStatus);
            UnitCounter = 5;
         ELSIF UnitCounter == 5 THEN
            CopyVariable(PhaseControl.UnitFound.Name, UnitFound5, DebugStatus);
            UnitCounter = 6;
         ELSIF UnitCounter == 6 THEN
            CopyVariable(PhaseControl.UnitFound.Name, UnitFound6, DebugStatus);
            UnitCounter = 1;
         ENDIF;
      ENDIF;
      IF PhaseControl.AllocConnFound.Execute THEN
         PhaseControl.AllocConnFound.Execute = False;
         IF AllocConnCounter == 1 THEN
            AllocatorAtConnNo1 = PhaseControl.AllocConnFound.AllocatorAtConnNo;
            AllocConnCounter = 2;
         ELSIF AllocConnCounter == 2 THEN
            AllocatorAtConnNo2 = PhaseControl.AllocConnFound.AllocatorAtConnNo;
            AllocConnCounter = 3;
         ELSIF AllocConnCounter == 3 THEN
            AllocatorAtConnNo3 = PhaseControl.AllocConnFound.AllocatorAtConnNo;
            AllocConnCounter = 4;
         ELSIF AllocConnCounter == 4 THEN
            AllocatorAtConnNo4 = PhaseControl.AllocConnFound.AllocatorAtConnNo;
            AllocConnCounter = 5;
         ELSIF AllocConnCounter == 5 THEN
            AllocatorAtConnNo5 = PhaseControl.AllocConnFound.AllocatorAtConnNo;
            AllocConnCounter = 6;
         ELSIF AllocConnCounter == 6 THEN
            AllocatorAtConnNo6 = PhaseControl.AllocConnFound.AllocatorAtConnNo;
            AllocConnCounter = 1;
         ENDIF;
      ENDIF;
   
   ENDDEF (*Ramping*);
   
   Filling
   (* 1. Function
      
      2. Relation to other modules
      
      3. Comments on connection list
      
      4. Operators interface
      4.1 Pop-up windows
      
      4.2 Logging of operator interaction
      
      4.3 Modules accessable through pathstring
      "ModuleName*SelectButton"
      "ModuleName*Info"
      
      5. Scangroups
      Inherit/ProgStationData.GroupProg
      
      6. Opsave and secure
      
      7. Advice for usage *)
    = MODULEDEFINITION DateCode_ 554426661
   MODULEPARAMETERS
      PhaseName "IN Module instance name": string  := "Phase name";
      UnitName "IN Unit name": string  := "UnitName";
      EnableEdit "IN Enable editing", EnableEditRestricted 
      "IN Enable restricted editing", EnableControl "IN Enable control": 
      boolean  := True;
      InteractionSeverity "IN interaction severity": integer  := 0;
      InteractionClass "IN interaction class": integer  := 1;
      Error "OUT": boolean  := Default;
   LOCALVARIABLES
      FormulaDisplay: Formula3DisplayType ;
      PhaseControl: PhaseControlType ;
      PhaseStatus: PhaseStatusType ;
      ScaleFactor: real ;
      UnitFound1, UnitFound2, UnitFound3, UnitFound4, UnitFound5, UnitFound6: 
      string ;
      Ready: boolean ;
      PrgStep, PrgStepOld: integer ;
      Started: boolean ;
      StartString: string  := "Starting";
      OperationString: string  := "Operating";
      PauseString: string  := "Pause";
      ContinueString: string  := "Continue";
      StopString: string  := "Stopping";
      DebugStatus: integer ;
      Init: boolean  := True;
      CounterInit "for test/demo purpose only": integer  := 10;
      Counter "for test/demo purpose only": integer ;
      Result: integer  := 1;
      AllocatorAtConnNo1, AllocatorAtConnNo2, AllocatorAtConnNo3, 
      AllocatorAtConnNo4, AllocatorAtConnNo5, AllocatorAtConnNo6: integer  := 
      -1;
      UnitCounter, AllocConnCounter: integer  := 1;
   SUBMODULES
      Icon Invocation
         ( -1.0 , -1.0 , 0.0 , 2.0 , 2.0 
          Layer_ = 1
          ) : PhaseIcon;
      
      Info Invocation
         ( -0.96 , 0.8 , 0.0 , 0.52 , 0.52 
          Layer_ = 2
          ) : MODULEDEFINITION DateCode_ 681319668 ( Frame_Module ) 
      
      
      ModuleDef
      ClippingBounds = ( 0.0 , -2.42 ) ( 2.0 , 0.0 )
      GraphObjects :
         RectangleObject ( 0.0 , -2.42 ) ( 2.0 , 0.0 ) 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.0 , -0.16 ) ( 2.0 , -0.02 ) 
            "PhaseName" VarName Width_ = 5 : InVar_ 5  ValueFraction = 3  
            OutlineColour : Colour0 = -3 
         CompositeObject 
         TextObject ( 0.02 , -1.92 ) ( 0.36 , -1.82 ) 
            "Mode" RightAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.36 , -1.92 ) ( 0.98 , -1.82 ) 
            "PhaseStatus.Mode" VarName Width_ = 5 : InVar_ 5  ValueFraction = 2  
            OutlineColour : Colour0 = -3 
         TextObject ( 0.02 , -2.22 ) ( 0.36 , -2.12 ) 
            "Error" RightAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.02 , -2.02 ) ( 0.36 , -1.92 ) 
            "Result" RightAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.98 , -1.92 ) ( 1.48 , -1.82 ) 
            "Phase state" RightAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 1.48 , -1.92 ) ( 1.62 , -1.82 ) 
            "PhaseStatus.PhaseState" VarName Width_ = 5 : InVar_ 5  
            ValueFraction = 2  LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.02 , -2.12 ) ( 0.36 , -2.02 ) 
            "Delay" RightAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.02 , -0.28 ) ( 0.7 , -0.18 ) 
            "RecipePhase:" RightAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.7 , -0.28 ) ( 1.98 , -0.18 ) 
            "PhaseControl.RecipePhase" VarName Width_ = 5  ValueFraction = 2  
            LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.6 , -2.12 ) ( 1.1 , -2.02 ) 
            "Found units:" LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.62 , -2.02 ) ( 1.12 , -1.92 ) 
            "Allocators:" RightAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.6 , -2.22 ) ( 1.3 , -2.12 ) 
            "UnitFound1" VarName Width_ = 5  ValueFraction = 2  LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 1.3 , -2.22 ) ( 2.0 , -2.12 ) 
            "UnitFound4" VarName Width_ = 5  ValueFraction = 2  LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.6 , -2.32 ) ( 1.3 , -2.22 ) 
            "UnitFound2" VarName Width_ = 5  ValueFraction = 2  LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.6 , -2.42 ) ( 1.3 , -2.32 ) 
            "UnitFound3" VarName Width_ = 5  ValueFraction = 2  LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 1.3 , -2.32 ) ( 2.0 , -2.22 ) 
            "UnitFound5" VarName Width_ = 5  ValueFraction = 2  LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 1.3 , -2.42 ) ( 2.0 , -2.32 ) 
            "UnitFound6" VarName Width_ = 5  ValueFraction = 2  LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 1.12 , -2.02 ) ( 1.26 , -1.92 ) 
            "AllocatorAtConnNo1" VarName Width_ = 5 : InVar_ 5  ValueFraction = 
            2  
            OutlineColour : Colour0 = -3 
         TextObject ( 1.26 , -2.02 ) ( 1.4 , -1.92 ) 
            "AllocatorAtConnNo2" VarName Width_ = 5 : InVar_ 5  ValueFraction = 
            2  
            OutlineColour : Colour0 = -3 
         TextObject ( 1.4 , -2.02 ) ( 1.54 , -1.92 ) 
            "AllocatorAtConnNo3" VarName Width_ = 5 : InVar_ 5  ValueFraction = 
            2  
            OutlineColour : Colour0 = -3 
         TextObject ( 1.54 , -2.02 ) ( 1.68 , -1.92 ) 
            "AllocatorAtConnNo4" VarName Width_ = 5 : InVar_ 5  ValueFraction = 
            2  
            OutlineColour : Colour0 = -3 
         TextObject ( 1.68 , -2.02 ) ( 1.82 , -1.92 ) 
            "AllocatorAtConnNo5" VarName Width_ = 5 : InVar_ 5  ValueFraction = 
            2  
            OutlineColour : Colour0 = -3 
         TextObject ( 1.82 , -2.02 ) ( 1.96 , -1.92 ) 
            "AllocatorAtConnNo6" VarName Width_ = 5 : InVar_ 5  ValueFraction = 
            2  
            OutlineColour : Colour0 = -3 
      InteractObjects :
         ComBut_ ( 0.36 , -2.22 ) ( 0.46 , -2.12 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "PhaseStatus.Error" ToggleAction
            Abs_ SetApp_
            
         TextBox_ ( 0.36 , -2.12 ) ( 0.6 , -2.02 ) 
            Int_Value
            Enable_ = True : InVar_ "EnableControl" Variable = 0 : OutVar_ 
            "CounterInit" OpMin = 0 : InVar_ 0 CenterAligned Abs_ Digits_
            
            FillColour : Colour0 = 9 Colour1 = -1 
         TextBox_ ( 0.36 , -2.02 ) ( 0.6 , -1.92 ) 
            Int_Value
            Enable_ = True : InVar_ "EnableControl" Variable = 0 : OutVar_ 
            "Result" OpMin = 0 : InVar_ 0 CenterAligned Abs_ Digits_
            
            FillColour : Colour0 = 9 Colour1 = -1 
      
      ENDDEF (*Info*);
      
      PhaseModes Invocation
         ( 0.52 , -0.8 , 0.0 , 0.12 , 0.12 
          Layer_ = 2
          ) : PhaseModes (
      UnitName => UnitName, 
      PhaseName => PhaseName, 
      PhaseStatus => PhaseStatus, 
      Ready => Ready, 
      PhaseControl => PhaseControl, 
      Formula => FormulaDisplay.Formula, 
      ScaleFactor => ScaleFactor);
      
      PhaseDisplay Invocation
         ( 0.24 , -0.8 , 0.0 , 0.12 , 0.12 
          Layer_ = 2
          ) : FillingDisplay (
      FormulaDisplay => FormulaDisplay);
      
      Prog Invocation
         ( 0.64 , -0.64 , 0.0 , 0.32 , 0.32 
          Layer_ = 2
          ) : MODULEDEFINITION DateCode_ 681321023 ( GroupConn = 
      ProgStationData.GroupProg ) 
      MODULEPARAMETERS
         FormulaDisplay: Formula3DisplayType ;
         EnableEdit, EnableEditRestricted: boolean ;
         ProgStationData: ProgStationData ;
      
      
      ModuleDef
      ClippingBounds = ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
      GraphObjects :
         RectangleObject ( 3.72529E-08 , 0.0 ) ( 1.0 , 1.0 ) 
            OutlineColour : Colour0 = -3 Colour1 = -3 
      
      ModuleCode
      EQUATIONBLOCK Prog COORD 0.1, 0.1 OBJSIZE 0.8, 0.8 :
         FormulaDisplay.EnableEdit = EnableEdit;
         FormulaDisplay.EnableEditRestricted = EnableEditRestricted;
      
      ENDDEF (*Prog*) (
      FormulaDisplay => FormulaDisplay, 
      EnableEdit => EnableEdit, 
      EnableEditRestricted => EnableEditRestricted, 
      ProgStationData => GLOBAL ProgStationData);
      
   
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   Two_Layers_ LayerLimit_ = 0.95
   Zoomable
   GraphObjects :
      RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      TextObject ( -1.0 , 0.8 ) ( 1.0 , 0.96 ) 
         "PhaseName" VarName Width_ = 5 : InVar_ 5  ValueFraction = 2  
         Layer_ = 2
         OutlineColour : Colour0 = -3 
   InteractObjects :
      ProcedureInteract ( -0.8 , -0.8 ) ( 0.8 , 0.8 ) 
         ToggleWindow
         "" : InVar_ LitString "+Info" "" False : InVar_ True 0.0 : InVar_ 0.1 
         0.0 : InVar_ -0.1 0.0 : InVar_ 0.48 0.0 False 0 0 False 0 
         Layer_ = 1
         Variable = 0.0 
   
   ModuleCode
   EQUATIONBLOCK sys COORD 0.68, -0.92 OBJSIZE 0.26, 0.24
   Layer_ = 2 :
      (* Read and reset commands from UnitManager *);
      IF PhaseControl.Start THEN
         PhaseControl.Start = False;
         Counter = CounterInit;
         (* Check if the phase already has been started *);
         IF Started THEN
            Error = True;
            PrgStep = 900;
         ELSE
            Started = True;
            PrgStep = 200;
         ENDIF;
      ENDIF;
      IF PhaseControl.Continue THEN
         PhaseControl.Continue = False;
         PrgStep = 300;
      ENDIF;
      IF PhaseControl.Pause THEN
         PhaseControl.Pause = False;
         PrgStep = 500;
      ENDIF;
      IF PhaseControl.Stop THEN
         PhaseControl.Stop = False;
         PrgStep = 600;
      ENDIF;
      (* Idle *);
      IF PrgStep == 100 THEN
         PhaseStatus.PhaseState = 1;
         ClearString(UnitFound1);
         ClearString(UnitFound2);
         ClearString(UnitFound3);
         ClearString(UnitFound4);
         ClearString(UnitFound5);
         ClearString(UnitFound6);
         ClearString(PhaseControl.RecipePhase);
         AllocatorAtConnNo1 =  -1;
         AllocatorAtConnNo2 =  -1;
         AllocatorAtConnNo3 =  -1;
         AllocatorAtConnNo4 =  -1;
         AllocatorAtConnNo5 =  -1;
         AllocatorAtConnNo6 =  -1;
         UnitCounter = 1;
         AllocConnCounter = 1;
         (* Insert code for idle state *);
      ENDIF;
      (* Start *);
      IF PrgStep == 200 THEN
         PhaseStatus.PhaseState = 2;
         IF PrgStepOld <> 200 THEN
            CopyVariable(StartString, PhaseStatus.Mode, DebugStatus);
            PrgStepOld = 200;
         ENDIF;
         (* Insert code for startup procedure.
            End with PrgStep=400. *);
         Counter = Counter - 1;
         IF Counter <= 0 THEN
            Counter = CounterInit;
            PrgStep = 400;
         ENDIF;
      ENDIF;
      (* Continue *);
      IF PrgStep == 300 THEN
         PhaseStatus.PhaseState = 3;
         IF PrgStepOld <> 300 THEN
            CopyVariable(ContinueString, PhaseStatus.Mode, DebugStatus);
            PrgStepOld = 300;
         ENDIF;
         (* Insert code for continue procedure.
            End with PrgStep=400. *);
         PrgStep = 400;
      ENDIF;
      (* Operation *);
      IF PrgStep == 400 THEN
         PhaseStatus.PhaseState = 4;
         IF PrgStepOld <> 400 THEN
            CopyVariable(OperationString, PhaseStatus.Mode, DebugStatus);
            PrgStepOld = 400;
         ENDIF;
         (* Insert code for normal operation
            End with PrgStep=600 *);
         Counter = Counter - 1;
         IF Counter <= 0 THEN
            Counter = CounterInit;
            PrgStep = 600;
         ENDIF;
      ENDIF;
      (* Pause *);
      IF PrgStep == 500 THEN
         PhaseStatus.PhaseState = 5;
         IF PrgStepOld <> 500 THEN
            CopyVariable(PauseString, PhaseStatus.Mode, DebugStatus);
            PrgStepOld = 500;
         ENDIF;
         (* Insert code for pause *);
      ENDIF;
      (* Stop *);
      IF PrgStep == 600 THEN
         PhaseStatus.PhaseState = 6;
         IF PrgStepOld <> 600 THEN
            CopyVariable(StopString, PhaseStatus.Mode, DebugStatus);
            PrgStepOld = 600;
         ENDIF;
         (* Insert code for stopping
            If OK then End with PrgStep=700
            If Error then ? *);
         Counter = Counter - 1;
         PhaseStatus.Result = Result;
         IF Counter <= 0 THEN
            Counter = CounterInit;
            PrgStep = 700;
         ENDIF;
      ENDIF;
      (* Ready *);
      IF PrgStep == 700 THEN
         PhaseStatus.PhaseState = 7;
         Ready = True;
         Started = False;
         PrgStep = 100;
      ENDIF;
      (* Error *);
      IF PrgStep == 900 THEN
         PhaseStatus.PhaseState = 9;
         Error = True;
         PhaseStatus.Error = True;
         PrgStep = 600;
      ENDIF;
      IF PhaseControl.UnitFound.Execute THEN
         PhaseControl.UnitFound.Execute = False;
         IF UnitCounter == 1 THEN
            CopyVariable(PhaseControl.UnitFound.Name, UnitFound1, DebugStatus);
            UnitCounter = 2;
         ELSIF UnitCounter == 2 THEN
            CopyVariable(PhaseControl.UnitFound.Name, UnitFound2, DebugStatus);
            UnitCounter = 3;
         ELSIF UnitCounter == 3 THEN
            CopyVariable(PhaseControl.UnitFound.Name, UnitFound3, DebugStatus);
            UnitCounter = 4;
         ELSIF UnitCounter == 4 THEN
            CopyVariable(PhaseControl.UnitFound.Name, UnitFound4, DebugStatus);
            UnitCounter = 5;
         ELSIF UnitCounter == 5 THEN
            CopyVariable(PhaseControl.UnitFound.Name, UnitFound5, DebugStatus);
            UnitCounter = 6;
         ELSIF UnitCounter == 6 THEN
            CopyVariable(PhaseControl.UnitFound.Name, UnitFound6, DebugStatus);
            UnitCounter = 1;
         ENDIF;
      ENDIF;
      IF PhaseControl.AllocConnFound.Execute THEN
         PhaseControl.AllocConnFound.Execute = False;
         IF AllocConnCounter == 1 THEN
            AllocatorAtConnNo1 = PhaseControl.AllocConnFound.AllocatorAtConnNo;
            AllocConnCounter = 2;
         ELSIF AllocConnCounter == 2 THEN
            AllocatorAtConnNo2 = PhaseControl.AllocConnFound.AllocatorAtConnNo;
            AllocConnCounter = 3;
         ELSIF AllocConnCounter == 3 THEN
            AllocatorAtConnNo3 = PhaseControl.AllocConnFound.AllocatorAtConnNo;
            AllocConnCounter = 4;
         ELSIF AllocConnCounter == 4 THEN
            AllocatorAtConnNo4 = PhaseControl.AllocConnFound.AllocatorAtConnNo;
            AllocConnCounter = 5;
         ELSIF AllocConnCounter == 5 THEN
            AllocatorAtConnNo5 = PhaseControl.AllocConnFound.AllocatorAtConnNo;
            AllocConnCounter = 6;
         ELSIF AllocConnCounter == 6 THEN
            AllocatorAtConnNo6 = PhaseControl.AllocConnFound.AllocatorAtConnNo;
            AllocConnCounter = 1;
         ENDIF;
      ENDIF;
   
   ENDDEF (*Filling*);
   
   Agitation1Display
   (* 1. Function
      
      2. Relation to other modules
      
      3. Comments on connection list
      
      4. Operators interface
      4.1 Pop-up windows
      
      4.2 Logging of operator interaction
      
      4.3 Modules accessable through pathstring
      "ModuleName*SelectButton"
      "ModuleName*Info"
      
      5. Scangroups
      Inherit/ProgStationData.GroupProg
      
      6. Opsave and secure
      
      7. Advice for usage *)
    = MODULEDEFINITION DateCode_ 385656579
   MODULEPARAMETERS
      FormulaDisplay "IN/OUT": Formula1DisplayType ;
      WarningColour "IN Warning colour": integer  := 9;
   LOCALVARIABLES
      PhaseName: string  := "Agitation1";
      ToggleWindow, DeleteWindow, Changed, ExecuteSelected: boolean ;
   SUBMODULES
      Icon Invocation
         ( -1.0 , -1.0 , 0.0 , 2.0 , 2.0 
          Layer_ = 1
          ZoomLimits = 0.5 0.01 ) : PhaseDisplayIcon;
      
      BatchWindowControl Invocation
         ( 0.72 , -0.78 , 0.0 , 0.12 , 0.12 
          Layer_ = 2
          ) : BatchWindowControl (
      ToggleWindow => ToggleWindow, 
      DeleteWindow => DeleteWindow, 
      WindowPath => "-+Page1+Info", 
      RelPos => True, 
      xSize => 0.24, 
      ProgStationData => GLOBAL ProgStationData);
      
      PhaseDisplayControl Invocation
         ( 0.42 , -0.78 , 0.0 , 0.12 , 0.12 
          Layer_ = 2
          ) : PhaseDisplayControl (
      String1 => PhaseName, 
      String2 => FormulaDisplay.PhaseName, 
      ExecuteToggle => FormulaDisplay.DisplayWindow, 
      Toggle => ToggleWindow, 
      ExecuteDelete => FormulaDisplay.DeleteWindow, 
      Delete => DeleteWindow, 
      Changed => Changed, 
      ExecuteSelected => ExecuteSelected, 
      ProgStationData => GLOBAL ProgStationData);
      
      Page1 Invocation
         ( -0.8 , -0.6 , 0.0 , 1.2 , 1.2 
          Layer_ = 2
          ) : MODULEDEFINITION DateCode_ 385375918 ( Frame_Module ) 
      SUBMODULES
         Info Invocation
            ( 0.1 , 1.0 , 0.0 , 0.5 , 0.5 
             ) : MODULEDEFINITION DateCode_ 385426853 ( Frame_Module ) 
         SUBMODULES
            Display Invocation
               ( 0.0 , -0.28 , 0.0 , 1.0 , 1.0 
                ) : MODULEDEFINITION DateCode_ 385426853 ( Frame_Module ) 
            SUBMODULES
               Speed Invocation
                  ( 0.48 , 0.0 , 0.0 , 0.48 , 0.1 
                   ) : BatchIntegerMenu (
               Value => FormulaDisplay.Formula.Int1, 
               Changed => Changed, 
               WarningColour => WarningColour, 
               InteractEnable => FormulaDisplay.EnableEditRestricted, 
               MaxValue => 65000, 
               MinValue => 0);
               
            
            ModuleDef
            ClippingBounds = ( 0.0 , 0.0 ) ( 1.0 , 0.1 )
            GraphObjects :
               TextObject ( 0.02 , 0.0 ) ( 0.52 , 0.1 ) 
                  "Speed:" LeftAligned 
                  OutlineColour : Colour0 = -3 Colour1 = 3 ColourStyle = False 
                  : ( NOT FormulaDisplay.EnableEditRestricted) 
            
            ENDDEF (*Display*);
            
            ExecuteOn Invocation
               ( 0.86 , -0.4 , 0.0 , 0.1 , 0.1 
                Enable_ = True : InVar_ "FormulaDisplay.EnableEditRestricted" ) 
            : BatchExecuteOn (
            Execute => FormulaDisplay.Changed, 
            Changed => ExecuteSelected);
            
         
         ModuleDef
         ClippingBounds = ( 0.0 , -0.42 ) ( 1.0 , 0.0 )
         GraphObjects :
            RectangleObject ( 0.0 , -7.07805E-08 ) 
               ( 1.0 , -0.42 ) 
               OutlineColour : Colour0 = -3 
               FillColour : Colour1 = 51 
            TextObject ( -1.49012E-08 , -0.16 ) ( 1.0 , 0.0 ) 
               "PhaseName" VarName Width_ = 5 : InVar_ 5  ValueFraction = 2  
               OutlineColour : Colour0 = -3 
         
         ENDDEF (*Info*);
         
      
      ModuleDef
      ClippingBounds = ( -2.98023E-08 , 0.0 ) ( 1.0 , 1.1 )
      
      ENDDEF (*Page1*);
      
   
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   Two_Layers_ LayerLimit_ = 0.95
   Zoomable
   GraphObjects :
      TextObject ( 0.1 , -0.06 ) ( 0.98 , 0.08 ) 
         "FormulaDisplay" 
         ConnectionNode ( 1.0 , 0.0 ) 
         
         OutlineColour : Colour0 = -3 
      RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
         Layer_ = 1
         OutlineColour : Colour0 = -3 
      TextObject ( -1.0 , 0.8 ) ( 1.0 , 0.96 ) 
         "PhaseName" VarName Width_ = 5 : InVar_ 5  ValueFraction = 2  
         Layer_ = 1
         OutlineColour : Colour0 = -3 
      RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = -2 
      RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      TextObject ( -1.0 , 0.8 ) ( 1.0 , 0.96 ) 
         "PhaseName" VarName Width_ = 5 : InVar_ 5  ValueFraction = 2  
         Layer_ = 2
         OutlineColour : Colour0 = -3 
   
   ENDDEF (*Agitation1Display*);
   
   HeaterDisplay
   (* 1. Function
      
      2. Relation to other modules
      
      3. Comments on connection list
      
      4. Operators interface
      4.1 Pop-up windows
      
      4.2 Logging of operator interaction
      
      4.3 Modules accessable through pathstring
      "ModuleName*SelectButton"
      "ModuleName*Info"
      
      5. Scangroups
      Inherit/ProgStationData.GroupProg
      
      6. Opsave and secure
      
      7. Advice for usage *)
    = MODULEDEFINITION DateCode_ 385981953
   MODULEPARAMETERS
      FormulaDisplay "IN/OUT": Formula1DisplayType ;
      WarningColour "IN Warning colour": integer  := 9;
   LOCALVARIABLES
      PhaseName: string  := "Heating";
      ToggleWindow, DeleteWindow, Changed, ExecuteSelected: boolean ;
   SUBMODULES
      Icon Invocation
         ( -1.0 , -1.0 , 0.0 , 2.0 , 2.0 
          Layer_ = 1
          ZoomLimits = 0.5 0.01 ) : PhaseDisplayIcon;
      
      BatchWindowControl Invocation
         ( 0.82 , -0.78 , 0.0 , 0.12 , 0.12 
          Layer_ = 2
          ) : BatchWindowControl (
      ToggleWindow => ToggleWindow, 
      DeleteWindow => DeleteWindow, 
      WindowPath => "-+Page1+Info", 
      RelPos => True, 
      xSize => 0.24, 
      ProgStationData => GLOBAL ProgStationData);
      
      PhaseDisplayControl Invocation
         ( 0.52 , -0.78 , 0.0 , 0.12 , 0.12 
          Layer_ = 2
          ) : PhaseDisplayControl (
      String1 => PhaseName, 
      String2 => FormulaDisplay.PhaseName, 
      ExecuteToggle => FormulaDisplay.DisplayWindow, 
      Toggle => ToggleWindow, 
      ExecuteDelete => FormulaDisplay.DeleteWindow, 
      Delete => DeleteWindow, 
      Changed => Changed, 
      ExecuteSelected => ExecuteSelected, 
      ProgStationData => GLOBAL ProgStationData);
      
      Page1 Invocation
         ( -0.8 , -0.6 , 0.0 , 1.2 , 1.2 
          Layer_ = 2
          ) : MODULEDEFINITION DateCode_ 385767904 ( Frame_Module ) 
      SUBMODULES
         Info Invocation
            ( 0.1 , 1.0 , 0.0 , 0.5 , 0.5 
             ) : MODULEDEFINITION DateCode_ 385809384 ( Frame_Module ) 
         SUBMODULES
            Display Invocation
               ( -2.98023E-08 , -0.28 , 0.0 , 1.0 , 1.0 
                ) : MODULEDEFINITION DateCode_ 385809384 ( Frame_Module ) 
            SUBMODULES
               Speed Invocation
                  ( 0.5 , 0.0 , 0.0 , 0.48 , 0.1 
                   ) : BatchIntegerMenu (
               Value => FormulaDisplay.Formula.Int1, 
               Changed => Changed, 
               WarningColour => WarningColour, 
               InteractEnable => FormulaDisplay.EnableEditRestricted, 
               MaxValue => 65000, 
               MinValue => 0);
               
            
            ModuleDef
            ClippingBounds = ( 0.0 , 0.0 ) ( 1.0 , 0.1 )
            GraphObjects :
               TextObject ( 0.02 , 0.0 ) ( 0.52 , 0.1 ) 
                  "Temperature:" LeftAligned 
                  OutlineColour : Colour0 = -3 Colour1 = 3 ColourStyle = False 
                  : ( NOT FormulaDisplay.EnableEditRestricted) 
            
            ENDDEF (*Display*);
            
            ExecutionOn Invocation
               ( 0.86 , -0.4 , 0.0 , 0.1 , 0.1 
                Enable_ = True : InVar_ "FormulaDisplay.EnableEditRestricted" ) 
            : BatchExecuteOn (
            Execute => FormulaDisplay.Changed, 
            Changed => ExecuteSelected);
            
         
         ModuleDef
         ClippingBounds = ( 0.0 , -0.4 ) ( 1.0 , 0.0 )
         GraphObjects :
            RectangleObject ( 0.0 , -7.07805E-08 ) 
               ( 1.0 , -0.4 ) 
               OutlineColour : Colour0 = -3 
               FillColour : Colour1 = 51 
            TextObject ( -1.49012E-08 , -0.16 ) ( 1.0 , 0.0 ) 
               "PhaseName" VarName Width_ = 5 : InVar_ 5  ValueFraction = 2  
               OutlineColour : Colour0 = -3 
         
         ENDDEF (*Info*);
         
      
      ModuleDef
      ClippingBounds = ( -2.98023E-08 , 0.0 ) ( 1.0 , 1.1 )
      
      ENDDEF (*Page1*);
      
   
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   Two_Layers_ LayerLimit_ = 0.95
   Zoomable
   GraphObjects :
      TextObject ( 0.04 , -0.06 ) ( 0.96 , 0.06 ) 
         "FormulaDisplay" 
         ConnectionNode ( 1.0 , 0.0 ) 
         
         OutlineColour : Colour0 = -3 
      RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
         Layer_ = 1
         OutlineColour : Colour0 = -3 
      TextObject ( -1.0 , 0.8 ) ( 1.0 , 0.96 ) 
         "PhaseName" VarName Width_ = 5 : InVar_ 5  ValueFraction = 2  
         Layer_ = 1
         OutlineColour : Colour0 = -3 
      RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = -2 
      RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      TextObject ( -1.0 , 0.8 ) ( 1.0 , 0.96 ) 
         "PhaseName" VarName Width_ = 5 : InVar_ 5  ValueFraction = 2  
         Layer_ = 2
         OutlineColour : Colour0 = -3 
   
   ENDDEF (*HeaterDisplay*);
   
   RampingDisplay
   (* 1. Function
      
      2. Relation to other modules
      
      3. Comments on connection list
      
      4. Operators interface
      4.1 Pop-up windows
      
      4.2 Logging of operator interaction
      
      4.3 Modules accessable through pathstring
      "ModuleName*SelectButton"
      "ModuleName*Info"
      
      5. Scangroups
      Inherit/ProgStationData.GroupProg
      
      6. Opsave and secure
      
      7. Advice for usage *)
    = MODULEDEFINITION DateCode_ 387190180
   MODULEPARAMETERS
      FormulaDisplay "IN/OUT": Formula2DisplayType ;
      WarningColour "IN Warning colour": integer  := 9;
   LOCALVARIABLES
      PhaseName: string  := "Ramping";
      ToggleWindow, DeleteWindow, Changed, ExecuteSelected: boolean ;
   SUBMODULES
      Icon Invocation
         ( -1.0 , -1.0 , 0.0 , 2.0 , 2.0 
          Layer_ = 1
          ZoomLimits = 0.5 0.01 ) : PhaseDisplayIcon;
      
      BatchWindowControl Invocation
         ( 0.82 , -0.78 , 0.0 , 0.12 , 0.12 
          Layer_ = 2
          ) : BatchWindowControl (
      ToggleWindow => ToggleWindow, 
      DeleteWindow => DeleteWindow, 
      WindowPath => "-+Page1+Info", 
      RelPos => True, 
      xSize => 0.48, 
      ProgStationData => GLOBAL ProgStationData);
      
      PhaseDisplayControl Invocation
         ( 0.52 , -0.78 , 0.0 , 0.12 , 0.12 
          Layer_ = 2
          ) : PhaseDisplayControl (
      String1 => PhaseName, 
      String2 => FormulaDisplay.PhaseName, 
      ExecuteToggle => FormulaDisplay.DisplayWindow, 
      Toggle => ToggleWindow, 
      ExecuteDelete => FormulaDisplay.DeleteWindow, 
      Delete => DeleteWindow, 
      Changed => Changed, 
      ExecuteSelected => ExecuteSelected, 
      ProgStationData => GLOBAL ProgStationData);
      
      Page1 Invocation
         ( -0.8 , -0.6 , 0.0 , 1.2 , 1.2 
          Layer_ = 2
          ) : MODULEDEFINITION DateCode_ 386968445 ( Frame_Module ) 
      SUBMODULES
         Info Invocation
            ( 0.1 , 1.0 , 0.0 , 0.4 , 0.4 
             ) : MODULEDEFINITION DateCode_ 387018160 ( Frame_Module ) 
         SUBMODULES
            Display Invocation
               ( 5.21541E-08 , -1.16 , 0.0 , 1.0 , 1.0 
                ) : MODULEDEFINITION DateCode_ 387018160 ( Frame_Module ) 
            SUBMODULES
               Time1 Invocation
                  ( 0.46 , 0.36 , 0.0 , 0.5 , 0.1 
                   ) : BatchIntegerMenu (
               Value => FormulaDisplay.Formula.Int1, 
               Changed => Changed, 
               WarningColour => WarningColour, 
               InteractEnable => FormulaDisplay.EnableEditRestricted, 
               MaxValue => 65000, 
               MinValue => 0);
               
               Time2 Invocation
                  ( 0.96 , 0.36 , 0.0 , 0.5 , 0.1 
                   ) : BatchIntegerMenu (
               Value => FormulaDisplay.Formula.Int2, 
               Changed => Changed, 
               WarningColour => WarningColour, 
               InteractEnable => FormulaDisplay.EnableEditRestricted, 
               MaxValue => 65000, 
               MinValue => 0);
               
               Time3 Invocation
                  ( 1.46 , 0.36 , 0.0 , 0.5 , 0.1 
                   ) : BatchIntegerMenu (
               Value => FormulaDisplay.Formula.Int3, 
               Changed => Changed, 
               WarningColour => WarningColour, 
               InteractEnable => FormulaDisplay.EnableEditRestricted, 
               MaxValue => 65000, 
               MinValue => 0);
               
               StopTemp Invocation
                  ( 0.04 , 0.82 , 0.0 , 0.48 , 0.1 
                   ) : BatchRealMenu (
               Value => FormulaDisplay.Formula.Real1, 
               Changed => Changed, 
               WarningColour => WarningColour, 
               InteractEnable => FormulaDisplay.EnableEditRestricted, 
               MaxValue => 65000.0, 
               MinValue => 0.0, 
               Fraction => 1);
               
               StartTemp Invocation
                  ( 0.04 , 0.52 , 0.0 , 0.48 , 0.1 
                   ) : BatchRealMenu (
               Value => FormulaDisplay.Formula.Real2, 
               Changed => Changed, 
               WarningColour => WarningColour, 
               InteractEnable => FormulaDisplay.EnableEditRestricted, 
               MaxValue => 65000.0, 
               MinValue => 0.0, 
               Fraction => 1);
               
               Gain Invocation
                  ( 0.4 , 0.1 , 0.0 , 0.5 , 0.1 
                   ) : BatchRealMenu (
               Value => FormulaDisplay.Formula.Real3, 
               Changed => Changed, 
               WarningColour => WarningColour, 
               InteractEnable => FormulaDisplay.EnableEditRestricted, 
               MaxValue => FormulaDisplay.Formula.Real5, 
               MinValue => FormulaDisplay.Formula.Real4, 
               Fraction => 1);
               
               Ti Invocation
                  ( 0.4 , -3.72529E-09 , 0.0 , 0.5 , 0.1 
                   ) : BatchRealMenu (
               Value => FormulaDisplay.Formula.Real6, 
               Changed => Changed, 
               WarningColour => WarningColour, 
               InteractEnable => FormulaDisplay.EnableEditRestricted, 
               MaxValue => FormulaDisplay.Formula.Real8, 
               MinValue => FormulaDisplay.Formula.Real7, 
               Fraction => 1);
               
               GainMin Invocation
                  ( 0.96 , 0.1 , 0.0 , 0.5 , 0.1 
                   ) : BatchRealMenu (
               Value => FormulaDisplay.Formula.Real4, 
               Changed => Changed, 
               WarningColour => WarningColour, 
               InteractEnable => FormulaDisplay.EnableEdit, 
               MaxValue => 65000.0, 
               MinValue => 0.0, 
               Fraction => 0);
               
               TiMin Invocation
                  ( 0.96 , -3.72529E-09 , 0.0 , 0.5 , 0.1 
                   ) : BatchRealMenu (
               Value => FormulaDisplay.Formula.Real7, 
               Changed => Changed, 
               WarningColour => WarningColour, 
               InteractEnable => FormulaDisplay.EnableEdit, 
               MaxValue => 65000.0, 
               MinValue => 0.0, 
               Fraction => 0);
               
               GainMax Invocation
                  ( 1.46 , 0.1 , 0.0 , 0.5 , 0.1 
                   ) : BatchRealMenu (
               Value => FormulaDisplay.Formula.Real5, 
               Changed => Changed, 
               WarningColour => WarningColour, 
               InteractEnable => FormulaDisplay.EnableEdit, 
               MaxValue => 65000.0, 
               MinValue => 0.0, 
               Fraction => 0);
               
               TiMax Invocation
                  ( 1.46 , -3.72529E-09 , 0.0 , 0.5 , 0.1 
                   ) : BatchRealMenu (
               Value => FormulaDisplay.Formula.Real8, 
               Changed => Changed, 
               WarningColour => WarningColour, 
               InteractEnable => FormulaDisplay.EnableEdit, 
               MaxValue => 65000.0, 
               MinValue => 0.0, 
               Fraction => 0);
               
            
            ModuleDef
            ClippingBounds = ( 0.0 , 0.0 ) ( 2.0 , 1.0 )
            GraphObjects :
               TextObject ( 0.02 , 0.1 ) ( 0.42 , 0.2 ) 
                  "PID Gain:" LeftAligned 
                  OutlineColour : Colour0 = -3 Colour1 = 3 ColourStyle = False 
                  : ( NOT FormulaDisplay.EnableEditRestricted) 
               TextObject ( 0.96 , 0.2 ) ( 1.46 , 0.3 ) 
                  "Min:" 
                  OutlineColour : Colour0 = -3 Colour1 = 3 ColourStyle = False 
                  : ( NOT FormulaDisplay.EnableEdit) 
               TextObject ( 1.46 , 0.2 ) ( 1.96 , 0.3 ) 
                  "Max:" 
                  OutlineColour : Colour0 = -3 Colour1 = 3 ColourStyle = False 
                  : ( NOT FormulaDisplay.EnableEdit) 
               TextObject ( 0.02 , -3.72529E-09 ) 
                  ( 0.42 , 0.1 ) 
                  "PID Ti:" LeftAligned 
                  OutlineColour : Colour0 = -3 Colour1 = 3 ColourStyle = False 
                  : ( NOT FormulaDisplay.EnableEditRestricted) 
               PolygonObject Polyline ( 0.56 , 0.58 ) 
                  ( 0.84 , 0.58 ) ( 1.22 , 0.8 ) 
                  ( 1.76 , 0.88 ) ( 1.98 , 0.88 ) 
                  OutlineColour : Colour0 = -3 
               PolygonObject Polyline ( 0.56 , 0.98 ) 
                  ( 0.56 , 0.5 ) ( 1.98 , 0.5 ) 
                  OutlineColour : Colour0 = -3 
            
            ENDDEF (*Display*);
            
            ExecuteOn Invocation
               ( 1.84 , -1.3 , 0.0 , 0.12 , 0.12 
                Enable_ = True : InVar_ "FormulaDisplay.EnableEditRestricted" ) 
            : BatchExecuteOn (
            Execute => FormulaDisplay.Changed, 
            Changed => ExecuteSelected);
            
         
         ModuleDef
         ClippingBounds = ( 0.0 , -1.3 ) ( 2.0 , 3.72529E-09 )
         GraphObjects :
            RectangleObject ( 0.0 , -8.19564E-08 ) 
               ( 2.0 , -1.3 ) 
               OutlineColour : Colour0 = -3 
               FillColour : Colour1 = 51 
            TextObject ( -1.49012E-08 , -0.16 ) ( 2.0 , 0.02 ) 
               "PhaseName" VarName Width_ = 5 : InVar_ 5  ValueFraction = 2  
               OutlineColour : Colour0 = -3 
         
         ENDDEF (*Info*);
         
      
      ModuleDef
      ClippingBounds = ( -2.98023E-08 , 0.0 ) ( 1.0 , 1.1 )
      
      ENDDEF (*Page1*);
      
   
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   Two_Layers_ LayerLimit_ = 0.95
   Zoomable
   GraphObjects :
      TextObject ( 0.08 , -0.06 ) ( 0.98 , 0.08 ) 
         "FormulaDisplay" 
         ConnectionNode ( 1.0 , 0.0 ) 
         
         OutlineColour : Colour0 = -3 
      RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
         Layer_ = 1
         OutlineColour : Colour0 = -3 
      TextObject ( -1.0 , 0.8 ) ( 1.0 , 0.96 ) 
         "PhaseName" VarName Width_ = 5 : InVar_ 5  ValueFraction = 2  
         Layer_ = 1
         OutlineColour : Colour0 = -3 
      RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = -2 
      RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      TextObject ( -1.0 , 0.8 ) ( 1.0 , 0.96 ) 
         "PhaseName" VarName Width_ = 5 : InVar_ 5  ValueFraction = 2  
         Layer_ = 2
         OutlineColour : Colour0 = -3 
   
   ENDDEF (*RampingDisplay*);
   
   Agitation2Display
   (* 1. Function
      
      2. Relation to other modules
      
      3. Comments on connection list
      
      4. Operators interface
      4.1 Pop-up windows
      
      4.2 Logging of operator interaction
      
      4.3 Modules accessable through pathstring
      "ModuleName*SelectButton"
      "ModuleName*Info"
      
      5. Scangroups
      Inherit/ProgStationData.GroupProg
      
      6. Opsave and secure
      
      7. Advice for usage *)
    = MODULEDEFINITION DateCode_ 386853765
   MODULEPARAMETERS
      FormulaDisplay "IN/OUT": Formula2DisplayType ;
      WarningColour "IN Warning colour": integer  := 9;
   LOCALVARIABLES
      PhaseName: string  := "Agitation2";
      ToggleWindow, DeleteWindow, Changed, ExecuteSelected: boolean ;
   SUBMODULES
      Icon Invocation
         ( -1.0 , -1.0 , 0.0 , 2.0 , 2.0 
          Layer_ = 1
          ZoomLimits = 0.5 0.01 ) : PhaseDisplayIcon;
      
      BatchWindowControl Invocation
         ( 0.82 , -0.78 , 0.0 , 0.12 , 0.12 
          Layer_ = 2
          ) : BatchWindowControl (
      ToggleWindow => ToggleWindow, 
      DeleteWindow => DeleteWindow, 
      WindowPath => "-+Page1+Info", 
      RelPos => True, 
      xSize => 0.48, 
      ProgStationData => GLOBAL ProgStationData);
      
      PhaseDisplayControl Invocation
         ( 0.52 , -0.78 , 0.0 , 0.12 , 0.12 
          Layer_ = 2
          ) : PhaseDisplayControl (
      String1 => PhaseName, 
      String2 => FormulaDisplay.PhaseName, 
      ExecuteToggle => FormulaDisplay.DisplayWindow, 
      Toggle => ToggleWindow, 
      ExecuteDelete => FormulaDisplay.DeleteWindow, 
      Delete => DeleteWindow, 
      Changed => Changed, 
      ExecuteSelected => ExecuteSelected, 
      ProgStationData => GLOBAL ProgStationData);
      
      Page1 Invocation
         ( -0.8 , -0.6 , 0.0 , 1.2 , 1.2 
          Layer_ = 2
          ) : MODULEDEFINITION DateCode_ 386552120 ( Frame_Module ) 
      SUBMODULES
         Info Invocation
            ( 0.05 , 1.04 , 0.0 , 0.44 , 0.44 
             ) : MODULEDEFINITION DateCode_ 386608057 ( Frame_Module ) 
         SUBMODULES
            Display Invocation
               ( 0.0 , -0.92 , 0.0 , 1.0 , 1.0 
                ) : MODULEDEFINITION DateCode_ 386608057 ( Frame_Module ) 
            SUBMODULES
               UpTime Invocation
                  ( 0.62 , 0.54 , 0.0 , 0.3 , 0.1 
                   ) : BatchIntegerMenu (
               Value => FormulaDisplay.Formula.Int1, 
               Changed => Changed, 
               WarningColour => WarningColour, 
               InteractEnable => FormulaDisplay.EnableEditRestricted, 
               MaxValue => 65000, 
               MinValue => 0);
               
               DownTime Invocation
                  ( 1.0 , 0.2 , 0.0 , 0.3 , 0.1 
                   ) : BatchIntegerMenu (
               Value => FormulaDisplay.Formula.Int2, 
               Changed => Changed, 
               WarningColour => WarningColour, 
               InteractEnable => FormulaDisplay.EnableEditRestricted, 
               MaxValue => 65000, 
               MinValue => 0);
               
               Direction Invocation
                  ( 0.46 , 0.04 , 0.0 , 0.4 , 0.1 
                   ) : BatchBooleanToggle (
               Value => FormulaDisplay.Formula.Bool1, 
               Changed => Changed, 
               WarningColour => WarningColour, 
               InteractEnable => FormulaDisplay.EnableEditRestricted);
               
               Speed Invocation
                  ( 0.14 , 0.46 , 0.0 , 0.28 , 0.1 
                   ) : BatchIntegerMenu (
               Value => FormulaDisplay.Formula.Int3, 
               Changed => Changed, 
               WarningColour => WarningColour, 
               InteractEnable => FormulaDisplay.EnableEditRestricted, 
               MaxValue => 65000, 
               MinValue => 0);
               
               Forward Invocation
                  ( 0.46 , 0.04 , 0.0 , 0.4 , 0.38 
                   Enable_ = True : InVar_ "FormulaDisplay.Formula.Bool1" ) : 
               MODULEDEFINITION DateCode_ 386608057
               
               
               ModuleDef
               ClippingBounds = ( 0.0 , 0.0 ) ( 1.0 , 0.25 )
               GraphObjects :
                  TextObject ( -1.49012E-07 , -2.98023E-07 ) 
                     ( 1.0 , 0.25 ) 
                     "Forward" 
                     OutlineColour : Colour0 = -3 
               
               ENDDEF (*Forward*);
               
               Reverse Invocation
                  ( 0.46 , 0.04 , 0.0 , 0.40111 , 0.38 
                   Enable_ = True : ( NOT FormulaDisplay.Formula.Bool1) ) : 
               MODULEDEFINITION DateCode_ 386608057
               
               
               ModuleDef
               ClippingBounds = ( 0.0 , 0.0 ) ( 1.0 , 0.25 )
               GraphObjects :
                  TextObject ( -1.11759E-07 , -5.96047E-07 ) 
                     ( 1.0 , 0.25 ) 
                     "Reverse" 
                     OutlineColour : Colour0 = -3 
               
               ENDDEF (*Reverse*);
               
            
            ModuleDef
            ClippingBounds = ( 0.0 , 0.0 ) ( 2.0 , 0.76 )
            GraphObjects :
               PolygonObject Polyline ( 0.46 , 0.62 ) 
                  ( 0.46 , 0.16 ) ( 1.86 , 0.16 ) 
                  OutlineColour : Colour0 = -3 
               PolygonObject Polyline ( 0.46 , 0.32 ) 
                  ( 0.64 , 0.32 ) ( 0.64 , 0.52 ) 
                  ( 0.92 , 0.52 ) ( 0.92 , 0.32 ) 
                  ( 1.4 , 0.32 ) ( 1.4 , 0.52 ) ( 1.68 , 0.52 ) 
                  ( 1.68 , 0.32 ) ( 1.84 , 0.32 ) 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.14 , 0.26 ) ( 0.42 , 0.36 ) 
                  "0" 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.16 , 0.62 ) ( 0.44 , 0.72 ) 
                  "R/min" 
                  OutlineColour : Colour0 = -3 
               TextObject ( 1.66 , 0.06 ) ( 1.86 , 0.16 ) 
                  "sec" 
                  OutlineColour : Colour0 = -3 
            
            ENDDEF (*Display*);
            
            Execute Invocation
               ( 1.88 , -1.0 , 0.0 , 0.1 , 0.1 
                Enable_ = True : InVar_ "FormulaDisplay.EnableEditRestricted" ) 
            : BatchExecuteOn (
            Execute => FormulaDisplay.Changed, 
            Changed => ExecuteSelected);
            
         
         ModuleDef
         ClippingBounds = ( 0.0 , -1.02 ) ( 2.0 , 0.0 )
         GraphObjects :
            RectangleObject ( 0.0 , -8.19564E-08 ) 
               ( 2.0 , -1.02 ) 
               OutlineColour : Colour0 = -3 
               FillColour : Colour1 = 51 
            TextObject ( -1.49012E-08 , -0.16 ) ( 2.0 , 0.02 ) 
               "PhaseName" VarName Width_ = 5 : InVar_ 5  ValueFraction = 2  
               OutlineColour : Colour0 = -3 
         
         ENDDEF (*Info*);
         
      
      ModuleDef
      ClippingBounds = ( -2.98023E-08 , 0.0 ) ( 1.0 , 1.1 )
      
      ENDDEF (*Page1*);
      
   
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   Two_Layers_ LayerLimit_ = 0.95
   Zoomable
   GraphObjects :
      TextObject ( 0.14 , -0.08 ) ( 0.94 , 0.06 ) 
         "FormulaDisplay" 
         ConnectionNode ( 1.0 , 0.0 ) 
         LeftAligned 
         OutlineColour : Colour0 = -3 
      RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
         Layer_ = 1
         OutlineColour : Colour0 = -3 
      TextObject ( -1.0 , 0.8 ) ( 1.0 , 0.96 ) 
         "PhaseName" VarName Width_ = 5 : InVar_ 5  ValueFraction = 2  
         Layer_ = 1
         OutlineColour : Colour0 = -3 
      RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = -2 
      RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      TextObject ( -1.0 , 0.8 ) ( 1.0 , 0.96 ) 
         "PhaseName" VarName Width_ = 5 : InVar_ 5  ValueFraction = 2  
         Layer_ = 2
         OutlineColour : Colour0 = -3 
   
   ENDDEF (*Agitation2Display*);
   
   FillingDisplay
   (* 1. Function
      
      2. Relation to other modules
      
      3. Comments on connection list
      
      4. Operators interface
      4.1 Pop-up windows
      
      4.2 Logging of operator interaction
      
      4.3 Modules accessable through pathstring
      "ModuleName*SelectButton"
      "ModuleName*Info"
      
      5. Scangroups
      Inherit/ProgStationData.GroupProg
      
      6. Opsave and secure
      
      7. Advice for usage *)
    = MODULEDEFINITION DateCode_ 387784076
   MODULEPARAMETERS
      FormulaDisplay "IN/OUT": Formula3DisplayType ;
      WarningColour "IN Warning colour": integer  := 9;
   LOCALVARIABLES
      PhaseName: string  := "Filling";
      ToggleWindow, DeleteWindow, Changed, ExecuteSelected: boolean ;
   SUBMODULES
      Icon Invocation
         ( -1.0 , -1.0 , 0.0 , 2.0 , 2.0 
          Layer_ = 1
          ZoomLimits = 0.5 0.01 ) : PhaseDisplayIcon;
      
      BatchWindowControl Invocation
         ( 0.82 , -0.78 , 0.0 , 0.12 , 0.12 
          Layer_ = 2
          ) : BatchWindowControl (
      ToggleWindow => ToggleWindow, 
      DeleteWindow => DeleteWindow, 
      WindowPath => "-+Page1+Info", 
      RelPos => True, 
      xSize => 0.36, 
      ProgStationData => GLOBAL ProgStationData);
      
      PhaseDisplayControl Invocation
         ( 0.52 , -0.78 , 0.0 , 0.12 , 0.12 
          Layer_ = 2
          ) : PhaseDisplayControl (
      String1 => PhaseName, 
      String2 => FormulaDisplay.PhaseName, 
      ExecuteToggle => FormulaDisplay.DisplayWindow, 
      Toggle => ToggleWindow, 
      ExecuteDelete => FormulaDisplay.DeleteWindow, 
      Delete => DeleteWindow, 
      Changed => Changed, 
      ExecuteSelected => ExecuteSelected, 
      ProgStationData => GLOBAL ProgStationData);
      
      Page1 Invocation
         ( -0.8 , -0.6 , 0.0 , 1.2 , 1.2 
          Layer_ = 2
          ) : MODULEDEFINITION DateCode_ 387491459 ( Frame_Module ) 
      SUBMODULES
         Info Invocation
            ( 0.1 , 1.0 , 0.0 , 0.46 , 0.46 
             ) : MODULEDEFINITION DateCode_ 387532146 ( Frame_Module ) 
         SUBMODULES
            Display Invocation
               ( 0.0 , -1.3 , 0.0 , 1.0 , 1.0 
                ) : MODULEDEFINITION DateCode_ 387532146 ( Frame_Module ) 
            SUBMODULES
               Time1 Invocation
                  ( 0.04 , 0.14 , 0.0 , 0.36 , 0.1 
                   ) : BatchIntegerMenu (
               Value => FormulaDisplay.Formula.Int1, 
               Changed => Changed, 
               WarningColour => WarningColour, 
               InteractEnable => FormulaDisplay.EnableEditRestricted, 
               MaxValue => 65000, 
               MinValue => 0);
               
               Time2 Invocation
                  ( 1.06 , 0.14 , 0.0 , 0.4 , 0.1 
                   ) : BatchIntegerMenu (
               Value => FormulaDisplay.Formula.Int2, 
               Changed => Changed, 
               WarningColour => WarningColour, 
               InteractEnable => FormulaDisplay.EnableEditRestricted, 
               MaxValue => 65000, 
               MinValue => 0);
               
               Coarse1 Invocation
                  ( 0.04 , 0.24 , 0.0 , 0.36 , 0.1 
                   ) : BatchRealMenu (
               Value => FormulaDisplay.Formula.Real1, 
               Changed => Changed, 
               WarningColour => WarningColour, 
               InteractEnable => FormulaDisplay.EnableEditRestricted, 
               MaxValue => 65000.0, 
               MinValue => 0.0, 
               Fraction => 1);
               
               Fine1 Invocation
                  ( 0.04 , 0.04 , 0.0 , 0.36 , 0.1 
                   ) : BatchRealMenu (
               Value => FormulaDisplay.Formula.Real3, 
               Changed => Changed, 
               WarningColour => WarningColour, 
               InteractEnable => FormulaDisplay.EnableEditRestricted, 
               MaxValue => 65000.0, 
               MinValue => 0.0, 
               Fraction => 1);
               
               Coarse2 Invocation
                  ( 1.06 , 0.24 , 0.0 , 0.4 , 0.1 
                   ) : BatchRealMenu (
               Value => FormulaDisplay.Formula.Real2, 
               Changed => Changed, 
               WarningColour => WarningColour, 
               InteractEnable => FormulaDisplay.EnableEditRestricted, 
               MaxValue => 65000.0, 
               MinValue => 0.0, 
               Fraction => 1);
               
               Fine2 Invocation
                  ( 1.06 , 0.04 , 0.0 , 0.4 , 0.1 
                   ) : BatchRealMenu (
               Value => FormulaDisplay.Formula.Real4, 
               Changed => Changed, 
               WarningColour => WarningColour, 
               InteractEnable => FormulaDisplay.EnableEditRestricted, 
               MaxValue => 65000.0, 
               MinValue => 0.0, 
               Fraction => 1);
               
               Product1 Invocation
                  ( 0.1 , 0.68 , 0.0 , 0.56 , 0.1 
                   ) : BatchStringMenu (
               Value => FormulaDisplay.Formula.String1, 
               Changed => Changed, 
               WarningColour => WarningColour, 
               InteractEnable => FormulaDisplay.EnableEditRestricted);
               
               Product2 Invocation
                  ( 0.82 , 0.68 , 0.0 , 0.56 , 0.1 
                   ) : BatchStringMenu (
               Value => FormulaDisplay.Formula.String2, 
               Changed => Changed, 
               WarningColour => WarningColour, 
               InteractEnable => FormulaDisplay.EnableEditRestricted);
               
               ParFill Invocation
                  ( 0.22 , 1.0 , 0.0 , 0.1 , 0.1 
                   ) : BatchBooleanToggle (
               Value => FormulaDisplay.Formula.Bool1, 
               Changed => Changed, 
               WarningColour => WarningColour, 
               InteractEnable => FormulaDisplay.EnableEditRestricted);
               
               Agitation Invocation
                  ( 0.22 , 0.9 , 0.0 , 0.1 , 0.1 
                   ) : BatchBooleanToggle (
               Value => FormulaDisplay.Formula.Bool2, 
               Changed => Changed, 
               WarningColour => WarningColour, 
               InteractEnable => FormulaDisplay.EnableEditRestricted);
               
            
            ModuleDef
            ClippingBounds = ( 0.0 , 0.0 ) ( 1.5 , 1.13333 )
            GraphObjects :
               PolygonObject Polyline ( 0.32 , 0.38 ) 
                  ( 0.32 , 0.48 ) ( 0.08 , 0.58 ) 
                  ( 0.08 , 0.88 ) ( 0.68 , 0.88 ) 
                  ( 0.68 , 0.58 ) ( 0.44 , 0.48 ) 
                  ( 0.44 , 0.38 ) 
                  OutlineColour : Colour0 = -3 
               PolygonObject Polyline ( 1.04 , 0.38 ) 
                  ( 1.04 , 0.48 ) ( 0.8 , 0.58 ) 
                  ( 0.8 , 0.88 ) ( 1.4 , 0.88 ) ( 1.4 , 0.58 ) 
                  ( 1.16 , 0.48 ) ( 1.16 , 0.38 ) 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.4 , 0.24 ) ( 1.06 , 0.34 ) 
                  "Coarse (kg)" 
                  OutlineColour : Colour0 = -3 Colour1 = 3 ColourStyle = False 
                  : ( NOT FormulaDisplay.EnableEditRestricted) 
               TextObject ( 0.32 , 0.9 ) ( 0.84 , 1.0 ) 
                  "Agitation" RightAligned 
                  Enable_ = True : InVar_ "FormulaDisplay.Formula.Bool2" 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.32 , 0.9 ) ( 0.84 , 1.0 ) 
                  "No Agitation" RightAligned 
                  Enable_ = True : ( NOT FormulaDisplay.Formula.Bool2) 
                  OutlineColour : Colour0 = -3 Colour1 = 3 ColourStyle = False 
                  : ( NOT FormulaDisplay.EnableEditRestricted) 
               TextObject ( 0.32 , 1.0 ) ( 0.94 , 1.1 ) 
                  "Parallel filling" RightAligned 
                  Enable_ = True : InVar_ "FormulaDisplay.Formula.Bool1" 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.32 , 1.0 ) ( 0.94 , 1.1 ) 
                  "No Parallel filling" RightAligned 
                  Enable_ = True : ( NOT FormulaDisplay.Formula.Bool1) 
                  OutlineColour : Colour0 = -3 Colour1 = 3 ColourStyle = False 
                  : ( NOT FormulaDisplay.EnableEditRestricted) 
               TextObject ( 0.4 , 0.04 ) ( 1.06 , 0.14 ) 
                  "Fine (kg)" 
                  OutlineColour : Colour0 = -3 Colour1 = 3 ColourStyle = False 
                  : ( NOT FormulaDisplay.EnableEditRestricted) 
               TextObject ( 0.4 , 0.14 ) ( 1.06 , 0.24 ) 
                  "Settling time (sec)" 
                  OutlineColour : Colour0 = -3 Colour1 = 3 ColourStyle = False 
                  : ( NOT FormulaDisplay.EnableEditRestricted) 
            
            ENDDEF (*Display*);
            
            ExecuteOn Invocation
               ( 1.36 , -1.4 , 0.0 , 0.1 , 0.1 
                Enable_ = True : InVar_ "FormulaDisplay.EnableEditRestricted" ) 
            : BatchExecuteOn (
            Execute => FormulaDisplay.Changed, 
            Changed => ExecuteSelected);
            
         
         ModuleDef
         ClippingBounds = ( 0.0 , -1.42 ) ( 1.5 , 0.0 )
         GraphObjects :
            RectangleObject ( -1.19209E-07 , -2.08616E-07 ) 
               ( 1.5 , -1.42 ) 
               OutlineColour : Colour0 = -3 
               FillColour : Colour1 = 51 
            TextObject ( -1.49012E-08 , -0.16 ) ( 1.5 , 0.0 ) 
               "PhaseName" VarName Width_ = 5 : InVar_ 5  ValueFraction = 2  
               OutlineColour : Colour0 = -3 
         
         ENDDEF (*Info*);
         
      
      ModuleDef
      ClippingBounds = ( -2.98023E-08 , 0.0 ) ( 1.0 , 1.1 )
      
      ENDDEF (*Page1*);
      
   
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   Two_Layers_ LayerLimit_ = 0.95
   Zoomable
   GraphObjects :
      TextObject ( 0.1 , -0.04 ) ( 0.96 , 0.08 ) 
         "FormulaDisplay" 
         ConnectionNode ( 1.0 , 0.0 ) 
         RightAligned 
         OutlineColour : Colour0 = -3 
      RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
         Layer_ = 1
         OutlineColour : Colour0 = -3 
      TextObject ( -1.0 , 0.8 ) ( 1.0 , 0.96 ) 
         "PhaseName" VarName Width_ = 5 : InVar_ 5  ValueFraction = 2  
         Layer_ = 1
         OutlineColour : Colour0 = -3 
      RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = -2 
      RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      TextObject ( -1.0 , 0.8 ) ( 1.0 , 0.96 ) 
         "PhaseName" VarName Width_ = 5 : InVar_ 5  ValueFraction = 2  
         Layer_ = 2
         OutlineColour : Colour0 = -3 
   
   ENDDEF (*FillingDisplay*);
   
   Tank
   (* 1. Function
      
      2. Relation to other modules
      
      3. Comments on connection list
      
      4. Operators interface
      4.1 Pop-up windows
      
      4.2 Logging of operator interaction
      
      4.3 Modules accessable through pathstring
      "ModuleName*SelectButton"
      "ModuleName*Info"
      
      5. Scangroups
      Inherit/ProgStationData.GroupProg
      
      6. Opsave and secure
      
      7. Advice for usage *)
    = MODULEDEFINITION DateCode_ 73641528
   MODULEPARAMETERS
      UnitName "IN Unit name": string  := "Unit name";
      JournalSystem "IN Journal system": string  := "";
      ProcessManagerNumber "IN ProcessManager number": integer ;
      EnableControl "IN Enable control": boolean  := True;
      ControlSeverity "IN Control severity": integer  := 0;
      ControlClass "IN Control class": integer  := 1;
      EnableEdit "IN Enable edit", EnableEditRestricted 
      "IN Enable restricted edit": boolean  := True;
      EditSeverity "IN Interaction severity": integer  := 0;
      EditClass "IN Interaction class": integer  := 1;
      Error "OUT Error": boolean  := Default;
      Warning "OUT Warning": boolean  := Default;
   LOCALVARIABLES
      UnitSystemList: UnitSystemType ;
      ProcessManList: ProcessManListType ;
      AccessableUnits: AccessableUnitsType ;
      Attributes: EquipAttributeType ;
      Recipe: RecipeType ;
      Operation: OperationType ;
      UnitControl: UnitControlType ;
      RecipeControl: RecipeControlType ;
      OpRecipeControl: OpRecipeControlType ;
      UnitStatus: UnitStatusType ;
      RecipeStatus: RecipeStatusType ;
      OpRecipeStatus: OpRecipeStatusType ;
      OpRecipeEditConn: OpRecipeEditConnType ;
      SampledValue: BatchJouSamplerType ;
      InteractionPar: DirectoryListPar ;
      EmptyString: identstring  := "";
      FilterTag: TagString ;
      StarString: TagString  := "*";
      Item: TagString  := "_Pump1";
      Tag: TagString ;
      A: string  := ".A";
      Status, DebugStatus: integer ;
      ErrorUnitSupervisor, WarningUnitSuper, JumpWarningUnitSuper: boolean ;
      Formula1Display: Formula1DisplayType ;
      Formula2Display: Formula2DisplayType ;
      Formula3Display: Formula3DisplayType ;
      ExecuteRequestRecipe, ExecuteRequestOpRec: boolean ;
      Value: real ;
      Error1, Error10, Error11, Error12, Error13, Error14, Error15, Error16, 
      Warning10, Warning11, Warning12, Warning13, Warning14, Warning15: boolean 
      ;
      AllocatorConnection0, AllocatorConnection1, AllocatorConnection2, 
      AllocatorConnection3, AllocatorConnection4, AllocatorConnection5: 
      AllocatorConnectType ;
      ArbitratorConnection: ArbitratorConnType ;
      ErrorColour, WarningColour, OnColour: integer ;
      ShowAllocStatus1, ShowAllocStatus2, ShowAllocStatus3, ShowAllocStatus4, 
      ShowAllocStatus5, ShowAllocStatusJump: boolean ;
   SUBMODULES
      UnitIcon Invocation
         ( -1.0 , -1.0 , 0.0 , 2.0 , 2.0 
          Layer_ = 1
          ) : UnitSuperviserIcon (
      Error => Error);
      
      UnitSupervisorCore Invocation
         ( -0.24 , -0.36 , 0.0 , 0.16 , 0.16 
          Layer_ = 2
          ) : UnitSupervisorCore (
      UnitName => UnitName, 
      ProcessManagerNumber => ProcessManagerNumber, 
      ProcessManList => ProcessManList, 
      Recipe => Recipe, 
      Operation => Operation, 
      UnitControl => UnitControl, 
      RecipeControl => RecipeControl, 
      OpRecipeControl => OpRecipeControl, 
      UnitStatus => UnitStatus, 
      RecipeStatus => RecipeStatus, 
      OpRecipeStatus => OpRecipeStatus, 
      OpRecipeEditConn => OpRecipeEditConn, 
      AllocatorConnection0 => AllocatorConnection0, 
      AllocatorConnection1 => AllocatorConnection1, 
      AllocatorConnection2 => AllocatorConnection2, 
      AllocatorConnection3 => AllocatorConnection3, 
      AllocatorConnection4 => AllocatorConnection4, 
      AllocatorConnection5 => AllocatorConnection5, 
      ArbitratorConnection => ArbitratorConnection, 
      Error => ErrorUnitSupervisor, 
      Warning => WarningUnitSuper, 
      JumpWarning => JumpWarningUnitSuper);
      
      Phase3 Invocation
         ( 0.0 , -0.36 , 0.0 , 0.04 , 0.04 
          Layer_ = 2
          ) : Agitation2 (
      PhaseName => "Agitation2", 
      UnitName => UnitName, 
      EnableEdit => EnableEdit, 
      EnableEditRestricted => EnableEditRestricted, 
      EnableControl => EnableControl, 
      InteractionSeverity => EditSeverity, 
      InteractionClass => EditClass);
      
      Phase4 Invocation
         ( 0.08 , -0.36 , 0.0 , 0.04 , 0.04 
          Layer_ = 2
          ) : Ramping (
      PhaseName => "Ramping", 
      UnitName => UnitName, 
      EnableEdit => EnableEdit, 
      EnableEditRestricted => EnableEditRestricted, 
      EnableControl => EnableControl, 
      InteractionSeverity => EditSeverity, 
      InteractionClass => EditClass);
      
      Phase1 Invocation
         ( 0.000120044 , -0.28 , 0.0 , 0.04 , 0.04 
          Layer_ = 2
          ) : Heating (
      PhaseName => "Heating", 
      UnitName => UnitName, 
      EnableEdit => EnableEdit, 
      EnableEditRestricted => EnableEditRestricted, 
      EnableControl => EnableControl, 
      InteractionSeverity => EditSeverity, 
      InteractionClass => EditClass);
      
      Phase2 Invocation
         ( 0.08 , -0.28 , 0.0 , 0.04 , 0.04 
          Layer_ = 2
          ) : Agitation1 (
      PhaseName => "Agitation1", 
      UnitName => UnitName, 
      EnableEdit => EnableEdit, 
      EnableEditRestricted => EnableEditRestricted, 
      EnableControl => EnableControl, 
      InteractionSeverity => EditSeverity, 
      InteractionClass => EditClass);
      
      Phase5 Invocation
         ( 0.0 , -0.44 , 0.0 , 0.04 , 0.04 
          Layer_ = 2
          ) : Filling (
      PhaseName => "Filling", 
      UnitName => UnitName, 
      EnableEdit => EnableEdit, 
      EnableEditRestricted => EnableEditRestricted, 
      EnableControl => EnableControl, 
      InteractionSeverity => EditSeverity, 
      InteractionClass => EditClass);
      
      BatchJournalSampler Invocation
         ( 0.6 , -0.4 , 0.0 , 0.08 , 0.08 
          Layer_ = 2
          ) : BatchJournalSampler (
      Value => value, 
      Tag => Tag, 
      SampledValue => SampledValue);
      
      BatchJournalLogger Invocation
         ( 0.72 , -0.72 , 0.0 , 0.2 , 0.2 
          Layer_ = 2
          ) : BatchLoggerMaster (
      FilterTag => FilterTag, 
      JournalName => OpRecipeEditConn.OperationRecipe.Header.
      BatchIdentification, 
      JournalSystem => JournalSystem, 
      EnableLogAlarms => OpRecipeEditConn.OperationRecipe.Header.LogAlarms, 
      EnableLogTracking => OpRecipeEditConn.OperationRecipe.Header.LogTracking, 
      EnableLogInteraction => OpRecipeEditConn.OperationRecipe.Header.
      LogInteraction, 
      EnableLogHistory => OpRecipeEditConn.OperationRecipe.Header.LogHistory, 
      SampledValues => SampledValue, 
      SampleTime => 10, 
      Error => Error1);
      
      Prog Invocation
         ( 0.84 , 0.16 , 0.0 , 0.12 , 0.12 
          Layer_ = 2
          ) : MODULEDEFINITION DateCode_ 74637132 ( GroupConn = GLOBAL 
      progstationdata.groupprogfast ) 
      MODULEPARAMETERS
         ExecuteRequestRecipe "IN Request operation recipe in Prog", 
         ExecuteRequestOpRec "IN Request recipe in Prog": boolean ;
         OpRecipeControl "OUT Write via the WriteVar procedure": 
         OpRecipeControlType ;
         RecipeControl "OUT Write via the WriteVar procedure": 
         RecipeControlType ;
      LOCALVARIABLES
         ControlRecipeAuthor, Dummystring: string ;
         AuthorAsyncOP, ExecuteAsyncOP: AsyncOperation ;
         Status: integer ;
      
      
      ModuleDef
      ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
      
      ModuleCode
      EQUATIONBLOCK Prog COORD -0.66667, -0.66667 OBJSIZE 1.33333, 1.33333 :
         IF ExecuteRequestOpRec THEN
            CurrentUser(ControlRecipeAuthor, Dummystring);
            WriteVar(OpRecipeControl.RequestRecipe.ControlRecipeAuthor, 
            ControlRecipeAuthor, AuthorAsyncOP, Status);
            WriteVar(OpRecipeControl.RequestRecipe.Execute, ExecuteRequestOpRec
            , ExecuteAsyncOP, Status);
            ExecuteRequestOpRec = Off;
         ENDIF;
         IF ExecuteRequestRecipe THEN
            CurrentUser(ControlRecipeAuthor, Dummystring);
            WriteVar(RecipeControl.RequestRecipe.ControlRecipeAuthor, 
            ControlRecipeAuthor, AuthorAsyncOP, Status);
            WriteVar(RecipeControl.RequestRecipe.Execute, ExecuteRequestRecipe, 
            ExecuteAsyncOP, Status);
            ExecuteRequestRecipe = Off;
         ENDIF;
      
      ENDDEF (*Prog*) (
      ExecuteRequestRecipe => ExecuteRequestRecipe, 
      ExecuteRequestOpRec => ExecuteRequestOpRec, 
      OpRecipeControl => OpRecipeControl, 
      RecipeControl => RecipeControl);
      
      OpRecipeEditor Invocation
         ( -0.68 , -0.36 , 0.0 , 0.16 , 0.16 
          Layer_ = 2
          ) : OpRecipeEditor (
      Name => "OperationRecipeEditor", 
      OpRecipeEditConn => OpRecipeEditConn, 
      OpRecipeControl => OpRecipeControl, 
      OpRecipeStatus => OpRecipeStatus, 
      EnableEdit => EnableEdit, 
      EnableEditRestricted => EnableEditRestricted, 
      EditSeverity => EditSeverity, 
      EditClass => EditClass, 
      EnableControl => EnableControl, 
      ControlSeverity => ControlSeverity, 
      ControlClass => ControlClass);
      
      UnitAllocator0 Invocation
         ( -0.6 , -0.76 , 0.0 , 0.08 , 0.08 
          Layer_ = 2
          ) : UnitAllocator (
      Recipe => Recipe, 
      IdentificationNo => 0, 
      UnitSystemList => UnitSystemList, 
      AccessableUnits => AccessableUnits, 
      AllocatorConnection => AllocatorConnection0, 
      EnableInteraction => EnableControl, 
      InteractionSeverity => ControlSeverity, 
      InteractionClass => ControlClass, 
      Error => Error10, 
      Warning => Warning10, 
      UnitName => UnitName, 
      Activity => OpRecipeStatus.Activity);
      
      UnitAllocator1 Invocation
         ( -0.4 , -0.76 , 0.0 , 0.08 , 0.08 
          Layer_ = 2
          ) : UnitAllocator (
      Recipe => Recipe, 
      IdentificationNo => 1, 
      UnitSystemList => UnitSystemList, 
      AccessableUnits => AccessableUnits, 
      AllocatorConnection => AllocatorConnection1, 
      EnableInteraction => EnableControl, 
      InteractionSeverity => ControlSeverity, 
      InteractionClass => ControlClass, 
      Error => Error11, 
      Warning => Warning11, 
      UnitName => UnitName, 
      Activity => OpRecipeStatus.Activity);
      
      UnitAllocator2 Invocation
         ( -0.2 , -0.76 , 0.0 , 0.08 , 0.08 
          Layer_ = 2
          ) : UnitAllocator (
      Recipe => Recipe, 
      IdentificationNo => 2, 
      UnitSystemList => UnitSystemList, 
      AccessableUnits => AccessableUnits, 
      AllocatorConnection => AllocatorConnection2, 
      EnableInteraction => EnableControl, 
      InteractionSeverity => ControlSeverity, 
      InteractionClass => ControlClass, 
      Error => Error12, 
      Warning => Warning12, 
      UnitName => UnitName, 
      Activity => OpRecipeStatus.Activity);
      
      UnitAllocator3 Invocation
         ( 0.0 , -0.76 , 0.0 , 0.08 , 0.08 
          Layer_ = 2
          ) : UnitAllocator (
      Recipe => Recipe, 
      IdentificationNo => 3, 
      UnitSystemList => UnitSystemList, 
      AccessableUnits => AccessableUnits, 
      AllocatorConnection => AllocatorConnection3, 
      EnableInteraction => EnableControl, 
      InteractionSeverity => ControlSeverity, 
      InteractionClass => ControlClass, 
      Error => Error13, 
      Warning => Warning13, 
      UnitName => UnitName, 
      Activity => OpRecipeStatus.Activity);
      
      UnitAllocator4 Invocation
         ( 0.2 , -0.76 , 0.0 , 0.08 , 0.08 
          Layer_ = 2
          ) : UnitAllocator (
      Recipe => Recipe, 
      IdentificationNo => 4, 
      UnitSystemList => UnitSystemList, 
      AccessableUnits => AccessableUnits, 
      AllocatorConnection => AllocatorConnection4, 
      EnableInteraction => EnableControl, 
      InteractionSeverity => ControlSeverity, 
      InteractionClass => ControlClass, 
      Error => Error14, 
      Warning => Warning14, 
      UnitName => UnitName, 
      Activity => OpRecipeStatus.Activity);
      
      UnitAllocator5 Invocation
         ( 0.4 , -0.76 , 0.0 , 0.08 , 0.08 
          Layer_ = 2
          ) : UnitAllocator (
      Recipe => Recipe, 
      IdentificationNo => 5, 
      UnitSystemList => UnitSystemList, 
      AccessableUnits => AccessableUnits, 
      AllocatorConnection => AllocatorConnection5, 
      EnableInteraction => EnableControl, 
      InteractionSeverity => ControlSeverity, 
      InteractionClass => ControlClass, 
      Error => Error15, 
      Warning => Warning15, 
      UnitName => UnitName, 
      Activity => OpRecipeStatus.Activity);
      
      UnitArbitrator Invocation
         ( -0.84 , -0.76 , 0.0 , 0.08 , 0.08 
          Layer_ = 2
          ) : UnitArbitratorMaster (
      UnitName => UnitName, 
      EquipmentAttribute => Attributes, 
      ArbitratorConnection => ArbitratorConnection, 
      Error => Error16);
      
      ColourExtraction Invocation
         ( 0.56 , -0.24 , 0.0 , 0.04 , 0.04 
          Layer_ = 2
          ) : ColourExtraction (
      ErrorColour => ErrorColour, 
      WarningColour => WarningColour, 
      OnColour => OnColour);
      
      Info Invocation
         ( -0.96 , 0.72 , 0.0 , 0.4 , 0.4 
          Layer_ = 2
          ) : MODULEDEFINITION DateCode_ 282951040 ( Frame_Module ) 
      SUBMODULES
         ParIcon Invocation
            ( 3.36 , -0.55 , 0.0 , 0.12 , 0.12 
             ) : RecipeIcon;
         
         StartIcon1 Invocation
            ( 1.18 , -1.6 , 0.0 , 0.1 , 0.1 
             Enable_ = True : InVar_ "ShowAllocStatus1" Dim_ = False : ( NOT 
             EnableControl) ) : StartIcon;
         
         StartIcon2 Invocation
            ( 1.18 , -1.7 , 0.0 , 0.1 , 0.1 
             Enable_ = True : InVar_ "ShowAllocStatus2" Dim_ = False : ( NOT 
             EnableControl) ) : StartIcon;
         
         OmitIcon2 Invocation
            ( 1.28 , -1.7 , 0.0 , 0.1 , 0.1 
             Enable_ = True : InVar_ "ShowAllocStatus2" Dim_ = False : ( NOT 
             EnableControl) ) : StopIcon;
         
         StartIcon3 Invocation
            ( 1.18 , -1.8 , 0.0 , 0.1 , 0.1 
             Enable_ = True : InVar_ "ShowAllocStatus3" Dim_ = False : ( NOT 
             EnableControl) ) : StartIcon;
         
         OmitIcon3 Invocation
            ( 1.28 , -1.8 , 0.0 , 0.1 , 0.1 
             Enable_ = True : InVar_ "ShowAllocStatus3" Dim_ = False : ( NOT 
             EnableControl) ) : StopIcon;
         
         StartIcon4 Invocation
            ( 1.18 , -1.9 , 0.0 , 0.1 , 0.1 
             Enable_ = True : InVar_ "ShowAllocStatus4" Dim_ = False : ( NOT 
             EnableControl) ) : StartIcon;
         
         OmitIcon4 Invocation
            ( 1.28 , -1.9 , 0.0 , 0.1 , 0.1 
             Enable_ = True : InVar_ "ShowAllocStatus4" Dim_ = False : ( NOT 
             EnableControl) ) : StopIcon;
         
         StartIcon5 Invocation
            ( 1.18 , -1.99 , 0.0 , 0.1 , 0.1 
             Enable_ = True : InVar_ "ShowAllocStatus5" Dim_ = False : ( NOT 
             EnableControl) ) : StartIcon;
         
         OmitIcon5 Invocation
            ( 1.28 , -2.0 , 0.0 , 0.1 , 0.1 
             Enable_ = True : InVar_ "ShowAllocStatus5" Dim_ = False : ( NOT 
             EnableControl) ) : StopIcon;
         
         StartIconJump Invocation
            ( 1.18 , -2.1 , 0.0 , 0.1 , 0.1 
             Enable_ = True : InVar_ "ShowAllocStatusJump" Dim_ = False : ( NOT 
             EnableControl) ) : StartIcon;
         
         OmitIconJump Invocation
            ( 1.28 , -2.1 , 0.0 , 0.1 , 0.1 
             Enable_ = True : InVar_ "ShowAllocStatusJump" Dim_ = False : ( NOT 
             EnableControl) ) : StopIcon;
         
         OpRecManIcon Invocation
            ( 3.03 , -0.54 , 0.0 , 0.12 , 0.12 
             Dim_ = False : ( NOT EnableControl) ) : ManIcon;
         
         OpRecAutoIcon Invocation
            ( 3.19 , -0.54 , 0.0 , 0.12 , 0.12 
             Dim_ = False : ( NOT EnableControl) ) : AutoIcon;
         
         RecExecuteIcon Invocation
            ( 1.34 , -1.14 , 0.0 , 0.1 , 0.1 
             Dim_ = False : ( NOT EnableControl) ) : ExecuteIcon;
         
         ReqRecExecuteIcon Invocation
            ( 1.34 , -1.02 , 0.0 , 0.1 , 0.1 
             Dim_ = False : ( NOT EnableControl) ) : ExecuteIcon;
         
         OpRecExecuteIcon Invocation
            ( 3.4 , -1.06 , 0.0 , 0.1 , 0.1 
             Dim_ = False : ( NOT EnableControl) ) : ExecuteIcon;
         
         WarningIcon Invocation
            ( 3.4 , -0.2 , 0.0 , 0.1 , 0.1 
             Enable_ = True : InVar_ "WarningUnitSuper" ) : WarningIcon;
         
         JumpWarningIcon Invocation
            ( 3.4 , -0.2 , 0.0 , 0.1 , 0.1 
             Enable_ = True : InVar_ "JumpWarningUnitSuper" ) : WarningIcon;
         
         ErrorIcon Invocation
            ( 3.4 , -0.1 , 0.0 , 0.1 , 0.1 
             Enable_ = True : InVar_ "ErrorUnitSupervisor" ) : ErrorIcon;
         
         WindowIcon Invocation
            ( 3.35 , -0.55 , 0.0 , 0.14 , 0.14 
             ) : WindowIcon;
         
         OmitIcon1 Invocation
            ( 1.28 , -1.6 , 0.0 , 0.1 , 0.1 
             Enable_ = True : InVar_ "ShowAllocStatus1" Dim_ = False : ( NOT 
             EnableControl) ) : StopIcon;
         
         DirectoryList1 Invocation
            ( 1.39 , -0.571 , 0.0 , 0.05 , 0.0500004 
             ) : DirectoryList (
         InteractionPar => InteractionPar, 
         EnableInteraction => EnableControl, 
         EnableTypeOfFile => False, 
         StrNoExt => RecipeControl.RequestRecipe.MasterRecipeName);
         
         DirectoryList2 Invocation
            ( 3.45 , -0.611 , 0.0 , 0.05 , 0.0500004 
             ) : DirectoryList (
         InteractionPar => InteractionPar, 
         EnableInteraction => EnableControl, 
         EnableTypeOfFile => False, 
         StrNoExt => OpRecipeControl.RequestRecipe.MasterRecipeName);
         
      
      ModuleDef
      ClippingBounds = ( 0.0 , -2.1 ) ( 3.5 , 0.0 )
      Grid = 0.01
      GraphObjects :
         RectangleObject ( 1.92 , -1.4 ) ( 2.24 , -1.1 ) 
            Enable_ = True : InVar_ "OpRecipeStatus.ActiveStep1.Error" 
            OutlineColour : Colour0 = -1 
            FillColour : Colour0 = 12 Colour1 = -1 
         RectangleObject ( 2.24 , -1.4 ) ( 2.56 , -1.1 ) 
            Enable_ = True : InVar_ "OpRecipeStatus.ActiveStep2.Error" 
            OutlineColour : Colour0 = -1 
            FillColour : Colour0 = 12 Colour1 = -1 
         RectangleObject ( 2.56 , -1.4 ) ( 2.88 , -1.1 ) 
            Enable_ = True : InVar_ "OpRecipeStatus.ActiveStep3.Error" 
            OutlineColour : Colour0 = -1 
            FillColour : Colour0 = 12 Colour1 = -1 
         RectangleObject ( 2.88 , -1.4 ) ( 3.2 , -1.1 ) 
            Enable_ = True : InVar_ "OpRecipeStatus.ActiveStep4.Error" 
            OutlineColour : Colour0 = -1 
            FillColour : Colour0 = 12 Colour1 = -1 
         RectangleObject ( 3.2 , -1.4 ) ( 3.52 , -1.1 ) 
            Enable_ = True : InVar_ "OpRecipeStatus.ActiveStep5.Error" 
            OutlineColour : Colour0 = -1 
            FillColour : Colour0 = 12 Colour1 = -1 
         RectangleObject ( 0.0 , -2.1 ) ( 3.5 , 1.86265E-08 ) 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.0 , -0.16 ) ( 1.48 , -1.49012E-08 ) 
            "UnitName" VarName Width_ = 5 : InVar_ 5  ValueFraction = 2  
            OutlineColour : Colour0 = -3 
         TextObject ( 1.92 , -1.2 ) ( 2.24 , -1.1 ) 
            "OpRecipeStatus.ActiveStep1.StepName" VarName Width_ = 5 : InVar_ 5  
            ValueFraction = 2  
            OutlineColour : Colour0 = -3 
         TextObject ( 2.24 , -1.2 ) ( 2.56 , -1.1 ) 
            "OpRecipeStatus.ActiveStep2.StepName" VarName Width_ = 5 : InVar_ 5  
            ValueFraction = 2  
            OutlineColour : Colour0 = -3 
         TextObject ( 2.56 , -1.2 ) ( 2.88 , -1.1 ) 
            "OpRecipeStatus.ActiveStep3.StepName" VarName Width_ = 5 : InVar_ 5  
            ValueFraction = 2  
            OutlineColour : Colour0 = -3 
         TextObject ( 2.88 , -1.2 ) ( 3.2 , -1.1 ) 
            "OpRecipeStatus.ActiveStep4.StepName" VarName Width_ = 5 : InVar_ 5  
            ValueFraction = 2  
            OutlineColour : Colour0 = -3 
         TextObject ( 3.2 , -1.2 ) ( 3.52 , -1.1 ) 
            "OpRecipeStatus.ActiveStep5.StepName" VarName Width_ = 5 : InVar_ 5  
            ValueFraction = 2  
            OutlineColour : Colour0 = -3 
         TextObject ( 1.92 , -1.3 ) ( 2.24 , -1.2 ) 
            "OpRecipeStatus.ActiveStep1.PhaseName" VarName Width_ = 5 : InVar_ 
            5  ValueFraction = 2  
            OutlineColour : Colour0 = -3 
         TextObject ( 2.24 , -1.3 ) ( 2.56 , -1.2 ) 
            "OpRecipeStatus.ActiveStep2.PhaseName" VarName Width_ = 5 : InVar_ 
            5  ValueFraction = 2  
            OutlineColour : Colour0 = -3 
         TextObject ( 2.56 , -1.3 ) ( 2.88 , -1.2 ) 
            "OpRecipeStatus.ActiveStep3.PhaseName" VarName Width_ = 5 : InVar_ 
            5  ValueFraction = 2  
            OutlineColour : Colour0 = -3 
         TextObject ( 2.88 , -1.3 ) ( 3.2 , -1.2 ) 
            "OpRecipeStatus.ActiveStep4.PhaseName" VarName Width_ = 5 : InVar_ 
            5  ValueFraction = 2  
            OutlineColour : Colour0 = -3 
         TextObject ( 3.2 , -1.3 ) ( 3.52 , -1.2 ) 
            "OpRecipeStatus.ActiveStep5.PhaseName" VarName Width_ = 5 : InVar_ 
            5  ValueFraction = 2  
            OutlineColour : Colour0 = -3 
         TextObject ( 1.92 , -1.4 ) ( 2.24 , -1.3 ) 
            "OpRecipeStatus.ActiveStep1.Mode" VarName Width_ = 5 : InVar_ 5  
            ValueFraction = 2  
            OutlineColour : Colour0 = -3 
         TextObject ( 2.24 , -1.4 ) ( 2.56 , -1.3 ) 
            "OpRecipeStatus.ActiveStep2.Mode" VarName Width_ = 5 : InVar_ 5  
            ValueFraction = 2  
            OutlineColour : Colour0 = -3 
         TextObject ( 2.56 , -1.4 ) ( 2.88 , -1.3 ) 
            "OpRecipeStatus.ActiveStep3.Mode" VarName Width_ = 5 : InVar_ 5  
            ValueFraction = 2  
            OutlineColour : Colour0 = -3 
         TextObject ( 2.88 , -1.4 ) ( 3.2 , -1.3 ) 
            "OpRecipeStatus.ActiveStep4.Mode" VarName Width_ = 5 : InVar_ 5  
            ValueFraction = 2  
            OutlineColour : Colour0 = -3 
         TextObject ( 3.2 , -1.4 ) ( 3.52 , -1.3 ) 
            "OpRecipeStatus.ActiveStep5.Mode" VarName Width_ = 5 : InVar_ 5  
            ValueFraction = 2  
            OutlineColour : Colour0 = -3 
         TextObject ( 1.48 , -1.2 ) ( 1.92 , -1.1 ) 
            "Recipe phase" LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 1.48 , -1.3 ) ( 1.92 , -1.2 ) 
            "Equipment phase:" LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 1.48 , -1.4 ) ( 1.92 , -1.3 ) 
            "Mode:" LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 1.5 , -1.52 ) ( 2.08 , -1.42 ) 
            "Start:" LeftAligned 
            OutlineColour : Colour0 = -3 Colour1 = 3 ColourStyle = False : ( 
            NOT EnableControl) 
         TextObject ( 1.5 , -1.62 ) ( 2.07 , -1.52 ) 
            "Stop:" LeftAligned 
            OutlineColour : Colour0 = -3 Colour1 = 3 ColourStyle = False : ( 
            NOT EnableControl) 
         TextObject ( 1.5 , -1.72 ) ( 2.07 , -1.62 ) 
            "Pause:" LeftAligned 
            OutlineColour : Colour0 = -3 Colour1 = 3 ColourStyle = False : ( 
            NOT EnableControl) 
         TextObject ( 1.5 , -1.82 ) ( 2.07 , -1.72 ) 
            "Continue:" LeftAligned 
            OutlineColour : Colour0 = -3 Colour1 = 3 ColourStyle = False : ( 
            NOT EnableControl) 
         TextObject ( 1.5 , -1.96 ) ( 2.08 , -1.86 ) 
            "Desired result:" LeftAligned 
            OutlineColour : Colour0 = -3 Colour1 = 3 ColourStyle = False : ( 
            NOT EnableControl) 
         TextObject ( 1.5 , -2.06 ) ( 2.07 , -1.96 ) 
            "Next:" LeftAligned 
            OutlineColour : Colour0 = -3 Colour1 = 3 ColourStyle = False : ( 
            NOT EnableControl) 
         CompositeObject 
         CompositeObject 
         TextObject ( 1.48 , -0.86 ) ( 2.19 , -0.76 ) 
            "Start recipe:" LeftAligned 
            OutlineColour : Colour0 = -3 Colour1 = 3 ColourStyle = False : ( 
            NOT EnableControl) 
         TextObject ( 1.48 , -0.96 ) ( 2.19 , -0.86 ) 
            "Stop recipe:" LeftAligned 
            OutlineColour : Colour0 = -3 Colour1 = 3 ColourStyle = False : ( 
            NOT EnableControl) 
         TextObject ( 2.98023E-08 , -1.26 ) ( 0.72 , -1.16 ) 
            "Deactivate operation:" LeftAligned 
            OutlineColour : Colour0 = -3 Colour1 = 3 ColourStyle = False : ( 
            NOT EnableControl) 
         TextObject ( 0.82 , -1.26 ) ( 1.38 , -1.16 ) 
            "Allocation inhibited:" LeftAligned 
            OutlineColour : Colour0 = -3 Colour1 = 3 ColourStyle = False : ( 
            NOT EnableControl) 
         TextObject ( 0.82 , -1.36 ) ( 1.38 , -1.26 ) 
            "Allocation allowed:" LeftAligned 
            OutlineColour : Colour0 = -3 Colour1 = 3 ColourStyle = False : ( 
            NOT EnableControl) 
         TextObject ( 0.0 , -1.14 ) ( 0.73 , -1.04 ) 
            "Activate operation:" LeftAligned 
            OutlineColour : Colour0 = -3 Colour1 = 3 ColourStyle = False : ( 
            NOT EnableControl) 
         TextObject ( 1.48 , -1.06 ) ( 2.19 , -0.96 ) 
            "Delete recipe:" LeftAligned 
            OutlineColour : Colour0 = -3 Colour1 = 3 ColourStyle = False : ( 
            NOT EnableControl) 
         TextObject ( 2.98023E-08 , -1.36 ) ( 0.72 , -1.26 ) 
            "Delete recipe:" LeftAligned 
            OutlineColour : Colour0 = -3 Colour1 = 3 ColourStyle = False : ( 
            NOT EnableControl) 
         TextObject ( 1.5 , -0.16 ) ( 2.16 , -0.06 ) 
            "Unit inhibited:" LeftAligned 
            OutlineColour : Colour0 = -3 Colour1 = 3 ColourStyle = False : ( 
            NOT EnableControl) 
         TextObject ( 1.5 , -0.26 ) ( 2.16 , -0.16 ) 
            "Unit available:" LeftAligned 
            OutlineColour : Colour0 = -3 Colour1 = 3 ColourStyle = False : ( 
            NOT EnableControl) 
         TextObject ( -8.9407E-08 , -1.5 ) ( 0.72 , -1.4 ) 
            "Next operations:" 
            OutlineColour : Colour0 = -3 
         TextObject ( -2.98023E-08 , -1.6 ) ( 0.66 , -1.5 ) 
            "RecipeStatus.NextOperation1.Name" VarName Width_ = 5  
            ValueFraction = 2  
            OutlineColour : Colour0 = -3 
         TextObject ( -2.98023E-08 , -1.7 ) ( 0.66 , -1.6 ) 
            "RecipeStatus.NextOperation2.Name" VarName Width_ = 5  
            ValueFraction = 2  
            OutlineColour : Colour0 = -3 
         TextObject ( -2.98023E-08 , -1.8 ) ( 0.66 , -1.7 ) 
            "RecipeStatus.NextOperation3.Name" VarName Width_ = 5  
            ValueFraction = 2  
            OutlineColour : Colour0 = -3 
         TextObject ( -2.98023E-08 , -1.9 ) ( 0.66 , -1.8 ) 
            "RecipeStatus.NextOperation4.Name" VarName Width_ = 5  
            ValueFraction = 2  
            OutlineColour : Colour0 = -3 
         TextObject ( -2.98023E-08 , -2.0 ) ( 0.66 , -1.9 ) 
            "RecipeStatus.NextOperation5.Name" VarName Width_ = 5  
            ValueFraction = 2  
            OutlineColour : Colour0 = -3 
         TextObject ( 2.98023E-08 , -2.1 ) ( 0.66 , -2.0 ) 
            "RecipeStatus.JumpOperation.Name" VarName Width_ = 5  ValueFraction 
            = 2  
            OutlineColour : Colour0 = -3 
         TextObject ( 0.72 , -1.5 ) ( 1.34 , -1.4 ) 
            "Allocation status:" 
            OutlineColour : Colour0 = -3 
         TextObject ( 1.49012E-07 , -1.02 ) ( 1.34 , -0.92 ) 
            "Request recipe:" LeftAligned 
            OutlineColour : Colour0 = -3 Colour1 = 3 ColourStyle = False : ( 
            NOT EnableControl) 
         TextObject ( 2.29 , -1.06 ) ( 3.39 , -0.96 ) 
            "Request recipe:" LeftAligned 
            OutlineColour : Colour0 = -3 Colour1 = 3 ColourStyle = False : ( 
            NOT EnableControl) 
         TextObject ( 1.19209E-07 , -0.62 ) ( 0.72 , -0.52 ) 
            "Master recipe:" LeftAligned 
            OutlineColour : Colour0 = -3 Colour1 = 3 ColourStyle = False : ( 
            NOT EnableControl) 
         TextObject ( 2.06 , -0.66 ) ( 2.82 , -0.56 ) 
            "Master recipe:" LeftAligned 
            OutlineColour : Colour0 = -3 Colour1 = 3 ColourStyle = False : ( 
            NOT EnableControl) 
         TextObject ( 1.45286E-07 , -0.52 ) ( 0.5 , -0.4 ) 
            "Operation:" LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.5 , -0.52 ) ( 1.44 , -0.4 ) 
            "Operation.Header.Name" VarName Width_ = 5  ValueFraction = 2  
            LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 1.49012E-07 , -0.72 ) ( 0.72 , -0.62 ) 
            "Control recipe:" LeftAligned 
            OutlineColour : Colour0 = -3 Colour1 = 3 ColourStyle = False : ( 
            NOT EnableControl) 
         TextObject ( 2.06 , -0.76 ) ( 2.82 , -0.66 ) 
            "Control recipe:" LeftAligned 
            OutlineColour : Colour0 = -3 Colour1 = 3 ColourStyle = False : ( 
            NOT EnableControl) 
         TextObject ( 4.02331E-07 , -0.82 ) ( 0.72 , -0.72 ) 
            "Batch id:" LeftAligned 
            OutlineColour : Colour0 = -3 Colour1 = 3 ColourStyle = False : ( 
            NOT EnableControl) 
         TextObject ( 2.29 , -0.86 ) ( 2.82 , -0.76 ) 
            "Batch id:" LeftAligned 
            OutlineColour : Colour0 = -3 Colour1 = 3 ColourStyle = False : ( 
            NOT EnableControl) 
         TextObject ( 3.72529E-07 , -0.92 ) ( 0.72 , -0.82 ) 
            "Scale factor:" LeftAligned 
            OutlineColour : Colour0 = -3 Colour1 = 3 ColourStyle = False : ( 
            NOT EnableControl) 
         TextObject ( 2.29 , -0.96 ) ( 3.05 , -0.86 ) 
            "Scale factor:" LeftAligned 
            OutlineColour : Colour0 = -3 Colour1 = 3 ColourStyle = False : ( 
            NOT EnableControl) 
         TextObject ( 2.71 , -0.54 ) ( 3.03 , -0.44 ) 
            "OpRecipeStatus.Activity" VarName Width_ = 5 : InVar_ 5  
            ValueFraction = 2  
            OutlineColour : Colour0 = -3 
         TextObject ( 1.28 , -0.4 ) ( 1.48 , -0.3 ) 
            "RecipeStatus.Activity" VarName Width_ = 5 : InVar_ 5  
            ValueFraction = 2  
            OutlineColour : Colour0 = -3 
         LineObject ( 1.48 , -2.09 ) ( 1.48 , -0.15 ) 
         TextObject ( 1.51 , -0.42 ) ( 2.64 , -0.28 ) 
            "Operation recipe:" 
         TextObject ( -1.49012E-07 , -0.3 ) ( 0.67 , -0.16 ) 
            "Recipe:" 
         TextObject ( 2.64 , -0.42 ) ( 3.5 , -0.28 ) 
            "OpRecipeEditConn.OperationRecipe.Header.MasterRecipeName" VarName 
            Width_ = 5  ValueFraction = 2  
         TextObject ( 0.67 , -0.3 ) ( 1.48 , -0.16 ) 
            "Recipe.Header.MasterRecipeName" VarName Width_ = 5  ValueFraction 
            = 2  
         LineObject ( 0.0 , -0.16 ) ( 1.48 , -0.16 ) 
         LineObject ( 1.48 , -0.28 ) ( 3.5 , -0.28 ) 
         TextObject ( 2.32 , -0.16 ) ( 2.68 , -0.06 ) 
            "Volume:" LeftAligned 
         TextObject ( 3.04 , -0.16 ) ( 3.28 , -0.06 ) 
            "L" LeftAligned 
         CompositeObject 
         CompositeObject 
         CompositeObject 
         CompositeObject 
         CompositeObject 
         CompositeObject 
         CompositeObject 
         CompositeObject 
         CompositeObject 
         CompositeObject 
         CompositeObject 
         CompositeObject 
         TextObject ( 3.3 , -0.2 ) ( 3.4 , -0.1 ) 
            "J" RightAligned 
            Enable_ = True : InVar_ "JumpWarningUnitSuper" 
      InteractObjects :
         ComBut_ ( 3.02 , -0.55 ) ( 3.16 , -0.41 ) 
            Bool_Value
            Enable_ = True : InVar_ False Variable = False : OutVar_ 
            "OpRecipeStatus.ManualMode" SetAction
            Abs_ SetApp_
            
         ComBut_ ( 3.02 , -0.55 ) ( 3.16 , -0.41 ) 
            Bool_Value
            Variable = False : OutVar_ "OpRecipeControl.Manual" Visible_ = True 
            : (EnableControl AND  NOT OpRecipeStatus.ManualMode) ToggleAction
            Abs_ SetApp_
            
         ComBut_ ( 3.18 , -0.55 ) ( 3.32 , -0.41 ) 
            Bool_Value
            Enable_ = True : InVar_ False Variable = False : OutVar_ 
            "OpRecipeStatus.ManualMode" ResetAction
            Abs_ SetApp_
            
         ComBut_ ( 3.18 , -0.55 ) ( 3.32 , -0.41 ) 
            Bool_Value
            Variable = False : OutVar_ "OpRecipeControl.Automatic" Visible_ = 
            True : (EnableControl AND OpRecipeStatus.ManualMode) ToggleAction
            Abs_ SetApp_
            
         TextBox_ ( 2.82 , -0.66 ) ( 3.4 , -0.56 ) 
            String_Value
            Enable_ = True : InVar_ "EnableControl" Variable = "" : OutVar_ 
            "OpRecipeControl.RequestRecipe.MasterRecipeName" LeftAligned Abs_ 
            Digits_
            
            FillColour : Colour0 = 9 Colour1 = -1 
         TextBox_ ( 0.72 , -0.62 ) ( 1.34 , -0.52 ) 
            String_Value
            Enable_ = True : InVar_ "EnableControl" Variable = "" : OutVar_ 
            "RecipeControl.RequestRecipe.MasterRecipeName" LeftAligned Abs_ 
            Digits_
            
            FillColour : Colour0 = 9 Colour1 = -1 
         TextBox_ ( 0.72 , -0.72 ) ( 1.44 , -0.62 ) 
            String_Value
            Enable_ = True : InVar_ "EnableControl" Variable = "" : OutVar_ 
            "RecipeControl.RequestRecipe.ControlRecipeName" LeftAligned Abs_ 
            Digits_
            
            FillColour : Colour0 = 9 Colour1 = -1 
         TextBox_ ( 0.72 , -0.82 ) ( 1.44 , -0.72 ) 
            String_Value
            Enable_ = True : InVar_ "EnableControl" Variable = "" : OutVar_ 
            "RecipeControl.RequestRecipe.BatchIdentification" LeftAligned Abs_ 
            Digits_
            
            FillColour : Colour0 = 9 Colour1 = -1 
         TextBox_ ( 0.73 , -1.14 ) ( 1.34 , -1.04 ) 
            String_Value
            Enable_ = True : InVar_ "EnableControl" Variable = "" : OutVar_ 
            "RecipeControl.ActivateOperation.Name" LeftAligned Abs_ Decimal_
            
            FillColour : Colour0 = 9 Colour1 = -1 
         TextBox_ ( 2.82 , -0.76 ) ( 3.5 , -0.66 ) 
            String_Value
            Enable_ = True : InVar_ "EnableControl" Variable = "" : OutVar_ 
            "OpRecipeControl.RequestRecipe.ControlRecipeName" LeftAligned Abs_ 
            Digits_
            
            FillColour : Colour0 = 9 Colour1 = -1 
         TextBox_ ( 2.82 , -0.86 ) ( 3.5 , -0.76 ) 
            String_Value
            Enable_ = True : InVar_ "EnableControl" Variable = "" : OutVar_ 
            "OpRecipeControl.RequestRecipe.BatchIdentification" LeftAligned 
            Abs_ Digits_
            
            FillColour : Colour0 = 9 Colour1 = -1 
         TextBox_ ( 3.05 , -0.96 ) ( 3.5 , -0.86 ) 
            Real_Value
            Enable_ = True : InVar_ "EnableControl" Variable = 0.0 : OutVar_ 
            "OpRecipeControl.RequestRecipe.ScaleFactor" LeftAligned Abs_ 
            Decimal_
            NoOf_ = 2 : InVar_ 2 
            
            FillColour : Colour0 = 9 Colour1 = -1 
         TextBox_ ( 0.72 , -0.92 ) ( 1.44 , -0.82 ) 
            Real_Value
            Enable_ = True : InVar_ "EnableControl" Variable = 0.0 : OutVar_ 
            "RecipeControl.RequestRecipe.ScaleFactor" LeftAligned Abs_ Decimal_
            NoOf_ = 2 : InVar_ 2 
            
            FillColour : Colour0 = 9 Colour1 = -1 
         ComBut_ ( 3.4 , -1.06 ) ( 3.5 , -0.96 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "ExecuteRequestOpRec" SetAction
            Abs_ 
         ComBut_ ( 1.34 , -1.02 ) ( 1.44 , -0.92 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "ExecuteRequestRecipe" SetAction
            Abs_ 
         ComBut_ ( 1.34 , -1.14 ) ( 1.44 , -1.04 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "RecipeControl.ActivateOperation.Execute" SetAction
            Abs_ 
         ComBut_ ( 1.38 , -1.36 ) ( 1.48 , -1.26 ) 
            Bool_Value
            Enable_ = True : InVar_ False Variable = False : OutVar_ 
            "RecipeStatus.AllocationInhibited" ResetAction
            Abs_ SetApp_
            
         ComBut_ ( 2.16 , -0.26 ) ( 2.26 , -0.16 ) 
            Bool_Value
            Enable_ = True : InVar_ False Variable = False : OutVar_ 
            "UnitStatus.Inhibited" ResetAction
            Abs_ SetApp_
            
         ComBut_ ( 1.38 , -1.36 ) ( 1.48 , -1.26 ) 
            Bool_Value
            Variable = False : OutVar_ "RecipeControl.AllowAllocation" Visible_ 
            = True : (EnableControl AND RecipeStatus.AllocationInhibited) 
            ToggleAction
            Abs_ SetApp_
            
         ComBut_ ( 2.16 , -0.26 ) ( 2.26 , -0.16 ) 
            Bool_Value
            Variable = False : OutVar_ "UnitControl.ReleaseUnit" Visible_ = 
            True : (EnableControl AND UnitStatus.Inhibited) ToggleAction
            Abs_ SetApp_
            
         ComBut_ ( 1.38 , -1.26 ) ( 1.48 , -1.16 ) 
            Bool_Value
            Enable_ = True : InVar_ False Variable = False : OutVar_ 
            "RecipeStatus.AllocationInhibited" SetAction
            Abs_ SetApp_
            
         ComBut_ ( 2.16 , -0.16 ) ( 2.26 , -0.06 ) 
            Bool_Value
            Enable_ = True : InVar_ False Variable = False : OutVar_ 
            "UnitStatus.Inhibited" SetAction
            Abs_ SetApp_
            
         ComBut_ ( 1.38 , -1.26 ) ( 1.48 , -1.16 ) 
            Bool_Value
            Variable = False : OutVar_ "RecipeControl.InhibitAllocation" 
            Visible_ = True : (EnableControl AND  NOT RecipeStatus.
            AllocationInhibited) ToggleAction
            Abs_ SetApp_
            
         ComBut_ ( 2.16 , -0.16 ) ( 2.26 , -0.06 ) 
            Bool_Value
            Variable = False : OutVar_ "UnitControl.InhibitUnit" Visible_ = 
            True : (EnableControl AND  NOT UnitStatus.Inhibited) ToggleAction
            Abs_ SetApp_
            
         ComButProc_ ( 3.35 , -0.55 ) ( 3.49 , -0.41 ) 
            ToggleWindow
            "" : InVar_ LitString "-+OpRecipeEditor*OpRecipeEditorCore*Info" "" 
            : InVar_ LitString "Editor" False 0.0 0.0 0.0 : InVar_ 0.96 0.0 
            False : InVar_ True 0 0 False 0 
            Variable = 0.0 
         CheckBox_ ( 2.33 , -0.26 ) ( 3.28 , -0.16 ) 
            Bool_Value
            Variable = False : OutVar_ "Attributes.AgitatorPresent" TextObject 
            = "" : InVar_ LitString "Agitator present" 
            
            FillColour : Colour1 = -1 
         TextBox_ ( 2.68 , -0.16 ) ( 3.04 , -0.06 ) 
            Int_Value
            Variable = 0 : OutVar_ "Attributes.MinVolume" LeftAligned Abs_ 
            Digits_
            
            FillColour : Colour0 = 9 Colour1 = -1 
         TextBox_ ( 2.07 , -1.96 ) ( 2.17 , -1.86 ) 
            Int_Value
            Enable_ = True : InVar_ "EnableControl" Variable = 0 : OutVar_ 
            "OpRecipeControl.ActiveStep1.Next.DesiredResult" CenterAligned Abs_ 
            Digits_
            
            FillColour : Colour0 = 9 Colour1 = -1 
         TextBox_ ( 2.71 , -1.96 ) ( 2.81 , -1.86 ) 
            Int_Value
            Enable_ = True : InVar_ "EnableControl" Variable = 0 : OutVar_ 
            "OpRecipeControl.ActiveStep3.Next.DesiredResult" CenterAligned Abs_ 
            Digits_
            
            FillColour : Colour0 = 9 Colour1 = -1 
         TextBox_ ( 3.35 , -1.96 ) ( 3.45 , -1.86 ) 
            Int_Value
            Enable_ = True : InVar_ "EnableControl" Variable = 0 : OutVar_ 
            "OpRecipeControl.ActiveStep5.Next.DesiredResult" CenterAligned Abs_ 
            Digits_
            
            FillColour : Colour0 = 9 Colour1 = -1 
         TextBox_ ( 2.39 , -1.96 ) ( 2.49 , -1.86 ) 
            Int_Value
            Enable_ = True : InVar_ "EnableControl" Variable = 0 : OutVar_ 
            "OpRecipeControl.ActiveStep2.Next.DesiredResult" CenterAligned Abs_ 
            Digits_
            
            FillColour : Colour0 = 9 Colour1 = -1 
         TextBox_ ( 3.03 , -1.96 ) ( 3.13 , -1.86 ) 
            Int_Value
            Enable_ = True : InVar_ "EnableControl" Variable = 0 : OutVar_ 
            "OpRecipeControl.ActiveStep4.Next.DesiredResult" CenterAligned Abs_ 
            Digits_
            
            FillColour : Colour0 = 9 Colour1 = -1 
         ComBut_ ( 2.19 , -0.86 ) ( 2.29 , -0.76 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "OpRecipeControl.StartRecipe" ToggleAction
            Abs_ 
         ComBut_ ( 2.19 , -0.96 ) ( 2.29 , -0.86 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "OpRecipeControl.StopRecipe" ToggleAction
            Abs_ 
         ComBut_ ( 2.19 , -1.06 ) ( 2.29 , -0.96 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "OpRecipeControl.CancelRecipe" ToggleAction
            Abs_ 
         ComBut_ ( 2.07 , -1.52 ) ( 2.17 , -1.42 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "OpRecipeControl.ActiveStep1.Start" ToggleAction
            Abs_ 
         ComBut_ ( 1.18 , -1.6 ) ( 1.28 , -1.5 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "RecipeControl.StartNextOp1" Visible_ = True : InVar_ 
            "ShowAllocStatus1" ToggleAction
            Abs_ 
         ComBut_ ( 1.28 , -1.6 ) ( 1.38 , -1.5 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "RecipeControl.OmitNextOp1" Visible_ = True : InVar_ 
            "ShowAllocStatus1" ToggleAction
            Abs_ 
         ComBut_ ( 1.28 , -1.7 ) ( 1.38 , -1.6 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "RecipeControl.OmitNextOp2" Visible_ = True : InVar_ 
            "ShowAllocStatus2" ToggleAction
            Abs_ 
         ComBut_ ( 1.28 , -1.8 ) ( 1.38 , -1.7 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "RecipeControl.OmitNextOp3" Visible_ = True : InVar_ 
            "ShowAllocStatus3" ToggleAction
            Abs_ 
         ComBut_ ( 1.28 , -1.9 ) ( 1.38 , -1.8 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "RecipeControl.OmitNextOp4" Visible_ = True : InVar_ 
            "ShowAllocStatus4" ToggleAction
            Abs_ 
         ComBut_ ( 1.28 , -2.0 ) ( 1.38 , -1.9 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "RecipeControl.OmitNextOp5" Visible_ = True : InVar_ 
            "ShowAllocStatus5" ToggleAction
            Abs_ 
         ComBut_ ( 1.28 , -2.1 ) ( 1.38 , -2.0 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "RecipeControl.OmitJumpOp" Visible_ = True : InVar_ 
            "ShowAllocStatusJump" ToggleAction
            Abs_ 
         ComBut_ ( 1.18 , -1.7 ) ( 1.28 , -1.6 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "RecipeControl.StartNextOp2" Visible_ = True : InVar_ 
            "ShowAllocStatus2" ToggleAction
            Abs_ 
         ComBut_ ( 1.18 , -1.8 ) ( 1.28 , -1.7 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "RecipeControl.StartNextOp3" Visible_ = True : InVar_ 
            "ShowAllocStatus3" ToggleAction
            Abs_ 
         ComBut_ ( 1.18 , -1.9 ) ( 1.28 , -1.8 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "RecipeControl.StartNextOp4" Visible_ = True : InVar_ 
            "ShowAllocStatus4" ToggleAction
            Abs_ 
         ComBut_ ( 1.18 , -2.0 ) ( 1.28 , -1.9 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "RecipeControl.StartNextOp5" Visible_ = True : InVar_ 
            "ShowAllocStatus5" ToggleAction
            Abs_ 
         ComBut_ ( 1.18 , -2.1 ) ( 1.28 , -2.0 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "RecipeControl.StartJumpOp" Visible_ = True : InVar_ 
            "ShowAllocStatusJump" ToggleAction
            Abs_ 
         ComBut_ ( 0.72 , -1.26 ) ( 0.82 , -1.16 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "RecipeControl.DeactivateOperation" ToggleAction
            Abs_ 
         ComBut_ ( 0.72 , -1.36 ) ( 0.82 , -1.26 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "RecipeControl.CancelRecipe" ToggleAction
            Abs_ 
         ComBut_ ( 2.71 , -1.52 ) ( 2.81 , -1.42 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "OpRecipeControl.ActiveStep3.Start" ToggleAction
            Abs_ 
         ComBut_ ( 3.35 , -1.52 ) ( 3.45 , -1.42 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "OpRecipeControl.ActiveStep5.Start" ToggleAction
            Abs_ 
         ComBut_ ( 2.39 , -1.52 ) ( 2.49 , -1.42 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "OpRecipeControl.ActiveStep2.Start" ToggleAction
            Abs_ 
         ComBut_ ( 3.03 , -1.52 ) ( 3.13 , -1.42 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "OpRecipeControl.ActiveStep4.Start" ToggleAction
            Abs_ 
         ComBut_ ( 2.07 , -1.62 ) ( 2.17 , -1.52 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "OpRecipeControl.ActiveStep1.Stop" ToggleAction
            Abs_ 
         ComBut_ ( 2.71 , -1.62 ) ( 2.81 , -1.52 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "OpRecipeControl.ActiveStep3.Stop" ToggleAction
            Abs_ 
         ComBut_ ( 3.35 , -1.62 ) ( 3.45 , -1.52 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "OpRecipeControl.ActiveStep5.Stop" ToggleAction
            Abs_ 
         ComBut_ ( 2.39 , -1.62 ) ( 2.49 , -1.52 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "OpRecipeControl.ActiveStep2.Stop" ToggleAction
            Abs_ 
         ComBut_ ( 3.03 , -1.62 ) ( 3.13 , -1.52 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "OpRecipeControl.ActiveStep4.Stop" ToggleAction
            Abs_ 
         ComBut_ ( 2.07 , -1.72 ) ( 2.17 , -1.62 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "OpRecipeControl.ActiveStep1.Pause" ToggleAction
            Abs_ 
         ComBut_ ( 2.71 , -1.72 ) ( 2.81 , -1.62 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "OpRecipeControl.ActiveStep3.Pause" ToggleAction
            Abs_ 
         ComBut_ ( 3.35 , -1.72 ) ( 3.45 , -1.62 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "OpRecipeControl.ActiveStep5.Pause" ToggleAction
            Abs_ 
         ComBut_ ( 2.39 , -1.72 ) ( 2.49 , -1.62 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "OpRecipeControl.ActiveStep2.Pause" ToggleAction
            Abs_ 
         ComBut_ ( 3.03 , -1.72 ) ( 3.13 , -1.62 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "OpRecipeControl.ActiveStep4.Pause" ToggleAction
            Abs_ 
         ComBut_ ( 2.07 , -1.82 ) ( 2.17 , -1.72 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "OpRecipeControl.ActiveStep1.Continue" ToggleAction
            Abs_ 
         ComBut_ ( 2.71 , -1.82 ) ( 2.81 , -1.72 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "OpRecipeControl.ActiveStep3.Continue" ToggleAction
            Abs_ 
         ComBut_ ( 3.35 , -1.82 ) ( 3.45 , -1.72 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "OpRecipeControl.ActiveStep5.Continue" ToggleAction
            Abs_ 
         ComBut_ ( 2.39 , -1.82 ) ( 2.49 , -1.72 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "OpRecipeControl.ActiveStep2.Continue" ToggleAction
            Abs_ 
         ComBut_ ( 3.03 , -1.82 ) ( 3.13 , -1.72 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "OpRecipeControl.ActiveStep4.Continue" ToggleAction
            Abs_ 
         ComBut_ ( 2.07 , -2.06 ) ( 2.17 , -1.96 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "OpRecipeControl.ActiveStep1.Next.Execute" ToggleAction
            Abs_ 
         ComBut_ ( 2.71 , -2.06 ) ( 2.81 , -1.96 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "OpRecipeControl.ActiveStep3.Next.Execute" ToggleAction
            Abs_ 
         ComBut_ ( 3.35 , -2.06 ) ( 3.45 , -1.96 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "OpRecipeControl.ActiveStep5.Next.Execute" ToggleAction
            Abs_ 
         ComBut_ ( 2.39 , -2.06 ) ( 2.49 , -1.96 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "OpRecipeControl.ActiveStep2.Next.Execute" ToggleAction
            Abs_ 
         ComBut_ ( 3.03 , -2.06 ) ( 3.13 , -1.96 ) 
            Bool_Value
            Enable_ = True : InVar_ "EnableControl" Variable = False : OutVar_ 
            "OpRecipeControl.ActiveStep4.Next.Execute" ToggleAction
            Abs_ 
      
      ENDDEF (*Info*);
      
   
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   Two_Layers_ LayerLimit_ = 0.95
   Zoomable
   GraphObjects :
      RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
         OutlineColour : Colour0 = -3 
      TextObject ( -1.0 , 0.8 ) ( 1.0 , 0.96 ) 
         "UnitName" VarName Width_ = 5 : InVar_ 5  ValueFraction = 2  
         Layer_ = 2
         OutlineColour : Colour0 = -3 
   InteractObjects :
      ProcedureInteract ( -0.8 , -0.8 ) ( 0.8 , 0.8 ) 
         ToggleWindow
         "" : InVar_ LitString "+Info" "" False : InVar_ True 0.0 : InVar_ 0.1 
         0.0 : InVar_ -0.1 0.0 : InVar_ 0.6 0.0 False 0 0 False 0 
         Layer_ = 1
         Variable = 0.0 
   
   ModuleCode
   EQUATIONBLOCK Start_Code COORD 0.76, -0.22 OBJSIZE 0.2, 0.2
   Layer_ = 2 :
      ClearString(FilterTag);
      Concatenate(UnitName, StarString, FilterTag, DebugStatus);
      ClearString(Tag);
      Concatenate(UnitName, Item, Tag, DebugStatus);
      (* Set the InteractionPar to the DirectoryList *);
      CopyVariable(A, InteractionPar.TypeOfFile, Status);
   EQUATIONBLOCK Code COORD 0.76, -0.46 OBJSIZE 0.2, 0.2
   Layer_ = 2 :
      ShowAllocStatus1 = RecipeStatus.NextOperation1.AllocationActivity <> 0;
      ShowAllocStatus2 = RecipeStatus.NextOperation2.AllocationActivity <> 0;
      ShowAllocStatus3 = RecipeStatus.NextOperation3.AllocationActivity <> 0;
      ShowAllocStatus4 = RecipeStatus.NextOperation4.AllocationActivity <> 0;
      ShowAllocStatus5 = RecipeStatus.NextOperation5.AllocationActivity <> 0;
      ShowAllocStatusJump = RecipeStatus.JumpOperation.AllocationActivity <> 0;
      Error = Error1 OR Error10 OR Error11 OR Error12 OR Error13 OR Error14 OR 
         Error15 OR Error16;
      Warning = WarningUnitSuper OR Warning10 OR Warning11 OR Warning12 OR 
         Warning13 OR Warning14 OR Warning15;
   
   ENDDEF (*Tank*);
   
   PhaseList
   (* 1. Function
      
      2. Relation to other modules
      
      3. Comments on connection list
      
      4. Operators interface
      4.1 Pop-up windows
      
      4.2 Logging of operator interaction
      
      4.3 Modules accessable through pathstring
      "ModuleName*SelectButton"
      "ModuleName*Info"
      
      5. Scangroups
      Inherit/ProgStationData.GroupProg
      
      6. Opsave and secure
      
      7. Advice for usage *)
    = MODULEDEFINITION DateCode_ 103013416
   MODULEPARAMETERS
      PhaseDisplay "OUT <=>": PhaseDisplayType ;
   SUBMODULES
      Icon Invocation
         ( -1.0 , -1.0 , 0.0 , 2.0 , 2.0 
          Layer_ = 1
          ZoomLimits = 0.5 0.01 ) : PhaseNameIcon;
      
      Info Invocation
         ( -0.96 , 0.76 , 0.0 , 0.76 , 0.76 
          Layer_ = 2
          ) : MODULEDEFINITION DateCode_ 681845510 ( Frame_Module ) 
      SUBMODULES
         Phase4 Invocation
            ( 2.98023E-08 , -0.56 , 0.0 , 0.5 , 0.1 
             ) : SelectPhase (
         PhaseName => "Agitation2", 
         FormulaType => 2, 
         PhaseDisplay => PhaseDisplay, 
         DeleteWindow => PhaseDisplay.DisplayWindow);
         
         Phase5 Invocation
            ( 2.98023E-08 , -0.66 , 0.0 , 0.5 , 0.1 
             ) : SelectPhase (
         PhaseName => "Filling", 
         FormulaType => 3, 
         PhaseDisplay => PhaseDisplay, 
         DeleteWindow => PhaseDisplay.DisplayWindow);
         
         Phase6 Invocation
            ( 2.6077E-08 , -0.76 , 0.0 , 0.5 , 0.1 
             ) : SelectPhase (
         PhaseName => "Ramping", 
         FormulaType => 2, 
         PhaseDisplay => PhaseDisplay, 
         DeleteWindow => PhaseDisplay.DisplayWindow);
         
         Phase1 Invocation
            ( 3.72529E-08 , -0.26 , 0.0 , 0.5 , 0.1 
             ) : SelectPhase (
         PhaseName => "Dummy", 
         FormulaType => 0, 
         PhaseDisplay => PhaseDisplay, 
         DeleteWindow => PhaseDisplay.DisplayWindow);
         
         Phase2 Invocation
            ( 3.72529E-08 , -0.36 , 0.0 , 0.5 , 0.1 
             ) : SelectPhase (
         PhaseName => "Heating", 
         FormulaType => 1, 
         PhaseDisplay => PhaseDisplay, 
         DeleteWindow => PhaseDisplay.DisplayWindow);
         
         Phase3 Invocation
            ( 3.35276E-08 , -0.46 , 0.0 , 0.5 , 0.1 
             ) : SelectPhase (
         PhaseName => "Agitation1", 
         FormulaType => 1, 
         PhaseDisplay => PhaseDisplay, 
         DeleteWindow => PhaseDisplay.DisplayWindow);
         
      
      ModuleDef
      ClippingBounds = ( 0.0 , -0.76 ) ( 0.5 , 0.0 )
      GraphObjects :
         RectangleObject ( 0.5 , 0.0 ) ( -4.84288E-08 , -0.76 ) 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.0 , -0.16 ) ( 0.5 , 0.0 ) 
            "Phases" 
            OutlineColour : Colour0 = -3 
      
      ENDDEF (*Info*);
      
      BatchWindowControl Invocation
         ( 0.64 , -0.68 , 0.0 , 0.2 , 0.2 
          Layer_ = 2
          ) : BatchWindowControl (
      ToggleWindow => PhaseDisplay.DisplayWindow, 
      DeleteWindow => PhaseDisplay.DeleteWindow, 
      WindowPath => "-+Info", 
      RelPos => True, 
      xSize => 0.12, 
      ProgStationData => GLOBAL ProgStationData);
      
   
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   Two_Layers_ LayerLimit_ = 0.95
   Zoomable
   GraphObjects :
      RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
         OutlineColour : Colour0 = -3 
      TextObject ( 0.26 , -0.08 ) ( 0.94 , 0.06 ) 
         "PhaseDisplay" 
         ConnectionNode ( 1.0 , 0.0 ) 
         
         OutlineColour : Colour0 = -3 
      TextObject ( -1.0 , 0.8 ) ( 1.0 , 0.96 ) 
         "PhaseNames" 
         Layer_ = 1
         OutlineColour : Colour0 = -3 
      RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = -2 
      RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      TextObject ( -1.0 , 0.8 ) ( 1.0 , 0.96 ) 
         "PhaseNames" 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
   InteractObjects :
      SimpleInteract ( -0.8 , -0.8 ) ( 0.8 , 0.8 ) 
         Bool_Value
         Layer_ = 1
         Variable = False : OutVar_ "PhaseDisplay.DisplayWindow" ToggleAction 
         
   
   ENDDEF (*PhaseList*);
   
   RecipeEditor = MODULEDEFINITION DateCode_ 287344580
   MODULEPARAMETERS
      Name "IN Module instance name": identstring  := "Module name";
      RecipeEditConnection 
      "IN <=> NODE Connection to RecipeManager, OperationControlExt and/or UnitManager"
      : RecipeEditConnType ;
      WindowDisplayed "OUT true if editor window is displayed.": boolean  := 
      Default;
      EnableEdit "IN Enable edit", EnableEditRestricted 
      "IN Enable restricted edit": boolean  := True;
      EditSeverity "IN Edit interaction severity 0-127": integer  := 0;
      EditClass "IN Edit interaction class 1-98": integer  := 1;
      EnableControl "IN Enable recipe control": boolean  := True;
      ControlSeverity "IN Recipe control interaction severity 0-127": integer  
      := 0;
      ControlClass "IN Recipe control interaction class 1-98": integer  := 1;
      OpRecipeRestoreConn "IN Connection to restore of operation recipe": 
      OpRecipeRestConnType ;
   LOCALVARIABLES
      OperationDisplay: OperationDisplayType ;
      OpRecipeEditConn: OpRecipeEditConnType ;
   SUBMODULES
      Icon Invocation
         ( -1.0 , -1.0 , 0.0 , 2.0 , 2.0 
          Layer_ = 1
          ZoomLimits = 0.5 0.01 ) : recipeeditoricon;
      
      OperationDisplay Invocation
         ( -0.08 , -0.08 , 0.0 , 0.16 , 0.16 
          Layer_ = 2
          ) : OperationMaster (
      OperationDisplay => OperationDisplay, 
      OpRecipeEditConn => OpRecipeEditConn, 
      OpRecipeRestoreConn => OpRecipeRestoreConn, 
      EnableEdit => EnableEdit);
      
      OpRecipeEditor Invocation
         ( -0.68 , -0.08 , 0.0 , 0.16 , 0.16 
          Layer_ = 2
          ) : OpRecipeEditor (
      OpRecipeEditConn => OpRecipeEditConn, 
      WindowDisplayed => WindowDisplayed, 
      EnableEdit => False, 
      EnableEditRestricted => False, 
      EnableControl => False);
      
      RecipeEditor Invocation
         ( 0.64 , -0.08 , 0.0 , 0.16 , 0.16 
          Layer_ = 2
          ) : RecipeEditorCore (
      Name => "RecipeEditor", 
      RecipeEditConnection => RecipeEditConnection, 
      OperationDisplay => OperationDisplay, 
      WindowDisplayed => WindowDisplayed, 
      EnableEdit => EnableEdit, 
      EnableEditRestricted => EnableEditRestricted, 
      EditSeverity => EditSeverity, 
      EditClass => EditClass, 
      EnableControl => EnableControl, 
      ControlSeverity => ControlSeverity, 
      ControlClass => ControlClass);
      
      HeaderExtension Invocation
         ( 0.28 , -0.24 , 0.0 , 0.08 , 0.08 
          Layer_ = 2
          ) : RecHeaderExt (
      Recipe => RecipeEditConnection.Recipe);
      
   
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   Two_Layers_ LayerLimit_ = 0.95
   Zoomable
   GraphObjects :
      TextObject ( 0.86 , 0.1 ) ( 0.1 , 0.22 ) 
         "RecipeEditConnection" 
         ConnectionNode ( 1.0 , 2.98023E-08 ) 
         LeftAligned 
         OutlineColour : Colour0 = -3 
      RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
         OutlineColour : Colour0 = -3 
      TextObject ( -0.96 , 0.6 ) ( 0.96 , 0.8 ) 
         "Name" VarName Width_ = 5 : InVar_ 5  ValueFraction = 2  
         Layer_ = 1
         OutlineColour : Colour0 = -3 
      RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = -2 
      RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      TextObject ( -1.0 , 0.8 ) ( 1.0 , 0.96 ) 
         "Name" VarName Width_ = 5 : InVar_ 5  ValueFraction = 3  
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      TextObject ( -0.36 , 0.08 ) ( 0.2 , 0.16 ) 
         "OperationMaster" 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      TextObject ( -1.0 , 0.08 ) ( -0.36 , 0.16 ) 
         "OperationRecipeEditor" 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      TextObject ( 0.36 , 0.08 ) ( 0.92 , 0.16 ) 
         "RecipeEditorCore" 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( 0.36 , -0.24 ) 
         ( 0.48 , -0.24 ) 
         Layer_ = 2
   
   ENDDEF (*RecipeEditor*);
   
   OpRecipeEditor
   (* 1. Function
      
      2. Relation to other modules
      
      3. Comments on connection list
      
      4. Operators interface
      4.1 Pop-up windows
      
      4.2 Logging of operator interaction
      
      4.3 Modules accessable through pathstring
      "ModuleName*SelectButton"
      "ModuleName*Info"
      
      5. Scangroups
      Inherit/ProgStationData.GroupProg
      
      6. Opsave and secure
      
      7. Advice for usage *)
    = MODULEDEFINITION DateCode_ 0
   MODULEPARAMETERS
      Name "IN Module instance name": string  := "Operation recipe editor";
      OpRecipeEditConn "IN/OUT": OpRecipeEditConnType ;
      OpRecipeControl "OUT": OpRecipeControlType  := Default;
      OpRecipeStatus "IN": OpRecipeStatusType  := Default;
      WindowDisplayed "OUT": boolean  := Default;
      EnableEdit "IN ", EnableEditRestricted "IN": boolean  := True;
      EditSeverity "IN": integer  := 0;
      EditClass "IN": integer  := 1;
      EnableControl "IN": boolean  := True;
      ControlSeverity "IN  severity": integer  := 0;
      ControlClass "IN  class": integer  := 1;
   LOCALVARIABLES
      Formula1Display: Formula1DisplayType ;
      Formula2Display: Formula2DisplayType ;
      Formula3Display: Formula3DisplayType ;
   SUBMODULES
      Icon Invocation
         ( -1.0 , -1.0 , 0.0 , 2.0 , 2.0 
          Layer_ = 1
          ) : RecipeEditorIcon;
      
      OpRecipeEditorCore Invocation
         ( 0.2 , -0.24 , 0.0 , 0.16 , 0.16 
          Layer_ = 2
          ) : OpRecipeEditorCore (
      Name => Name, 
      OpRecipeEditConn => OpRecipeEditConn, 
      OpRecipeControl => OpRecipeControl, 
      OpRecipeStatus => OpRecipeStatus, 
      WindowDisplayed => WindowDisplayed, 
      EnableEdit => EnableEdit, 
      EnableEditRestricted => EnableEditRestricted, 
      EditSeverity => EditSeverity, 
      EditClass => EditClass, 
      EnableControl => EnableControl, 
      ControlSeverity => ControlSeverity, 
      ControlClass => ControlClass);
      
      PhaseNames Invocation
         ( -0.44 , 0.12 , 0.0 , 0.08 , 0.08 
          Layer_ = 2
          ) : PhaseList;
      
      Agitation1Display Invocation
         ( -0.44 , -0.08 , 0.0 , 0.08 , 0.08 
          Layer_ = 2
          ) : Agitation1Display (
      WarningColour => 39);
      
      PhaseDisplay12 Invocation
         ( -0.6 , -0.08 , 0.0 , 0.08 , 0.08 
          Layer_ = 2
          ) : HeaterDisplay (
      WarningColour => 39);
      
      RampingDisplay Invocation
         ( -0.44 , -0.24 , 0.0 , 0.08 , 0.08 
          Layer_ = 2
          ) : RampingDisplay (
      WarningColour => 39);
      
      Agitation2Display Invocation
         ( -0.6 , -0.24 , 0.0 , 0.08 , 0.08 
          Layer_ = 2
          ) : Agitation2Display (
      WarningColour => 39);
      
      FillingDisplay Invocation
         ( -0.44 , -0.4 , 0.0 , 0.08 , 0.08 
          Layer_ = 2
          ) : FillingDisplay (
      WarningColour => 39);
      
      HeaderExtension Invocation
         ( -0.44 , -0.6 , 0.0 , 0.08 , 0.08 
          Layer_ = 2
          ) : OpRecHeaderExt (
      OperationRecipe => OpRecipeEditConn.OperationRecipe);
      
   
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   Two_Layers_ LayerLimit_ = 0.95
   Zoomable
   GraphObjects :
      RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      TextObject ( -1.0 , 0.8 ) ( 1.0 , 0.96 ) 
         "Name" VarName Width_ = 5 : InVar_ 5  ValueFraction = 3  
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      TextObject ( 0.0 , -0.44 ) ( 0.48 , -0.52 ) 
         "OpRecipeEditorCore" 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.36 , 0.12 ) 
         ( -0.04 , 0.12 ) ( 0.04 , -0.08 ) 
         Layer_ = 2
         OutlineColour : Colour0 = 2 Colour1 = 2 
      PolygonObject Polyline Connection ( -0.36 , -0.6 ) 
         ( -0.04 , -0.6 ) ( 0.04 , -0.4 ) 
         Layer_ = 2
         OutlineColour : Colour0 = 2 Colour1 = 2 
      TextObject ( -0.12 , -0.16 ) ( -0.32 , -0.12 ) 
         "Formula1Display" 
         ConnectionNode ( -0.2 , -0.08 ) 
         LeftAligned 
         Layer_ = 2
         OutlineColour : Colour0 = 2 Colour1 = 2 
      TextObject ( -0.12 , -0.32 ) ( -0.32 , -0.28 ) 
         "Formula2Display" 
         ConnectionNode ( -0.2 , -0.24 ) 
         LeftAligned 
         Layer_ = 2
         OutlineColour : Colour0 = 2 Colour1 = 2 
      TextObject ( -0.12 , -0.48 ) ( -0.32 , -0.44 ) 
         "Formula3Display" 
         ConnectionNode ( -0.2 , -0.4 ) 
         LeftAligned 
         Layer_ = 2
         OutlineColour : Colour0 = 2 Colour1 = 2 
      PolygonObject Polyline Connection ( -0.2 , -0.08 ) 
         ( -0.08 , -0.08 ) ( -0.08 , -0.16 ) ( 0.04 , -0.16 ) 
         Layer_ = 2
         OutlineColour : Colour0 = 2 Colour1 = 2 
      PolygonObject Polyline Connection ( -0.2 , -0.24 ) 
         ( 0.04 , -0.24 ) 
         Layer_ = 2
         OutlineColour : Colour0 = 2 Colour1 = 2 
      PolygonObject Polyline Connection ( -0.2 , -0.4 ) 
         ( -0.08 , -0.4 ) ( -0.08 , -0.32 ) ( 0.04 , -0.32 ) 
         Layer_ = 2
         OutlineColour : Colour0 = 2 Colour1 = 2 
      PolygonObject Polyline Connection ( -0.36 , -0.4 ) 
         ( -0.2 , -0.4 ) 
         Layer_ = 2
         OutlineColour : Colour0 = 2 Colour1 = 2 
      PolygonObject Polyline Connection ( -0.52 , -0.24 ) 
         ( -0.2 , -0.24 ) 
         Layer_ = 2
         OutlineColour : Colour0 = 2 Colour1 = 2 
      PolygonObject Polyline Connection ( -0.36 , -0.24 ) 
         ( -0.2 , -0.24 ) 
         Layer_ = 2
         OutlineColour : Colour0 = 2 Colour1 = 2 
      PolygonObject Polyline Connection ( -0.52 , -0.08 ) 
         ( -0.2 , -0.08 ) 
         Layer_ = 2
         OutlineColour : Colour0 = 2 Colour1 = 2 
      PolygonObject Polyline Connection ( -0.36 , -0.08 ) 
         ( -0.2 , -0.08 ) 
         Layer_ = 2
         OutlineColour : Colour0 = 2 Colour1 = 2 
   InteractObjects :
      ProcedureInteract ( -0.8 , -0.8 ) ( 0.8 , 0.8 ) 
         ToggleWindow
         "" : InVar_ LitString "++Info" "" False : InVar_ True 0.0 : InVar_ 0.1 
         0.0 : InVar_ -0.1 0.0 : InVar_ 0.24 0.0 False 0 0 False 0 
         Layer_ = 1
         Variable = 0.0 
   
   ENDDEF (*OpRecipeEditor*);
   
   OpRecHeaderExt
   (* 1. Function
      
      2. Relation to other modules
      
      3. Comments on connection list
      
      4. Operators interface
      4.1 Pop-up windows
      
      4.2 Logging of operator interaction
      
      4.3 Modules accessable through pathstring
      "ModuleName*SelectButton"
      "ModuleName*Info"
      
      5. Scangroups
      Inherit/ProgStationData.GroupProg
      
      6. Opsave and secure
      
      7. Advice for usage *)
    = MODULEDEFINITION DateCode_ 380454133
   MODULEPARAMETERS
      OperationRecipe "IN/OUT": OperationRecipeType ;
      HeaderExtDisplay "IN/OUT": HeaderExtDisplayType ;
   LOCALVARIABLES
      ToggleWindow: boolean ;
   SUBMODULES
      Icon Invocation
         ( -1.0 , -1.0 , 0.0 , 2.00039 , 2.00101 
          Layer_ = 1
          ZoomLimits = 0.5 0.01 ) : HeaderExtIcon;
      
      BatchWindowControl Invocation
         ( 0.72 , -0.77997 , 0.0 , 0.11999 , 0.12 
          Layer_ = 2
          ) : BatchWindowControl (
      ToggleWindow => HeaderExtDisplay.DisplayWindow, 
      WindowPath => "-+Page1+Info", 
      RelPos => True, 
      xSize => 0.24, 
      ProgStationData => GLOBAL ProgStationData);
      
      HeaderExtControl Invocation
         ( 0.42 , -0.77997 , 0.0 , 0.11999 , 0.12 
          Layer_ = 2
          ) : HeaderExtControl (
      Value => HeaderExtDisplay.HeaderExtPresent);
      
      Page1 Invocation
         ( -0.9 , -0.8 , 0.0 , 1.12 , 1.12 
          Layer_ = 2
          ) : MODULEDEFINITION DateCode_ 380148950 ( Frame_Module ) 
      SUBMODULES
         Info Invocation
            ( 0.1 , 1.2 , 0.0 , 0.64 , 0.64007 
             ) : MODULEDEFINITION DateCode_ 380202935 ( Frame_Module ) 
         SUBMODULES
            Par1 Invocation
               ( 0.4 , -0.3 , -7.09579E-09 , 0.6 , 0.10714 
                ) : BatchStringMenu (
            Value => OperationRecipe.Header.Extension.Ext1, 
            InteractEnable => HeaderExtDisplay.EnableInteraction);
            
            Par2 Invocation
               ( 0.4 , -0.4 , -7.09579E-09 , 0.6 , 0.10714 
                ) : BatchStringMenu (
            Value => OperationRecipe.Header.Extension.Ext2, 
            InteractEnable => HeaderExtDisplay.EnableInteraction);
            
            Par3 Invocation
               ( 0.4 , -0.5 , -7.09579E-09 , 0.6 , 0.10714 
                ) : BatchStringMenu (
            Value => OperationRecipe.Header.Extension.Ext3, 
            InteractEnable => HeaderExtDisplay.EnableInteraction);
            
            Par4 Invocation
               ( 0.4 , -0.6 , -7.09579E-09 , 0.6 , 0.10714 
                ) : BatchStringMenu (
            Value => OperationRecipe.Header.Extension.Ext4, 
            InteractEnable => HeaderExtDisplay.EnableInteraction);
            
         
         ModuleDef
         ClippingBounds = ( 0.0 , -0.6 ) ( 1.0 , 0.0 )
         GraphObjects :
            RectangleObject ( -1.19209E-07 , -2.08616E-07 ) 
               ( 1.0 , -0.6 ) 
               OutlineColour : Colour0 = -3 
               FillColour : Colour1 = 51 
            TextObject ( -1.49012E-08 , -0.16 ) ( 1.0 , 0.0 ) 
               "HeaderExtension" 
               OutlineColour : Colour0 = -3 
            TextObject ( 0.0 , -0.3 ) ( 0.4 , -0.2 ) 
               "Ext1:" LeftAligned 
               OutlineColour : Colour0 = -3 
            TextObject ( -3.72529E-09 , -0.4 ) ( 0.4 , -0.3 ) 
               "Ext2:" LeftAligned 
               OutlineColour : Colour0 = -3 
            TextObject ( -3.72529E-09 , -0.5 ) ( 0.4 , -0.4 ) 
               "Ext3:" LeftAligned 
               OutlineColour : Colour0 = -3 
            TextObject ( -3.72529E-09 , -0.6 ) ( 0.4 , -0.5 ) 
               "Ext4:" LeftAligned 
               OutlineColour : Colour0 = -3 
         
         ENDDEF (*Info*);
         
      
      ModuleDef
      ClippingBounds = ( -2.98023E-08 , 0.0 ) ( 1.0 , 1.3 )
      
      ENDDEF (*Page1*);
      
   
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   Two_Layers_ LayerLimit_ = 0.95
   Zoomable
   GraphObjects :
      RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = -2 
      TextObject ( 2.23517E-08 , -0.06 ) ( 0.98 , 0.08 ) 
         "HeaderExtDisplay" 
         ConnectionNode ( 1.0 , 0.0 ) 
         
         OutlineColour : Colour0 = -3 
      RectangleObject ( 1.0 , 1.0002 ) ( -1.0 , -1.0 ) 
         Layer_ = 1
         OutlineColour : Colour0 = -3 
      TextObject ( -1.0 , 0.80018 ) ( 1.0 , 0.9602 ) 
         "HeaderExtension" 
         Layer_ = 1
         OutlineColour : Colour0 = -3 
      RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0002 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = -2 
      TextObject ( -1.0 , 0.80018 ) ( 1.0 , 0.9602 ) 
         "HeaderExtension" 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
   InteractObjects :
      SimpleInteract ( -0.8 , -0.79998 ) ( 0.8 , 0.80018 ) 
         Bool_Value
         Layer_ = 1
         Variable = False : OutVar_ "HeaderExtDisplay.DisplayWindow" 
         ToggleAction 
         
   
   ENDDEF (*OpRecHeaderExt*);
   
   RecHeaderExt
   (* 1. Function
      
      2. Relation to other modules
      
      3. Comments on connection list
      
      4. Operators interface
      4.1 Pop-up windows
      
      4.2 Logging of operator interaction
      
      4.3 Modules accessable through pathstring
      "ModuleName*SelectButton"
      "ModuleName*Info"
      
      5. Scangroups
      Inherit/ProgStationData.GroupProg
      
      6. Opsave and secure
      
      7. Advice for usage *)
    = MODULEDEFINITION DateCode_ 372499855
   MODULEPARAMETERS
      Recipe "IN/OUT": RecipeType ;
      HeaderExtDisplay "IN/OUT": HeaderExtDisplayType ;
   LOCALVARIABLES
      ToggleWindow: boolean ;
   SUBMODULES
      Icon Invocation
         ( -1.0 , -1.0 , 0.0 , 2.00039 , 2.00101 
          Layer_ = 1
          ZoomLimits = 0.5 0.01 ) : HeaderExtIcon;
      
      BatchWindowControl Invocation
         ( 0.72 , -0.77997 , 0.0 , 0.11999 , 0.12 
          Layer_ = 2
          ) : BatchWindowControl (
      ToggleWindow => HeaderExtDisplay.DisplayWindow, 
      WindowPath => "-+Page1+Info", 
      RelPos => True, 
      xSize => 0.24, 
      ProgStationData => GLOBAL ProgStationData);
      
      HeaderExtControl Invocation
         ( 0.42 , -0.77997 , 0.0 , 0.11999 , 0.12 
          Layer_ = 2
          ) : HeaderExtControl (
      Value => HeaderExtDisplay.HeaderExtPresent);
      
      Page1 Invocation
         ( -0.9 , -0.8 , 0.0 , 1.12 , 1.12 
          Layer_ = 2
          ) : MODULEDEFINITION DateCode_ 371894918 ( Frame_Module ) 
      SUBMODULES
         Info Invocation
            ( 0.1 , 1.2 , 0.0 , 0.5 , 0.50005 
             ) : MODULEDEFINITION DateCode_ 371994653 ( Frame_Module ) 
         SUBMODULES
            Par1 Invocation
               ( 0.4 , -0.3 , -7.09579E-09 , 0.6 , 0.10714 
                ) : BatchStringMenu (
            Value => Recipe.Header.Extension.Ext1, 
            InteractEnable => HeaderExtDisplay.EnableInteraction);
            
            Par2 Invocation
               ( 0.4 , -0.4 , -7.09579E-09 , 0.6 , 0.10714 
                ) : BatchStringMenu (
            Value => Recipe.Header.Extension.Ext2, 
            InteractEnable => HeaderExtDisplay.EnableInteraction);
            
            Par3 Invocation
               ( 0.4 , -0.5 , -7.09579E-09 , 0.6 , 0.10714 
                ) : BatchStringMenu (
            Value => Recipe.Header.Extension.Ext3, 
            InteractEnable => HeaderExtDisplay.EnableInteraction);
            
            Par4 Invocation
               ( 0.4 , -0.6 , -7.09579E-09 , 0.6 , 0.10714 
                ) : BatchStringMenu (
            Value => Recipe.Header.Extension.Ext4, 
            InteractEnable => HeaderExtDisplay.EnableInteraction);
            
         
         ModuleDef
         ClippingBounds = ( 0.0 , -0.6 ) ( 1.0 , 0.0 )
         GraphObjects :
            RectangleObject ( -1.19209E-07 , -2.08616E-07 ) 
               ( 1.0 , -0.6 ) 
               OutlineColour : Colour0 = -3 
               FillColour : Colour1 = 51 
            TextObject ( -1.49012E-08 , -0.16 ) ( 1.0 , 0.0 ) 
               "HeaderExtension" 
               OutlineColour : Colour0 = -3 
            TextObject ( 0.0 , -0.3 ) ( 0.4 , -0.2 ) 
               "Ext1:" LeftAligned 
               OutlineColour : Colour0 = -3 
            TextObject ( -3.72529E-09 , -0.4 ) ( 0.4 , -0.3 ) 
               "Ext2:" LeftAligned 
               OutlineColour : Colour0 = -3 
            TextObject ( -3.72529E-09 , -0.5 ) ( 0.4 , -0.4 ) 
               "Ext3:" LeftAligned 
               OutlineColour : Colour0 = -3 
            TextObject ( -3.72529E-09 , -0.6 ) ( 0.4 , -0.5 ) 
               "Ext4:" LeftAligned 
               OutlineColour : Colour0 = -3 
         
         ENDDEF (*Info*);
         
      
      ModuleDef
      ClippingBounds = ( -2.98023E-08 , 0.0 ) ( 1.0 , 1.3 )
      
      ENDDEF (*Page1*);
      
   
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   Two_Layers_ LayerLimit_ = 0.95
   Zoomable
   GraphObjects :
      RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = -2 
      TextObject ( 2.23517E-08 , -0.06 ) ( 0.98 , 0.08 ) 
         "HeaderExtDisplay" 
         ConnectionNode ( 1.0 , 0.0 ) 
         
         OutlineColour : Colour0 = -3 
      RectangleObject ( 1.0 , 1.0002 ) ( -1.0 , -1.0 ) 
         Layer_ = 1
         OutlineColour : Colour0 = -3 
      TextObject ( -1.0 , 0.80018 ) ( 1.0 , 0.9602 ) 
         "HeaderExtension" 
         Layer_ = 1
         OutlineColour : Colour0 = -3 
      RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0002 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = -2 
      TextObject ( -1.0 , 0.80018 ) ( 1.0 , 0.9602 ) 
         "HeaderExtension" 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
   InteractObjects :
      SimpleInteract ( -0.8 , -0.79998 ) ( 0.8 , 0.80018 ) 
         Bool_Value
         Layer_ = 1
         Variable = False : OutVar_ "HeaderExtDisplay.DisplayWindow" 
         ToggleAction 
         
   
   ENDDEF (*RecHeaderExt*);
   
   RecipeManager1
   (* 1. Function:
      The recipe manager, together with a connected RecipeEditor, is used to create,
      edit and store master recipes. If a RecipeDocument module is connected
      the recipe may also be documented in a textfile.
      
      2. Relation to other modules:
      A RecipeEditor and RecipeDocument module can be connected to the RecipeManager.
      Several RecipeManagers (and OperationControlExt modules in BatchManager)
      can share the same editor and/or the same documenter, but only one RecipeManager
      (or OperationControlExt) can use them at a time.
      
      3. Comments on connection list:
      RecipeEditor and/or RecipeDocument is connected to the parameters RecipeCopy
      and EditorAndDocConn. The latter has a graphical connection.
      
      4. Operators interface:
      4.1. Pop-up windows:
      When selecting the module the main menu of the RecipeManager pops up with
      the following entries entries:
      
      New recipe: By entering a recipe name and the sizes of the recipe arrays a
      local recipe in the recipe manager is created and opened.
      
      Open recipe: By entering a recipe name an existing master recipe on the disk is
      restored and put into the local recipe in the recipe manager. If necessary, the
      recipe arrays can be expanded to a bigger size. When resizing a recipe the old
      contents of the recipe is kept unchanged. If the definition of the formula
      records in batchwlib have been changed since the recipe was saved the values
      of the components, whose names match, will be preserved. New components
      will have their default values.
      
      Close recipe: The local recipe in the recipe manager is erased. A warning and
      a request for confirmation pops up if the recipe has not been saved.
      
      Edit recipe: The recipe editor, which is connected through a parameter, pops up
      its editing window. The recipe can be edited.
      
      Document recipe: The recipe documenter, which is connected through a parameter,
      creates a text file containing a readable recipe document.
      
      View header: The recipe header of the local recipe in the recipe manager pops
      up for inspection.
      
      Save recipe: The local recipe is saved, via the "SaveVariable" function, on the disk
      in the system where this module executes. The recipe name is used as filename.
      (An extension .A is always added to SaveVariable filenames.)
      
      Submenues appear when selecting New, Open or (sometimes) Close in the
      main menu.
      
      4.2. Logging of operator interaction
      None
      
      4.3. Modules accessable through pathstring:
      The main pop up window is reached through "ModuleName*Info".
      
      5. Scangroups:
      The module inherits the scangroup from its father module but must execute
      in an operatorstation.
      
      6. Opsave and Secure:
      None
      
      7. Advice for usage:
      The parameters SavedRecipeName and RecipeSaved can be used to create back up
      copies of saved recipes. On positive edge of RecipeSaved the recipe file can be
      copied and transferred to another system. This optional function should be
      written in the application specific programs surrounding the RecipeManager. 
   *)
    = MODULEDEFINITION DateCode_ 323283860
   MODULEPARAMETERS
      Name "IN Module instance name": string  := "Recipe Manager";
      RecipeSystem "IN System to read recipe from", RecipeDirectory 
      "IN Directory to read recipe from", RecipeRevServer 
      "IN Name of the file revision server. The revison handling is activated if this name is defined"
      : string  := "";
      RevisionDelimiter 
      "IN The delimiter between filename and revision number. See description of module RestoreRecipe"
      : string  := "_v";
      EnableEdit "IN Enable editing", EnableEditRestricted 
      "IN Enable restricted editing": boolean  := True;
      EditSeverity "IN Edit severity": integer  := 0;
      EditClass "IN Edit class": integer  := 1;
      EnableControl "IN Enable control": boolean  := True;
      ControlSeverity "IN Control severity": integer  := 0;
      ControlClass "IN Control class": integer  := 1;
      Error "OUT Error": boolean  := Default;
      PrinterSystem "IN Printer system": String ;
      PrinterNo "IN Printer No.": Integer ;
   LOCALVARIABLES
      RecipeEditConnection "IN/OUT Connection to editor": RecipeEditConnType  
      := Default;
      RecipeDocConn "IN/OUT Connection to documenter": RecipeDocConnType  := 
      Default;
      RecipeRestoreConn "IN/OUT Connection to restore of recipe": 
      RecipeRestConnType ;
      RecipeSaveConn "IN/OUT Connection to save of recipe": RecipeSaveConnType 
      ;
      OpRecipeEditConn "IN/OUT To editor": OpRecipeEditConnType  := Default;
      OpRecipeDocConn "IN/OUT To documenter": OpRecipeDocConnType  := Default;
      OpRecipeRestoreConn "IN/OUT Connection to restore of operation recipe": 
      OpRecipeRestConnType ;
      OpRecipeSaveConn "IN/OUT Connection to save of operation recipe": 
      OpRecipeSaveConnType ;
      RecipeDocConnDummy "dummy variable - no function": RecipeDocConnType ;
      OpRecipeDocConnDummy "dummy variable - no function": OpRecipeDocConnType 
      ;
      EnableSave: boolean ;
   SUBMODULES
      Icon Invocation
         ( -1.0 , -1.0 , 0.0 , 2.0 , 2.0 
          Layer_ = 1
          ZoomLimits = 1000.0 0.01 ) : RecipeManagerIcon (
      error => error);
      
      RecipeManagerCore Invocation
         ( -0.58 , 0.44 , 0.0 , 0.2 , 0.2 
          Layer_ = 2
          ) : RecipeManagerCore (
      RecipeRestoreConn => RecipeRestoreConn, 
      RecipeSaveConn => RecipeSaveConn, 
      RecipeEditConnection => RecipeEditConnection, 
      RecipeDocConn => RecipeDocConn, 
      OpRecipeRestoreConn => OpRecipeRestoreConn, 
      OpRecipeSaveConn => OpRecipeSaveConn, 
      OpRecipeEditConn => OpRecipeEditConn, 
      OpRecipeDocConn => OpRecipeDocConn, 
      EnableNew => EnableEdit, 
      EnableSave => EnableSave);
      
      RecipeEditor Invocation
         ( -0.58 , -0.16 , 0.0 , 0.2 , 0.2 
          Layer_ = 2
          ) : RecipeEditor (
      Name => "RecipeEditor", 
      RecipeEditConnection => RecipeEditConnection, 
      EnableEdit => EnableEdit, 
      EnableEditRestricted => EnableEditRestricted, 
      EditSeverity => EditSeverity, 
      EditClass => EditClass, 
      EnableControl => EnableControl, 
      ControlSeverity => ControlSeverity, 
      ControlClass => ControlClass, 
      OpRecipeRestoreConn => OpRecipeRestoreConn);
      
      OpRecipeDocument1 Invocation
         ( 0.82 , -0.7 , 0.0 , 0.08 , 0.08 
          Layer_ = 2
          ) : OpRecipeDocument (
      FileName => OpRecipeDocConn.OperationRecipe.Header.MasterRecipeName, 
      FileExtension => ".M", 
      OpRecipeDocConn => OpRecipeDocConnDummy, 
      PrinterNo => 3);
      
      OpRecipeEditor Invocation
         ( 0.3 , -0.16 , 0.0 , 0.2 , 0.2 
          Layer_ = 2
          ) : OpRecipeEditor (
      OpRecipeEditConn => OpRecipeEditConn, 
      EnableEdit => EnableEdit, 
      EnableEditRestricted => EnableEditRestricted, 
      EditSeverity => EditSeverity, 
      EditClass => EditClass, 
      EnableControl => False);
      
      RecipeDocument1 Invocation
         ( -0.24 , -0.68 , 0.0 , 0.08 , 0.08 
          Layer_ = 2
          ) : RecipeDocument (
      FileName => RecipeDocConn.Recipe.Header.MasterRecipeName, 
      RecipeDocConnection => RecipeDocConnDummy);
      
      RestoreRecipe1 Invocation
         ( 0.16 , 0.48 , 0.0 , 0.08 , 0.08 
          Layer_ = 2
          ) : RestoreRecipe (
      RecipeSystem => RecipeSystem, 
      RecipeDirectory => RecipeDirectory, 
      RecipeRevServer => RecipeRevServer, 
      RevisionDelimiter => RevisionDelimiter, 
      RecipeRestoreConn => RecipeRestoreConn);
      
      RestoreOpRecipe1 Invocation
         ( 0.16 , 0.28 , 0.0 , 0.08 , 0.08 
          Layer_ = 2
          ) : RestoreOpRecipe (
      RecipeSystem => RecipeSystem, 
      RecipeDirectory => RecipeDirectory, 
      RecipeRevServer => RecipeRevServer, 
      RevisionDelimiter => RevisionDelimiter, 
      OpRecipeRestoreConn => OpRecipeRestoreConn);
      
      RecipeToFile1 Invocation
         ( 0.48 , 0.48 , 0.0 , 0.08 , 0.08 
          Layer_ = 2
          ) : RecipeToFile (
      RecipeRevServer => RecipeRevServer, 
      RecipeSystem => RecipeSystem, 
      RecipeDirectory => RecipeDirectory, 
      RevisionDelimiter => RevisionDelimiter, 
      RecipeSaveConn => RecipeSaveConn);
      
      OpRecipeToFile1 Invocation
         ( 0.48 , 0.28 , 0.0 , 0.08 , 0.08 
          Layer_ = 2
          ) : OpRecipeToFile (
      RecipeRevServer => RecipeRevServer, 
      RecipeSystem => RecipeSystem, 
      RecipeDirectory => RecipeDirectory, 
      RevisionDelimiter => RevisionDelimiter, 
      OpRecipeSaveConn => OpRecipeSaveConn);
      
      PutFileLocalRemote1 Invocation
         ( 0.72 , 0.48 , 0.0 , 0.08 , 0.08 
          Layer_ = 2
          ) : PutTextFile (
      RemoteSystem => RecipeSystem, 
      RemoteDirectory => RecipeDirectory);
      
      PutFileLocalRemote2 Invocation
         ( 0.72 , 0.28 , 0.0 , 0.08 , 0.08 
          Layer_ = 2
          ) : PutTextFile (
      RemoteSystem => RecipeSystem, 
      RemoteDirectory => RecipeDirectory);
      
      RecipeGraphDoc Invocation
         ( -0.66 , -0.64 , 0.0 , 0.14 , 0.14 
          Layer_ = 2
          ) : RecipeGraphDoc (
      RecipeDocConn => RecipeDocConn, 
      PrinterSystem => PrinterSystem, 
      PrinterNo => PrinterNo, 
      FileExtension => ".psm", 
      MasterRecipe => True);
      
      OpRecGraphDoc Invocation
         ( 0.26 , -0.64 , 0.0 , 0.14 , 0.14 
          Layer_ = 2
          ) : OpRecGraphDoc (
      OpRecipeDocConn => OpRecipeDocConn, 
      PrinterSystem => PrinterSystem, 
      PrinterNo => PrinterNo, 
      FileExtension => ".psm");
      
   
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   Two_Layers_ LayerLimit_ = 0.95
   Zoomable
   GraphObjects :
      RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
         Layer_ = 1
         OutlineColour : Colour0 = -3 Colour1 = 12 ColourStyle = False : InVar_ 
         "error" 
         FillColour : Colour1 = 12 ColourStyle = False : InVar_ "error" 
      RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = -2 
      RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      TextObject ( -1.0 , 0.8 ) ( 1.0 , 0.96 ) 
         "Name" VarName Width_ = 5 : InVar_ 5  ValueFraction = 3  
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      TextObject ( -1.0 , 0.64 ) ( -0.04 , 0.76 ) 
         "RecipeManagerCore" LeftAligned 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      TextObject ( -0.9 , 0.04 ) ( -0.26 , 0.16 ) 
         "RecipeEditor" LeftAligned 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      TextObject ( -0.1 , -0.5 ) ( 0.7 , -0.38 ) 
         "OpRecGraphDocument" LeftAligned 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      TextObject ( -0.96 , -0.5 ) ( -0.24 , -0.38 ) 
         "RecipeGraphDocument" LeftAligned 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      TextObject ( -0.1 , 0.04 ) ( 0.62 , 0.16 ) 
         "OpRecipeEditor" LeftAligned 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      TextObject ( 0.08 , 0.68 ) ( 0.52 , 0.76 ) 
         "RecipeSystem" 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      TextObject ( 0.56 , 0.68 ) ( 1.0 , 0.76 ) 
         "RecipeDirectory" 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      TextObject ( 0.08 , 0.6 ) ( 0.52 , 0.68 ) 
         "RecipeSystem" VarName Width_ = 5  ValueFraction = 2  
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      TextObject ( 0.56 , 0.6 ) ( 1.0 , 0.68 ) 
         "RecipeDirectory" VarName Width_ = 5  ValueFraction = 2  
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( 0.56 , 0.48 ) 
         ( 0.64 , 0.48 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( 0.56 , 0.28 ) 
         ( 0.64 , 0.28 ) 
         Layer_ = 2
      TextObject ( -0.92 , -0.82 ) ( 0.94 , -0.9 ) 
         "The modules for graphical documentation will only work if " 
         LeftAligned 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      TextObject ( -0.92 , -0.9 ) ( 0.94 , -0.98 ) 
         
         "a textfile called ""TextFile1.txt"" exists in the working directory !" 
         LeftAligned 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
   InteractObjects :
      ProcedureInteract ( -0.8 , -0.8 ) ( 0.8 , 0.8 ) 
         ToggleWindow
         "" : InVar_ LitString "*RecipeManagerCore+++Info" "" False : InVar_ 
         True 0.0 : InVar_ 0.1 0.0 : InVar_ -0.1 0.0 : InVar_ 0.24 0.0 False 0 
         0 False 0 
         Layer_ = 1
         Variable = 0.0 
   
   ModuleCode
   EQUATIONBLOCK Code COORD 0.68, -0.94 OBJSIZE 0.3, 0.1
   Layer_ = 2 :
      EnableSave = EnableEdit OR EnableEditRestricted;
   
   ENDDEF (*RecipeManager1*);
   
   OpRecipeDocument
   (* 
      1. Function:
      2. Relation to other modules:
      3. Comments on connection list:
      4. Operators interface:
      4.1. Pop-up windows:
      4.2. Logging of operator interaction:
      4.3. Modules accesable through pathstring:
      5. Scangroups:
      The module inherits the scangroup from its father module but must execute in a
      operator station.
      6. Opsave and Secure:
      7. Advice for usage:
      
      ************F|ljande ska in i base picture f|r batch lib:**************
      
       1. Function
      
       The content and layout of a recipe document is defined in this module,
       which comprises a number of line modules which can be  duplicated,
       replaced or deleted according to the needs of the recipe document builder.
      
       The recipe document is built by using modules for line, table and field.
       Some modules are specially designed to handle recipe records:
       ReportRecipeLine and ReportRecipetable.
      
       The ReportRecipeTable module reads one recipe record in each execution.
       The data of the current step is then made available to the line- and
       field modules that follow. By using ControlDivert and ControlAccept
       modules the execution will loop through the ReportRecipeTable module
       until there are no more steps in the recipe.
      
       The line modules are grouped together for each phase type, i.e. for each
       phase defined in the application a few line modules will have to be
       configured with field modules to document the formula values of that
       particular phase.
      
       Knowledge of reportlib functionality is necessary to configure this
       module.  Study the ReportMaster module of reportlib. Study the
       parameters of ReportRecipeTable and the contents of the CurrentStep
       record - this is essential when a recipe layout is defined.
      
       The DocumentMaster module is run from the RecipeManager or the
       BatchManager via the DocumentConnection parameter. The pop up window
       indicates if the module is active and displays the current line and page
       number of the document in progress. It also contains an error text, if
       required, and let the user inspect the file contining the recipe
       document.
      
      
       This is an example of a document created by the DocumentMaster if it is
       being left unmodified: (The master recipe is created using the phases defined
       in the batchdemo program unit.)
      
      
      Vanilla Fudge Recipe                   1993-04-23 16:20:28                    1
      
      RECIPE HEADER:
      --------------
      Master recipe:      Vanilla Fudge Recipe
                        M.Nelson               93-04-13
      Control recipe:
                                               79-12-31
      Product:            ABC-123
                        This is a testrecipe for a testproduct
      Scale factor:             1.00
      Logging:            Alarms ON      Interact. ON   History ON     Tracking OFF
      
      PROCEDURE: FORMULA:
      ---------- --------
      
      FILL       Filling
               Parallel fill. Agitation off.
               Product:           HPKO oil                 Skimmilk powder
               Coarse weight:         250.00                    30.00
               Fine weight:            50.00                     5.00
               Settle (s):                10                       20
      
      - Parallel: -
      AGITATE    Agitation2
               Speed:                20 Reverse:              ON
               Running time:        300 Pausing time:        200
      - End -
      
      - Parallel: -
      HEAT       Ramping
               Temperature:       20.00 -->     300.00
               Times (s):           360      2000       200
               Gain:               0.12     (      0.00  -        1.00)
               TI:               170.00     (      0.00  -      200.00)
      
      CONST.TEMP Heating
               Temperature:           0
      - End -
      
      COOL       Ramping
               Temperature:      240.00 -->     120.00
               Times (s):           300       700      3600
               Gain:               0.30     (      0.00  -        5.00)
               TI:               120.00     (      0.00  -      200.00)
      
      - Alternative: -
      NORM.AGIT  Agitation1
               Speed:               123
      - End -
      
      - Alternative: -
      INTERM.AGI Agitation2
               Speed:                30 Reverse:             OFF
               Running time:         20 Pausing time:         40
      - End -
      
      FINAL COOL Ramping
               Temperature:      120.00 -->      90.00
               Times (s):            10        20        30
               Gain:               0.20     (      0.00  -       10.00)
               TI:               300.00     (      0.00  -     1000.00) *)
    = MODULEDEFINITION DateCode_ 323955644
   MODULEPARAMETERS
      Name "IN Module name.": string  := "OpRecipe Documentation";
      FileName "IN Name of the local file containing the recipe document.": 
      string  := "OpRecipeDoc";
      FileExtension "IN Extension of file name. Start with a dot (.)": 
      identstring  := ".";
      OpRecipeDocConn "IN Connection to BatchManager or RecipeManager.": 
      OpRecipeDocConnType ;
      PrinterType "IN =1 if textprinter, =2....???", PrinterNo 
      "IN Number, e.g. 2 if TextPrinter2 is used.": integer  := 1;
      PrinterSystem "IN System name where printer resides.": string  := "";
      AutoPrint "IN if true, the file is printed when it has been created.": 
      boolean  := False;
      PageLength 
      "IN Number of lines in page for textfile. If PrinterType = 2 it should be <= (PageLengthPS-1)."
      : integer  := 65;
      PageLengthPS 
      "IN PageLength for PostScript module (PrinterType =2). Controls pagebreak and textsize"
      : integer  := 66;
      PageWidth "IN No. of characters per line.": integer  := 80;
      Append "IN Append to existing file.": boolean  := False;
      TrailingFormFeed "IN If true then a formfeed is added after the text.": 
      boolean  := True;
      LeadingFormFeed 
      "IN If true then a formfeed is inserted  before  the text.": boolean  := 
      False;
      FontSize "IN Font size, connect to OpRecipeDocControl": integer  := 12;
   LOCALVARIABLES
      R "Common data for line and field modules.": ReportCommon ;
      FirstLine "Used by library modules.", LastLine "Used by library modules."
      , HeaderFirstLine "Used by library modules.", HeaderEndLine 
      "Used by library modules.": LineConnection ;
      ExecuteState "Used by library modules.": boolean State;
      windowenable "Used by library modules.", NewDocument 
      "Used by library modules. True when a new recipe document is initiated.": 
      Boolean ;
      InitTable: boolean  := False;
      StartOfParallel, EndOfParallel, StartOfAlternative, EndOfAlternative, 
      LastStep, MoreSteps, Jump, Error, Direct, NormalStep: boolean ;
      CurrentStep: ReportOpRecStepType ;
      ControlRecipe: boolean ;
      InternalFileName: string ;
      Status: integer ;
      JumpDestStepName: Identstring ;
   SUBMODULES
      Icon Invocation
         ( -1.0 , -1.0 , 0.0 , 2.0 , 2.0 
          Layer_ = 1
          ZoomLimits = 0.5 0.01 ) : RecipeDocumentIcon (
      error => Error);
      
      OpRecipeDocControl Invocation
         ( 0.78665 , -0.89333 , 0.0 , 0.06667 , 0.06667 
          Layer_ = 2
          ) : RecDocumentControl (
      Name => Name, 
      MasterRecipeName => OpRecipeDocConn.OperationRecipe.Header.
      MasterRecipeName, 
      ControlRecipeName => OpRecipeDocConn.OperationRecipe.Header.
      ControlRecipeName, 
      DocumenterPresent => OpRecipeDocConn.DocumenterPresent, 
      ExecuteDocument => OpRecipeDocConn.ExecuteDocument, 
      DocumentReady => OpRecipeDocConn.DocumentReady, 
      DocumentReadyOk => OpRecipeDocConn.DocumentReadyOk, 
      R => R, 
      FirstLine => FirstLine, 
      LastLine => LastLine, 
      HeaderFirstLine => HeaderFirstLine, 
      HeaderEndLine => HeaderEndLine, 
      FileName => InternalFileName, 
      PageLength => PageLength, 
      PageLengthPS => PageLengthPS, 
      PageWidth => PageWidth, 
      Append => Append, 
      TrailingFormFeed => trailingformfeed, 
      LeadingFormFeed => leadingformfeed, 
      FontSize => FontSize, 
      AutoPrint => AutoPrint, 
      NewDocument => NewDocument, 
      ControlRecipe => ControlRecipe);
      
      RecHeadMasterLine2 Invocation
         ( -0.93333 , 0.79998 , 0.0 , 0.16479 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      ReportControl => R);
      
      RecHeadControlLine2 Invocation
         ( -0.93333 , 0.76665 , 0.0 , 0.16479 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => ControlRecipe, 
      ReportControl => R);
      
      RecHeadProductLine2 Invocation
         ( -0.93333 , 0.69998 , 0.0 , 0.16485 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      ReportControl => R);
      
      RecHeadMasterLine1 Invocation
         ( -0.93333 , 0.81665 , 0.0 , 0.16479 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      ReportControl => R);
      
      RecHeadControlLine1 Invocation
         ( -0.93333 , 0.78332 , 0.0 , 0.16479 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => ControlRecipe, 
      ReportControl => R);
      
      RecHeadProductLine1 Invocation
         ( -0.93333 , 0.71665 , 0.0 , 0.16479 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      ReportControl => R);
      
      RecHeadScaleFactLine Invocation
         ( -0.93333 , 0.68332 , 0.0 , 0.16479 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      ReportControl => R);
      
      RecHeadLoggingLine Invocation
         ( -0.93333 , 0.66665 , 0.0 , 0.1648 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      ReportControl => R);
      
      RecHeadEmptyLine Invocation
         ( -0.93333 , 0.64998 , 0.0 , 0.1648 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      ReportControl => R);
      
      DirectTransLine2 Invocation
         ( -0.93333 , 0.48332 , 0.0 , 0.1648 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => Direct, 
      ReportControl => R);
      
      RecHeadTitleLine1 Invocation
         ( -0.93333 , 0.84998 , 0.0 , 0.1648 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      ReportControl => R);
      
      ProcedureTitleLine1 Invocation
         ( -0.93333 , 0.61665 , 0.0 , 0.1648 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      ReportControl => R);
      
      RecHeadTitleLine2 Invocation
         ( -0.93333 , 0.83332 , 0.0 , 0.1648 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      ReportControl => R);
      
      ProcedureTitleLine2 Invocation
         ( -0.93333 , 0.59998 , 0.0 , 0.1648 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      ReportControl => R);
      
      Dummyline1 Invocation
         ( -0.36667 , 0.88665 , 0.0 , 0.16601 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => False, 
      ReportControl => R);
      
      DummyLine2 Invocation
         ( 0.28332 , 0.85665 , 0.0 , 0.16601 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => False, 
      ReportControl => R);
      
      AcceptLine2 Invocation
         ( -0.93333 , 0.58332 , 0.0 , 0.16601 , 0.17333 
          Layer_ = 2
          ) : ReportControlAccept (
      ReportControl => R);
      
      ReportOpRecipeTrace2 Invocation
         ( -0.93333 , 0.56665 , 0.0 , 0.16485 , 0.17333 
          Layer_ = 2
          ) : ReportOpRecipeTrace (
      ReadFirstStep => InitTable, 
      Recipe => OpRecipeDocConn.OperationRecipe, 
      CurrentStep => CurrentStep, 
      StartOfParallel => StartOfParallel, 
      EndOfParallel => EndOfParallel, 
      StartOfAlternative => StartOfAlternative, 
      Direct => Direct, 
      NormalStep => NormalStep, 
      EndOfAlternative => EndOfAlternative, 
      LastStep => LastStep, 
      MoreSteps => MoreSteps, 
      Jump => Jump, 
      ReportControl => R, 
      JumpDestStepName => JumpDestStepName);
      
      StartParLine2 Invocation
         ( -0.93333 , 0.54998 , 0.0 , 0.16484 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => StartOfParallel, 
      ReportControl => R);
      
      StartAltLine2 Invocation
         ( -0.93333 , 0.53332 , 0.0 , 0.1648 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => StartOfAlternative, 
      ReportControl => R);
      
      JumpLine2 Invocation
         ( -0.93333 , 0.51665 , 0.0 , 0.1648 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => Jump, 
      ReportControl => R);
      
      PhaseStepLine2 Invocation
         ( -0.93333 , 0.49998 , 0.0 , 0.16485 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => NormalStep, 
      ReportControl => R);
      
      HeatingLine Invocation
         ( -0.93333 , 0.44999 , 0.0 , 0.16479 , 0.17333 
          Layer_ = 2
          ) : ReportRecipeLine (
      EnableModule => NormalStep, 
      CurrentPhase => CurrentStep.Step.PhaseName, 
      PhaseOfThisLine => "Heating", 
      ReportControl => R);
      
      Agit1Line Invocation
         ( -0.93333 , 0.41665 , 0.0 , 0.16479 , 0.17333 
          Layer_ = 2
          ) : ReportRecipeLine (
      EnableModule => NormalStep, 
      CurrentPhase => CurrentStep.Step.PhaseName, 
      PhaseOfThisLine => "Agitation1", 
      ReportControl => R);
      
      RampLine1 Invocation
         ( -0.93333 , 0.33332 , 0.0 , 0.16479 , 0.17333 
          Layer_ = 2
          ) : ReportRecipeLine (
      EnableModule => NormalStep, 
      CurrentPhase => CurrentStep.Step.PhaseName, 
      PhaseOfThisLine => "Ramping", 
      ReportControl => R);
      
      RampLine2 Invocation
         ( -0.93333 , 0.31665 , 0.0 , 0.16479 , 0.17333 
          Layer_ = 2
          ) : ReportRecipeLine (
      EnableModule => NormalStep, 
      CurrentPhase => CurrentStep.Step.PhaseName, 
      PhaseOfThisLine => "Ramping", 
      ReportControl => R);
      
      RampLine3 Invocation
         ( -0.93333 , 0.29999 , 0.0 , 0.16479 , 0.17333 
          Layer_ = 2
          ) : ReportRecipeLine (
      EnableModule => NormalStep, 
      CurrentPhase => CurrentStep.Step.PhaseName, 
      PhaseOfThisLine => "Ramping", 
      ReportControl => R);
      
      RampLine4 Invocation
         ( -0.93333 , 0.28332 , 0.0 , 0.16479 , 0.17333 
          Layer_ = 2
          ) : ReportRecipeLine (
      EnableModule => NormalStep, 
      CurrentPhase => CurrentStep.Step.PhaseName, 
      PhaseOfThisLine => "Ramping", 
      ReportControl => R);
      
      FillLine1 Invocation
         ( -0.93333 , 0.24999 , 0.0 , 0.16479 , 0.17333 
          Layer_ = 2
          ) : ReportRecipeLine (
      EnableModule => NormalStep, 
      CurrentPhase => CurrentStep.Step.PhaseName, 
      PhaseOfThisLine => "Filling", 
      ReportControl => R);
      
      FillLine2 Invocation
         ( -0.93333 , 0.23332 , 0.0 , 0.16479 , 0.17333 
          Layer_ = 2
          ) : ReportRecipeLine (
      EnableModule => NormalStep, 
      CurrentPhase => CurrentStep.Step.PhaseName, 
      PhaseOfThisLine => "Filling", 
      ReportControl => R);
      
      FillLine3 Invocation
         ( -0.93333 , 0.21665 , 0.0 , 0.16479 , 0.17333 
          Layer_ = 2
          ) : ReportRecipeLine (
      EnableModule => NormalStep, 
      CurrentPhase => CurrentStep.Step.PhaseName, 
      PhaseOfThisLine => "Filling", 
      ReportControl => R);
      
      FillLine4 Invocation
         ( -0.93333 , 0.19999 , 0.0 , 0.16479 , 0.17333 
          Layer_ = 2
          ) : ReportRecipeLine (
      EnableModule => NormalStep, 
      CurrentPhase => CurrentStep.Step.PhaseName, 
      PhaseOfThisLine => "Filling", 
      ReportControl => R);
      
      FillLine5 Invocation
         ( -0.93333 , 0.18332 , 0.0 , 0.16479 , 0.17333 
          Layer_ = 2
          ) : ReportRecipeLine (
      EnableModule => NormalStep, 
      CurrentPhase => CurrentStep.Step.PhaseName, 
      PhaseOfThisLine => "Filling", 
      ReportControl => R);
      
      EndAltLine2 Invocation
         ( -0.93333 , 0.15332 , 0.0 , 0.16479 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => EndOfAlternative, 
      ReportControl => R);
      
      EndParLine2 Invocation
         ( -0.93333 , 0.13332 , 0.0 , 0.16479 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => EndOfParallel, 
      ReportControl => R);
      
      DivertLine2 Invocation
         ( -0.93333 , 0.11666 , 0.0 , 0.16485 , 0.17206 
          Layer_ = 2
          ) : ReportControlDivert (
      Continue => LastStep, 
      Divert => MoreSteps, 
      ReportControl => R);
      
      PageHeaderLine1 Invocation
         ( -0.93333 , 0.91665 , 0.0 , 0.16479 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      ReportControl => R);
      
      HeaderLine2 Invocation
         ( -0.93333 , 0.89998 , 0.0 , 0.16479 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => ControlRecipe, 
      ReportControl => R);
      
      MasterRecipeName Invocation
         ( -0.91667 , 0.91665 , 0.0 , 0.06667 , 0.00666659 
          Layer_ = 2
          ) : ReportString (
      Value => OpRecipeDocConn.OperationRecipe.Header.MasterRecipeName, 
      Width => 40, 
      Left => True, 
      ReportControl => R);
      
      MasterRecName Invocation
         ( -0.85 , 0.81665 , 0.0 , 0.06667 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => OpRecipeDocConn.OperationRecipe.Header.MasterRecipeName, 
      Width => 40, 
      Left => True, 
      ReportControl => R);
      
      ControlRecName Invocation
         ( -0.85 , 0.78332 , 0.0 , 0.06667 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => OpRecipeDocConn.OperationRecipe.Header.ControlRecipeName, 
      Width => 40, 
      Left => True, 
      ReportControl => R);
      
      ProductCode Invocation
         ( -0.85 , 0.71665 , 0.0 , 0.06667 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => OpRecipeDocConn.OperationRecipe.Header.Productcode, 
      Width => 40, 
      Left => True, 
      ReportControl => R);
      
      ScaleFactor Invocation
         ( -0.85 , 0.68332 , 0.0 , 0.01667 , 0.0066666 
          Layer_ = 2
          ) : ReportReal (
      Value => OpRecipeDocConn.OperationRecipe.Header.ScaleFactor, 
      Width => 10, 
      ReportControl => R);
      
      LogAlarms Invocation
         ( -0.85 , 0.66665 , 0.0 , 0.025 , 0.0066666 
          Layer_ = 2
          ) : ReportBoolean (
      Value => OpRecipeDocConn.OperationRecipe.Header.LogAlarms, 
      OnText => "Alarms ON", 
      OffText => "Alarms OFF", 
      Left => True, 
      Width => 13, 
      ReportControl => R);
      
      LogInteraction Invocation
         ( -0.8 , 0.66665 , 0.0 , 0.025 , 0.0066666 
          Layer_ = 2
          ) : ReportBoolean (
      Value => OpRecipeDocConn.OperationRecipe.Header.LogInteraction, 
      OnText => "Interaction ON", 
      OffText => "Interaction OFF", 
      Left => True, 
      Width => 17, 
      ReportControl => R);
      
      LogHistory Invocation
         ( -0.75 , 0.66665 , 0.0 , 0.025 , 0.0066666 
          Layer_ = 2
          ) : ReportBoolean (
      Value => OpRecipeDocConn.OperationRecipe.Header.LogHistory, 
      OnText => "History ON", 
      OffText => "History OFF", 
      Left => True, 
      Width => 15, 
      ReportControl => R);
      
      LogTracking Invocation
         ( -0.7 , 0.66665 , 0.0 , 0.025 , 0.0066666 
          Layer_ = 2
          ) : ReportBoolean (
      Value => OpRecipeDocConn.OperationRecipe.Header.LogTracking, 
      OnText => "Tracking ON", 
      OffText => "Tracking OFF", 
      Left => True, 
      Width => 15, 
      ReportControl => R);
      
      ControlRecipeName Invocation
         ( -0.91667 , 0.89998 , 0.0 , 0.06667 , 0.00666659 
          Layer_ = 2
          ) : ReportString (
      Value => OpRecipeDocConn.OperationRecipe.Header.ControlRecipeName, 
      Width => 40, 
      Left => True, 
      ReportControl => R);
      
      ReportGenTime Invocation
         ( -0.78334 , 0.91665 , 0.0 , 0.03333 , 0.00666659 
          Layer_ = 2
          ) : ReportTime (
      Value => R.TimeOfReportGen, 
      TimeFormat => GLOBAL ProgStationData.TimeFormats.DateAndTime, 
      Width => 20, 
      Left => True, 
      ReportControl => R);
      
      PageNo Invocation
         ( -0.66667 , 0.91665 , 0.0 , 0.0099999 , 0.0066666 
          Layer_ = 2
          ) : ReportInteger (
      Value => R.CurrentPage, 
      Width => 5, 
      LeadingSpaces => 15, 
      ReportControl => R);
      
      StartParallel2 Invocation
         ( -0.91667 , 0.54998 , 0.0 , 0.05 , 0.00666659 
          Layer_ = 2
          ) : ReportString (
      Value => "- Parallel branch -", 
      Width => 30, 
      Left => True, 
      ReportControl => R);
      
      StartAlternative2 Invocation
         ( -0.91667 , 0.53332 , 0.0 , 0.05 , 0.00666659 
          Layer_ = 2
          ) : ReportString (
      Value => "- Alternative branch. Result =", 
      Width => 30, 
      Left => True, 
      ReportControl => R);
      
      StepName2 Invocation
         ( -0.91667 , 0.49998 , 0.0 , 0.01667 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => CurrentStep.step.Stepname, 
      Width => 10, 
      Left => True, 
      ReportControl => R);
      
      StepType2 Invocation
         ( -0.87667 , 0.49998 , 0.0 , 0.03167 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => CurrentStep.step.Phasename, 
      Width => 40, 
      LeadingSpaces => 1, 
      Left => True, 
      ReportControl => R);
      
      DirectTransition2 Invocation
         ( -0.91667 , 0.48332 , 0.0 , 0.06667 , 0.00666659 
          Layer_ = 2
          ) : ReportString (
      Value => "No step, direct conditional transition", 
      Width => 40, 
      Left => True, 
      ReportControl => R);
      
      AlternativeEnd2 Invocation
         ( -0.91667 , 0.15332 , 0.0 , 0.05 , 0.00666659 
          Layer_ = 2
          ) : ReportString (
      Value => "- End of alternative branch -", 
      Width => 30, 
      Left => True, 
      ReportControl => R);
      
      ParallelEnd2 Invocation
         ( -0.91667 , 0.13332 , 0.0 , 0.05 , 0.00666655 
          Layer_ = 2
          ) : ReportString (
      Value => "- End of parallel branch -", 
      Width => 30, 
      Left => True, 
      ReportControl => R);
      
      MasterRecText Invocation
         ( -0.91667 , 0.81665 , 0.0 , 0.03333 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => "Master recipe :", 
      Width => 20, 
      Left => True, 
      ReportControl => R);
      
      ControlRecText Invocation
         ( -0.91667 , 0.78332 , 0.0 , 0.03333 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => "Control recipe :", 
      Width => 20, 
      Left => True, 
      ReportControl => R);
      
      ProductText Invocation
         ( -0.91667 , 0.71665 , 0.0 , 0.03333 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => "Product :", 
      Width => 20, 
      Left => True, 
      ReportControl => R);
      
      ScaleFactorText Invocation
         ( -0.91667 , 0.68332 , 0.0 , 0.03333 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => "Scale factor :", 
      Width => 20, 
      Left => True, 
      ReportControl => R);
      
      LogText Invocation
         ( -0.91667 , 0.66665 , 0.0 , 0.03333 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => "Logging", 
      Width => 20, 
      Left => True, 
      ReportControl => R);
      
      RecipeHeaderTitle1 Invocation
         ( -0.91667 , 0.84998 , 0.0 , 0.06667 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => "RECIPE HEADER", 
      Width => 40, 
      Left => True, 
      ReportControl => R);
      
      ProcedureText Invocation
         ( -0.91667 , 0.61665 , 0.0 , 0.03333 , 0.00666659 
          Layer_ = 2
          ) : ReportString (
      Value => "PROCEDURE", 
      Width => 20, 
      Left => True, 
      ReportControl => R);
      
      FormulaText Invocation
         ( -0.83333 , 0.61665 , 0.0 , 0.03333 , 0.00666659 
          Layer_ = 2
          ) : ReportString (
      Value => "FORMULA", 
      Width => 20, 
      LeadingSpaces => 5, 
      Left => True, 
      ReportControl => R);
      
      RecipeHeaderTitle2 Invocation
         ( -0.91667 , 0.83332 , 0.0 , 0.06667 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => "--------------", 
      Width => 40, 
      Left => True, 
      ReportControl => R);
      
      ProcedureTextUndersc Invocation
         ( -0.91667 , 0.59998 , 0.0 , 0.03333 , 0.00666651 
          Layer_ = 2
          ) : ReportString (
      Value => "-------------------", 
      Width => 20, 
      Left => True, 
      ReportControl => R);
      
      FormulaTextUndersc Invocation
         ( -0.83333 , 0.59998 , 0.0 , 0.03333 , 0.00666651 
          Layer_ = 2
          ) : ReportString (
      Value => "------------------", 
      Width => 20, 
      LeadingSpaces => 5, 
      Left => True, 
      ReportControl => R);
      
      MasterRecAuthor Invocation
         ( -0.85 , 0.79998 , 0.0 , 0.03333 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => OpRecipeDocConn.OperationRecipe.Header.MasterrecipeAuthor, 
      Width => 20, 
      Left => True, 
      ReportControl => R);
      
      ControlRecAuthor Invocation
         ( -0.85 , 0.76665 , 0.0 , 0.03333 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => OpRecipeDocConn.OperationRecipe.Header.ControlrecipeAuthor, 
      Width => 20, 
      Left => True, 
      ReportControl => R);
      
      ProductDescription Invocation
         ( -0.85 , 0.69998 , 0.0 , 0.06667 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => OpRecipeDocConn.OperationRecipe.Header.ProductDescription, 
      Width => 40, 
      Left => True, 
      ReportControl => R);
      
      MasterRecDate Invocation
         ( -0.78334 , 0.79998 , 0.0 , 0.03333 , 0.0066666 
          Layer_ = 2
          ) : ReportTime (
      Value => OpRecipeDocConn.OperationRecipe.Header.MasterrecipeDate, 
      TimeFormat => GLOBAL ProgStationData.TimeFormats.Date, 
      Width => 20, 
      Left => True, 
      ReportControl => R);
      
      ControlRecDate Invocation
         ( -0.78334 , 0.76665 , 0.0 , 0.03333 , 0.0066666 
          Layer_ = 2
          ) : ReportTime (
      Value => OpRecipeDocConn.OperationRecipe.Header.ControlrecipeDate, 
      TimeFormat => GLOBAL ProgStationData.TimeFormats.Date, 
      Width => 20, 
      Left => True, 
      ReportControl => R);
      
      HeatText Invocation
         ( -0.88 , 0.44999 , 0.0 , 0.02333 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => "Temperature:", 
      Width => 14, 
      LeadingSpaces => 11, 
      Left => True, 
      ReportControl => R);
      
      AgitText Invocation
         ( -0.88 , 0.41665 , 0.0 , 0.02333 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => "Speed:", 
      Width => 14, 
      LeadingSpaces => 11, 
      Left => True, 
      ReportControl => R);
      
      RampText1 Invocation
         ( -0.88 , 0.33332 , 0.0 , 0.02333 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => "Temperature:", 
      Width => 14, 
      LeadingSpaces => 11, 
      Left => True, 
      ReportControl => R);
      
      RampText2 Invocation
         ( -0.88 , 0.31665 , 0.0 , 0.02333 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => "Times (s):", 
      Width => 14, 
      LeadingSpaces => 11, 
      Left => True, 
      ReportControl => R);
      
      RampText3 Invocation
         ( -0.88 , 0.29999 , 0.0 , 0.02333 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => "Gain:", 
      Width => 14, 
      LeadingSpaces => 11, 
      Left => True, 
      ReportControl => R);
      
      RampText4 Invocation
         ( -0.88 , 0.28332 , 0.0 , 0.02333 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => "TI:", 
      Width => 14, 
      LeadingSpaces => 11, 
      Left => True, 
      ReportControl => R);
      
      Temperature Invocation
         ( -0.82667 , 0.44999 , 0.0 , 0.015 , 0.0066666 
          Layer_ = 2
          ) : ReportInteger (
      Value => CurrentStep.Formula1.Formula.Int1, 
      Width => 9, 
      LeadingSpaces => 1, 
      ReportControl => R);
      
      Speed Invocation
         ( -0.82667 , 0.41665 , 0.0 , 0.015 , 0.0066666 
          Layer_ = 2
          ) : ReportInteger (
      Value => CurrentStep.Formula1.Formula.Int1, 
      Width => 9, 
      LeadingSpaces => 1, 
      ReportControl => R);
      
      StartTemp Invocation
         ( -0.82667 , 0.33332 , 0.0 , 0.015 , 0.0066666 
          Layer_ = 2
          ) : ReportReal (
      Value => CurrentStep.Formula2.Formula.Real2, 
      Width => 9, 
      LeadingSpaces => 1, 
      ReportControl => R);
      
      Gain Invocation
         ( -0.82667 , 0.29999 , 0.0 , 0.015 , 0.0066666 
          Layer_ = 2
          ) : ReportReal (
      Value => CurrentStep.Formula2.Formula.Real3, 
      Width => 9, 
      LeadingSpaces => 1, 
      ReportControl => R);
      
      Ti Invocation
         ( -0.82667 , 0.28332 , 0.0 , 0.015 , 0.0066666 
          Layer_ = 2
          ) : ReportReal (
      Value => CurrentStep.Formula2.Formula.Real6, 
      Width => 9, 
      LeadingSpaces => 1, 
      ReportControl => R);
      
      GainMin Invocation
         ( -0.77667 , 0.29999 , 0.0 , 0.015 , 0.0066666 
          Layer_ = 2
          ) : ReportReal (
      Value => CurrentStep.Formula2.Formula.Real4, 
      ReportControl => R);
      
      TiMin Invocation
         ( -0.77667 , 0.28332 , 0.0 , 0.015 , 0.0066666 
          Layer_ = 2
          ) : ReportReal (
      Value => CurrentStep.Formula2.Formula.Real7, 
      ReportControl => R);
      
      GainMax Invocation
         ( -0.73334 , 0.29999 , 0.0 , 0.01667 , 0.0066666 
          Layer_ = 2
          ) : ReportReal (
      Value => CurrentStep.Formula2.Formula.Real5, 
      Width => 10, 
      ReportControl => R);
      
      TiMax Invocation
         ( -0.73334 , 0.28332 , 0.0 , 0.01667 , 0.0066666 
          Layer_ = 2
          ) : ReportReal (
      Value => CurrentStep.Formula2.Formula.Real8, 
      Width => 10, 
      ReportControl => R);
      
      Time1 Invocation
         ( -0.82667 , 0.31665 , 0.0 , 0.015 , 0.0066666 
          Layer_ = 2
          ) : ReportInteger (
      Value => CurrentStep.Formula2.Formula.Int1, 
      Width => 9, 
      LeadingSpaces => 1, 
      ReportControl => R);
      
      Time2 Invocation
         ( -0.79334 , 0.31665 , 0.0 , 0.015 , 0.0066666 
          Layer_ = 2
          ) : ReportInteger (
      Value => CurrentStep.Formula2.Formula.Int2, 
      Width => 9, 
      LeadingSpaces => 1, 
      ReportControl => R);
      
      Time3 Invocation
         ( -0.76 , 0.31665 , 0.0 , 0.015 , 0.0066666 
          Layer_ = 2
          ) : ReportInteger (
      Value => CurrentStep.Formula2.Formula.Int3, 
      Width => 9, 
      LeadingSpaces => 1, 
      ReportControl => R);
      
      StopTemp Invocation
         ( -0.77667 , 0.33332 , 0.0 , 0.015 , 0.0066666 
          Layer_ = 2
          ) : ReportReal (
      Value => CurrentStep.Formula2.Formula.Real1, 
      Width => 9, 
      LeadingSpaces => 1, 
      ReportControl => R);
      
      Arrow1 Invocation
         ( -0.79334 , 0.33332 , 0.0 , 0.0066666 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => " --> ", 
      Width => 5, 
      Left => True, 
      ReportControl => R);
      
      Bracket1 Invocation
         ( -0.78667 , 0.29999 , 0.0 , 0.00166665 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => "(", 
      Width => 1, 
      LeadingSpaces => 5, 
      Left => True, 
      ReportControl => R);
      
      Bracket3 Invocation
         ( -0.78667 , 0.28332 , 0.0 , 0.00166665 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => "(", 
      Width => 1, 
      LeadingSpaces => 5, 
      Left => True, 
      ReportControl => R);
      
      Bracket2 Invocation
         ( -0.69667 , 0.29999 , 0.0 , 0.00166665 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => ")", 
      Width => 1, 
      Left => True, 
      ReportControl => R);
      
      Bracket4 Invocation
         ( -0.69667 , 0.28332 , 0.0 , 0.00166665 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => ")", 
      Width => 1, 
      Left => True, 
      ReportControl => R);
      
      Line Invocation
         ( -0.74667 , 0.29999 , 0.0 , 0.00833325 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => "  -  ", 
      Width => 5, 
      Left => True, 
      ReportControl => R);
      
      LineB Invocation
         ( -0.74667 , 0.28332 , 0.0 , 0.00833325 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => "  -  ", 
      Width => 5, 
      Left => True, 
      ReportControl => R);
      
      FillText Invocation
         ( -0.88 , 0.24999 , 0.0 , 0.02333 , 0.0066666 
          Layer_ = 2
          ) : ReportBoolean (
      Value => CurrentStep.Formula3.Formula.Bool1, 
      OnText => "Parallel fill.", 
      OffText => "Single fill.", 
      Left => True, 
      Width => 14, 
      LeadingSpaces => 11, 
      ReportControl => R);
      
      FillText1 Invocation
         ( -0.88 , 0.23332 , 0.0 , 0.02333 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => "Product:", 
      Width => 14, 
      Left => True, 
      ReportControl => R);
      
      Prod1 Invocation
         ( -0.81667 , 0.23332 , 0.0 , 0.03333 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => CurrentStep.Formula3.Formula.String1, 
      Width => 20, 
      LeadingSpaces => 5, 
      ReportControl => R);
      
      Prod2 Invocation
         ( -0.73334 , 0.23332 , 0.0 , 0.03333 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => CurrentStep.Formula3.Formula.String2, 
      Width => 20, 
      LeadingSpaces => 5, 
      ReportControl => R);
      
      FillText2 Invocation
         ( -0.88 , 0.21665 , 0.0 , 0.02333 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => "Coarse weight:", 
      Width => 14, 
      Left => True, 
      ReportControl => R);
      
      FillText3 Invocation
         ( -0.88 , 0.19999 , 0.0 , 0.02333 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => "Fine weight:", 
      Width => 14, 
      Left => True, 
      ReportControl => R);
      
      FillText4 Invocation
         ( -0.88 , 0.18332 , 0.0 , 0.02333 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => "Settle (s):", 
      Width => 14, 
      Left => True, 
      ReportControl => R);
      
      AgitTextFill Invocation
         ( -0.83 , 0.24999 , 0.0 , 0.03167 , 0.0066666 
          Layer_ = 2
          ) : ReportBoolean (
      Value => CurrentStep.Formula3.Formula.Bool2, 
      OnText => "Agitation on.", 
      OffText => "Agitation off.", 
      Left => True, 
      Width => 19, 
      LeadingSpaces => 1, 
      ReportControl => R);
      
      Coarse1 Invocation
         ( -0.81667 , 0.21665 , 0.0 , 0.01667 , 0.0066666 
          Layer_ = 2
          ) : ReportReal (
      Value => CurrentStep.Formula3.Formula.REal1, 
      Width => 10, 
      ReportControl => R);
      
      Fine1 Invocation
         ( -0.81667 , 0.19999 , 0.0 , 0.01667 , 0.0066666 
          Layer_ = 2
          ) : ReportReal (
      Value => CurrentStep.Formula3.Formula.REal3, 
      Width => 10, 
      ReportControl => R);
      
      Infl1 Invocation
         ( -0.81667 , 0.18332 , 0.0 , 0.01667 , 0.0066666 
          Layer_ = 2
          ) : ReportInteger (
      Value => CurrentStep.Formula3.Formula.Int1, 
      Width => 10, 
      ReportControl => R);
      
      Coarse2 Invocation
         ( -0.73334 , 0.21665 , 0.0 , 0.01667 , 0.0066666 
          Layer_ = 2
          ) : ReportReal (
      Value => CurrentStep.Formula3.Formula.REal2, 
      Width => 10, 
      LeadingSpaces => 15, 
      ReportControl => R);
      
      Fine2 Invocation
         ( -0.73334 , 0.19999 , 0.0 , 0.01667 , 0.0066666 
          Layer_ = 2
          ) : ReportReal (
      Value => CurrentStep.Formula3.Formula.REal4, 
      Width => 10, 
      LeadingSpaces => 15, 
      ReportControl => R);
      
      Infl2 Invocation
         ( -0.73334 , 0.18332 , 0.0 , 0.01667 , 0.0066666 
          Layer_ = 2
          ) : ReportInteger (
      Value => CurrentStep.Formula3.Formula.int2, 
      Width => 10, 
      LeadingSpaces => 15, 
      ReportControl => R);
      
      Agit2Line1 Invocation
         ( -0.93333 , 0.38332 , 0.0 , 0.16479 , 0.17333 
          Layer_ = 2
          ) : ReportRecipeLine (
      EnableModule => NormalStep, 
      CurrentPhase => CurrentStep.Step.PhaseName, 
      PhaseOfThisLine => "Agitation2", 
      ReportControl => R);
      
      Agit2Line2 Invocation
         ( -0.93333 , 0.36665 , 0.0 , 0.16479 , 0.17333 
          Layer_ = 2
          ) : ReportRecipeLine (
      EnableModule => NormalStep, 
      CurrentPhase => CurrentStep.Step.PhaseName, 
      PhaseOfThisLine => "Agitation2", 
      ReportControl => R);
      
      Agit2Text1 Invocation
         ( -0.88 , 0.38332 , 0.0 , 0.02333 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => "Speed:", 
      Width => 14, 
      LeadingSpaces => 11, 
      Left => True, 
      ReportControl => R);
      
      RunTime Invocation
         ( -0.88 , 0.36665 , 0.0 , 0.02333 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => "Running time:", 
      Width => 14, 
      LeadingSpaces => 11, 
      Left => True, 
      ReportControl => R);
      
      Agit2Text2 Invocation
         ( -0.79667 , 0.38332 , 0.0 , 0.02333 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => "Reverse:", 
      Width => 14, 
      LeadingSpaces => 1, 
      Left => True, 
      ReportControl => R);
      
      Agit2Text4 Invocation
         ( -0.79667 , 0.36665 , 0.0 , 0.02333 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => "Pausing time:", 
      Width => 14, 
      LeadingSpaces => 1, 
      Left => True, 
      ReportControl => R);
      
      Speed2 Invocation
         ( -0.82667 , 0.38332 , 0.0 , 0.015 , 0.0066666 
          Layer_ = 2
          ) : ReportInteger (
      Value => CurrentStep.Formula2.Formula.Int3, 
      Width => 9, 
      LeadingSpaces => 1, 
      ReportControl => R);
      
      UpTime Invocation
         ( -0.82667 , 0.36665 , 0.0 , 0.015 , 0.0066666 
          Layer_ = 2
          ) : ReportInteger (
      Value => CurrentStep.Formula2.Formula.Int1, 
      Width => 9, 
      LeadingSpaces => 1, 
      ReportControl => R);
      
      Reverse Invocation
         ( -0.74334 , 0.38332 , 0.0 , 0.015 , 0.0066666 
          Layer_ = 2
          ) : ReportBoolean (
      Value => CurrentStep.Formula2.Formula.Bool1, 
      Width => 9, 
      LeadingSpaces => 1, 
      ReportControl => R);
      
      DownTime Invocation
         ( -0.74334 , 0.36665 , 0.0 , 0.015 , 0.0066666 
          Layer_ = 2
          ) : ReportInteger (
      Value => CurrentStep.Formula2.Formula.Int2, 
      Width => 9, 
      LeadingSpaces => 1, 
      ReportControl => R);
      
      ResultInt2 Invocation
         ( -0.81667 , 0.53332 , 0.0 , 0.00499995 , 0.0066666 
          Layer_ = 2
          ) : ReportInteger (
      Value => CurrentStep.Result, 
      Width => 2, 
      ReportControl => R);
      
      RecHeadBatchIdLine Invocation
         ( -0.93333 , 0.74998 , 0.0 , 0.16545 , 0.17206 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => ControlRecipe, 
      ReportControl => R);
      
      RecHeadUnitLine Invocation
         ( -0.93333 , 0.73332 , 0.0 , 0.16455 , 0.17462 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => ControlRecipe, 
      ReportControl => R);
      
      BatchIdText Invocation
         ( -0.91667 , 0.74998 , 0.0 , 0.03333 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => "Batch id", 
      Width => 20, 
      Left => True, 
      ReportControl => R);
      
      BatchId Invocation
         ( -0.85 , 0.74998 , 0.0 , 0.06667 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => OpRecipeDocConn.OperationRecipe.Header.Batchidentification, 
      Width => 40, 
      Left => True, 
      ReportControl => R);
      
      UnitText Invocation
         ( -0.91667 , 0.73332 , 0.0 , 0.03333 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => "Unit", 
      Width => 20, 
      Left => True, 
      ReportControl => R);
      
      UnitName Invocation
         ( -0.85 , 0.73332 , 0.0 , 0.06667 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => OpRecipeDocConn.OperationRecipe.Operation.Parameters.UnitName, 
      Width => 40, 
      Left => True, 
      ReportControl => R);
      
      JumpStr2 Invocation
         ( -0.89667 , 0.51665 , 0.0 , 0.01667 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => "Jump to ", 
      Width => 10, 
      Left => True, 
      EnableModule => NormalStep, 
      ReportControl => R);
      
      JumpDestPhase2 Invocation
         ( -0.84333 , 0.51665 , 0.0 , 0.01667 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => JumpDestStepName, 
      Left => True, 
      EnableModule => NormalStep, 
      ReportControl => R);
      
      JumpResultStr2 Invocation
         ( -0.76667 , 0.51665 , 0.0 , 0.01667 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => " if Result is equal to ", 
      Width => 23, 
      Left => True, 
      EnableModule => NormalStep, 
      ReportControl => R);
      
      JumpResultInt2 Invocation
         ( -0.69667 , 0.51665 , 0.0 , 0.01667 , 0.0066666 
          Layer_ = 2
          ) : ReportInteger (
      Value => CurrentStep.Step.Jump.Result, 
      Width => 5, 
      EnableModule => NormalStep, 
      ReportControl => R);
      
   
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   Two_Layers_ LayerLimit_ = 0.95
   Zoomable
   GraphObjects :
      TextObject ( 0.92 , 0.08 ) ( -0.08 , -0.04 ) 
         "OpRecipeDocConn" 
         ConnectionNode ( 1.0 , 0.0 ) 
         LeftAligned 
         Layer_ = 1
         OutlineColour : Colour0 = -3 
      RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
         Layer_ = 1
         OutlineColour : Colour0 = -3 
      RectangleObject ( -1.0 , -1.0 ) ( 0.99998 , 0.99998 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      TextObject ( -0.92667 , 0.87665 ) ( -0.89667 , 0.88331 ) 
         "FirstLine" 
         ConnectionNode ( -0.93333 , 0.87998 ) 
         LeftAligned 
         Layer_ = 2
         Enable_ = True : InVar_ False 
         OutlineColour : Colour0 = -3 
      TextObject ( 0.22999 , -0.74667 ) ( 0.33665 , -0.72 ) 
         "LastLine" 
         ConnectionNode ( 0.28332 , -0.69334 ) 
         
         Layer_ = 2
         Enable_ = True : InVar_ False 
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.93333 , 0.44999 ) 
         ( -0.93333 , 0.430516 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.93333 , 0.41665 ) 
         ( -0.93333 , 0.397186 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.93333 , 0.15332 ) 
         ( -0.93333 , 0.147186 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.93333 , 0.13332 ) 
         ( -0.93333 , 0.130425 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      TextObject ( -0.92667 , 0.89331 ) ( -0.88 , 0.88665 ) 
         "HeaderEndLine" 
         ConnectionNode ( -0.93333 , 0.88998 ) 
         LeftAligned 
         Layer_ = 2
         Enable_ = True : InVar_ False 
         OutlineColour : Colour0 = -3 
      TextObject ( -0.92667 , 0.97665 ) ( -0.87667 , 0.96998 ) 
         "HeaderFirstLine" 
         ConnectionNode ( -0.93333 , 0.97331 ) 
         LeftAligned 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.93333 , 0.81665 ) 
         ( -0.93333 , 0.813846 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.93333 , 0.78332 ) 
         ( -0.93333 , 0.780516 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.93333 , 0.71665 ) 
         ( -0.93333 , 0.713846 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      TextObject ( -0.92 , 0.94665 ) ( -0.65 , 0.95665 ) 
         "Page Header" LeftAligned 
         Layer_ = 2
         Enable_ = True : InVar_ False 
         OutlineColour : Colour0 = 22 
      TextObject ( -0.65 , 0.89331 ) ( -0.65 , 0.87665 ) 
         "80" RightAligned 
         Layer_ = 2
         Enable_ = True : InVar_ False 
         OutlineColour : Colour0 = 22 
      TextObject ( -0.08334 , 0.89331 ) ( -0.08334 , 0.87665 ) 
         "80" RightAligned 
         Layer_ = 2
         Enable_ = True : InVar_ False 
         OutlineColour : Colour0 = 22 
      TextObject ( 0.56665 , 0.89665 ) ( 0.56665 , 0.87998 ) 
         "80" RightAligned 
         Layer_ = 2
         Enable_ = True : InVar_ False 
         OutlineColour : Colour0 = 22 
      TextObject ( -0.48001 , 0.89331 ) ( -0.48001 , 0.87665 ) 
         "132" RightAligned 
         Layer_ = 2
         Enable_ = True : InVar_ False 
         OutlineColour : Colour0 = 22 
      TextObject ( 0.08666 , 0.89331 ) ( 0.08666 , 0.87665 ) 
         "132" RightAligned 
         Layer_ = 2
         Enable_ = True : InVar_ False 
         OutlineColour : Colour0 = 22 
      TextObject ( 0.73665 , 0.89665 ) ( 0.73665 , 0.87998 ) 
         "132" RightAligned 
         Layer_ = 2
         Enable_ = True : InVar_ False 
         OutlineColour : Colour0 = 22 
      PolygonObject Polyline Connection ( -0.916851 , 0.923583 ) 
         ( -0.91667 , 0.923317 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.64667 , 0.923317 ) 
         ( -0.481805 , 0.923583 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.93333 , 0.97331 ) 
         ( -0.93333 , 0.930516 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.93333 , 0.91665 ) 
         ( -0.93333 , 0.913846 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 47 
      PolygonObject Polyline Connection ( -0.93333 , 0.89998 ) 
         ( -0.93333 , 0.88998 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 47 
      LineObject ( -0.48001 , 0.94998 ) ( -0.48001 , -0.66334 ) 
         Layer_ = 2
         Enable_ = True : InVar_ False 
         OutlineColour : Colour0 = 22 
      LineObject ( 0.08666 , 0.94998 ) ( 0.08666 , -0.66334 ) 
         Layer_ = 2
         Enable_ = True : InVar_ False 
         OutlineColour : Colour0 = 22 
      LineObject ( 0.73665 , 0.94998 ) ( 0.73665 , -0.66334 ) 
         Layer_ = 2
         Enable_ = True : InVar_ False 
         OutlineColour : Colour0 = 22 
      LineObject ( -0.65 , 0.94998 ) ( -0.65 , -0.66667 ) 
         Layer_ = 2
         Enable_ = True : InVar_ False 
         OutlineColour : Colour0 = 22 
      LineObject ( -0.08334 , 0.94998 ) ( -0.08334 , -0.66667 ) 
         Layer_ = 2
         Enable_ = True : InVar_ False 
         OutlineColour : Colour0 = 22 
      LineObject ( 0.56665 , 0.94998 ) ( 0.56665 , -0.66667 ) 
         Layer_ = 2
         Enable_ = True : InVar_ False 
         OutlineColour : Colour0 = 22 
      PolygonObject Polyline Connection ( -0.916845 , 0.506913 ) 
         ( -0.91667 , 0.506647 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.93333 , 0.123542 ) 
         ( -0.94667 , 0.31999 ) ( -0.94667 , 0.59332 ) 
         ( -0.93333 , 0.590253 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.916851 , 0.906913 ) 
         ( -0.91667 , 0.906647 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.916851 , 0.823583 ) 
         ( -0.91667 , 0.823317 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.916851 , 0.790253 ) 
         ( -0.91667 , 0.789987 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.916851 , 0.723583 ) 
         ( -0.91667 , 0.723317 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.916851 , 0.690253 ) 
         ( -0.91667 , 0.689987 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.91685 , 0.673583 ) 
         ( -0.91667 , 0.673317 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.85 , 0.823317 ) 
         ( -0.85001 , 0.823317 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.85 , 0.789987 ) 
         ( -0.85001 , 0.789987 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.85 , 0.723317 ) 
         ( -0.85001 , 0.723317 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.85 , 0.689987 ) 
         ( -0.85001 , 0.689987 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.85 , 0.673317 ) 
         ( -0.85001 , 0.673317 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.71666 , 0.823317 ) 
         ( -0.481805 , 0.823583 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.71666 , 0.789987 ) 
         ( -0.481805 , 0.790253 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.71666 , 0.723317 ) 
         ( -0.481805 , 0.723583 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.81666 , 0.689987 ) 
         ( -0.481805 , 0.690253 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.85 , 0.806647 ) 
         ( -0.916851 , 0.806913 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.85 , 0.773317 ) 
         ( -0.916851 , 0.773583 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.85 , 0.706647 ) 
         ( -0.916845 , 0.706913 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.85 , 0.81665 ) 
         ( -0.85 , 0.813313 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.85 , 0.78332 ) 
         ( -0.85 , 0.779983 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.85 , 0.71665 ) 
         ( -0.85 , 0.713313 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.78334 , 0.806647 ) 
         ( -0.78334 , 0.806647 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.78334 , 0.773317 ) 
         ( -0.78334 , 0.773317 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.71668 , 0.806647 ) 
         ( -0.481805 , 0.806913 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.71668 , 0.773317 ) 
         ( -0.481805 , 0.773583 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.71666 , 0.706647 ) 
         ( -0.481641 , 0.706913 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.93333 , 0.797186 ) 
         ( -0.93333 , 0.79998 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.93333 , 0.697186 ) 
         ( -0.93333 , 0.69998 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.85 , 0.796653 ) 
         ( -0.85 , 0.79998 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.85 , 0.729983 ) 
         ( -0.85 , 0.76665 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.85 , 0.696653 ) 
         ( -0.85 , 0.69998 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.93333 , 0.680516 ) 
         ( -0.93333 , 0.68332 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.85 , 0.679983 ) 
         ( -0.85 , 0.68332 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.78334 , 0.79998 ) 
         ( -0.78334 , 0.779983 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.8 , 0.673317 ) 
         ( -0.8 , 0.673317 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.75 , 0.673317 ) 
         ( -0.75 , 0.673317 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.7 , 0.673317 ) 
         ( -0.7 , 0.673317 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.65 , 0.673317 ) 
         ( -0.481778 , 0.673583 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.93333 , 0.11666 ) 
         ( -0.93333 , -0.69334 ) ( -0.40001 , -0.69334 ) 
         ( -0.40001 , 0.89998 ) ( -0.36667 , 0.89998 ) 
         ( -0.36667 , 0.900516 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.36667 , 0.88665 ) 
         ( -0.36667 , -0.69334 ) ( 0.23332 , -0.69334 ) 
         ( 0.23332 , 0.89998 ) ( 0.28332 , 0.89998 ) 
         ( 0.28332 , 0.870516 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( 0.28332 , 0.85665 ) 
         ( 0.28332 , -0.69334 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.350069 , 0.893583 ) 
         ( 0.0881974 , 0.893583 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( 0.299921 , 0.863583 ) 
         ( 0.738187 , 0.863583 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.916845 , 0.573583 ) 
         ( -0.481641 , 0.573583 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.916851 , 0.456923 ) 
         ( -0.88 , 0.456657 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.916851 , 0.423583 ) 
         ( -0.88 , 0.423317 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.83334 , 0.456657 ) 
         ( -0.82667 , 0.456657 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.83334 , 0.423317 ) 
         ( -0.82667 , 0.423317 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.79667 , 0.456657 ) 
         ( -0.481805 , 0.456923 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.79667 , 0.423317 ) 
         ( -0.481805 , 0.423583 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.93333 , 0.36665 ) 
         ( -0.93333 , 0.347186 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.916851 , 0.340253 ) 
         ( -0.88 , 0.339987 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.916851 , 0.323583 ) 
         ( -0.88 , 0.323317 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.83334 , 0.339987 ) 
         ( -0.82667 , 0.339987 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.83334 , 0.323317 ) 
         ( -0.82667 , 0.323317 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.79667 , 0.323317 ) 
         ( -0.79334 , 0.323317 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.76334 , 0.323317 ) 
         ( -0.76 , 0.323317 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.79667 , 0.339987 ) 
         ( -0.79334 , 0.339987 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.780007 , 0.339987 ) 
         ( -0.77667 , 0.339987 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.74667 , 0.339987 ) 
         ( -0.481805 , 0.340253 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.73 , 0.323317 ) 
         ( -0.481805 , 0.323583 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.93333 , 0.330516 ) 
         ( -0.93333 , 0.33332 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.481805 , 0.290253 ) 
         ( -0.693337 , 0.289987 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.93333 , 0.313856 ) 
         ( -0.93333 , 0.31665 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.93333 , 0.297186 ) 
         ( -0.93333 , 0.29999 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.79667 , 0.306657 ) 
         ( -0.78667 , 0.306657 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.79667 , 0.289987 ) 
         ( -0.78667 , 0.289987 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.77667 , 0.306657 ) 
         ( -0.783337 , 0.306657 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.77667 , 0.289987 ) 
         ( -0.783337 , 0.289987 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.74667 , 0.306657 ) 
         ( -0.74667 , 0.306657 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.74667 , 0.289987 ) 
         ( -0.74667 , 0.289987 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.73334 , 0.306657 ) 
         ( -0.730003 , 0.306657 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.73334 , 0.289987 ) 
         ( -0.730003 , 0.289987 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.7 , 0.306657 ) 
         ( -0.69667 , 0.306657 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.7 , 0.289987 ) 
         ( -0.69667 , 0.289987 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.481805 , 0.306923 ) 
         ( -0.693337 , 0.306657 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.88 , 0.306657 ) 
         ( -0.916851 , 0.306923 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.88 , 0.289987 ) 
         ( -0.916851 , 0.290253 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.83334 , 0.306657 ) 
         ( -0.82667 , 0.306657 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.83334 , 0.289987 ) 
         ( -0.82667 , 0.289987 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.93333 , 0.28332 ) 
         ( -0.93333 , 0.263856 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.83334 , 0.256657 ) 
         ( -0.83 , 0.256657 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.916851 , 0.256923 ) 
         ( -0.88 , 0.256657 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.76666 , 0.256657 ) 
         ( -0.481805 , 0.256923 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.481805 , 0.240253 ) 
         ( -0.66668 , 0.239987 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.481805 , 0.223583 ) 
         ( -0.7 , 0.223317 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.481805 , 0.206923 ) 
         ( -0.7 , 0.206657 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.481805 , 0.190253 ) 
         ( -0.7 , 0.189987 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.93333 , 0.24999 ) 
         ( -0.93333 , 0.247186 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.93333 , 0.23332 ) 
         ( -0.93333 , 0.230516 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.93333 , 0.21665 ) 
         ( -0.93333 , 0.213856 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.93333 , 0.19999 ) 
         ( -0.93333 , 0.197186 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.916851 , 0.240253 ) 
         ( -0.88 , 0.239987 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.916851 , 0.223583 ) 
         ( -0.88 , 0.223317 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.916851 , 0.206923 ) 
         ( -0.88 , 0.206657 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.916851 , 0.190253 ) 
         ( -0.88 , 0.189987 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.83334 , 0.239987 ) 
         ( -0.81667 , 0.239987 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.83334 , 0.223317 ) 
         ( -0.81667 , 0.223317 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.83334 , 0.206657 ) 
         ( -0.81667 , 0.206657 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.83334 , 0.189987 ) 
         ( -0.81667 , 0.189987 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.75001 , 0.239987 ) 
         ( -0.73334 , 0.239987 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.78333 , 0.223317 ) 
         ( -0.73334 , 0.223317 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.78333 , 0.206657 ) 
         ( -0.73334 , 0.206657 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.78333 , 0.189987 ) 
         ( -0.73334 , 0.189987 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.81667 , 0.23332 ) 
         ( -0.81667 , 0.229983 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.81667 , 0.21665 ) 
         ( -0.81667 , 0.213323 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.81667 , 0.19999 ) 
         ( -0.81667 , 0.196653 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.73334 , 0.23332 ) 
         ( -0.73334 , 0.229983 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.73334 , 0.21665 ) 
         ( -0.73334 , 0.213323 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.73334 , 0.19999 ) 
         ( -0.73334 , 0.196653 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      TextObject ( -0.91667 , 0.86665 ) ( -0.65 , 0.87665 ) 
         "Recipe header:" LeftAligned 
         Layer_ = 2
         OutlineColour : Colour0 = 22 
      TextObject ( -0.91667 , 0.63332 ) ( -0.65 , 0.64332 ) 
         "Procedure and formula:" LeftAligned 
         Layer_ = 2
         OutlineColour : Colour0 = 22 
      PolygonObject Polyline Connection ( -0.91685 , 0.856913 ) 
         ( -0.91667 , 0.856647 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.91685 , 0.840253 ) 
         ( -0.91667 , 0.839987 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.78333 , 0.856647 ) 
         ( -0.481778 , 0.856913 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.78333 , 0.839987 ) 
         ( -0.481778 , 0.840253 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.93333 , 0.87998 ) 
         ( -0.93333 , 0.863846 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.93333 , 0.84998 ) 
         ( -0.93333 , 0.847186 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.93333 , 0.61665 ) 
         ( -0.93333 , 0.613846 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.93333 , 0.83332 ) 
         ( -0.93333 , 0.830516 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.93333 , 0.59998 ) 
         ( -0.93333 , 0.597186 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      TextObject ( -0.91667 , 0.46665 ) ( -0.65 , 0.47665 ) 
         "Heating phase:" LeftAligned 
         Layer_ = 2
         OutlineColour : Colour0 = 22 
      TextObject ( -0.91667 , 0.43332 ) ( -0.65 , 0.44332 ) 
         "Agitation 1 phase:" LeftAligned 
         Layer_ = 2
         OutlineColour : Colour0 = 22 
      TextObject ( -0.91667 , 0.39999 ) ( -0.65 , 0.40999 ) 
         "Agitation 2 phase:" LeftAligned 
         Layer_ = 2
         OutlineColour : Colour0 = 22 
      TextObject ( -0.91667 , 0.34999 ) ( -0.65 , 0.35999 ) 
         "Ramping phase:" LeftAligned 
         Layer_ = 2
         OutlineColour : Colour0 = 22 
      TextObject ( -0.91667 , 0.26665 ) ( -0.65 , 0.27665 ) 
         "Filling phase:" LeftAligned 
         Layer_ = 2
         OutlineColour : Colour0 = 22 
      PolygonObject Polyline Connection ( -0.88 , 0.24999 ) 
         ( -0.88 , 0.246653 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.88 , 0.23332 ) 
         ( -0.88 , 0.229983 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.88 , 0.21665 ) 
         ( -0.88 , 0.213323 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.88 , 0.19999 ) 
         ( -0.88 , 0.196653 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.91685 , 0.656913 ) 
         ( -0.481778 , 0.656913 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.93333 , 0.38332 ) 
         ( -0.93333 , 0.380516 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.916851 , 0.390253 ) 
         ( -0.88 , 0.389987 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.916851 , 0.373583 ) 
         ( -0.88 , 0.373317 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.83334 , 0.389987 ) 
         ( -0.82667 , 0.389987 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.83334 , 0.373317 ) 
         ( -0.82667 , 0.373317 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.75001 , 0.389987 ) 
         ( -0.74334 , 0.389987 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.75001 , 0.373317 ) 
         ( -0.74334 , 0.373317 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.79667 , 0.389987 ) 
         ( -0.79667 , 0.389987 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.79667 , 0.373317 ) 
         ( -0.79667 , 0.373317 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.71334 , 0.389987 ) 
         ( -0.481805 , 0.390253 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.71334 , 0.373317 ) 
         ( -0.481805 , 0.373583 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.93333 , 0.18332 ) 
         ( -0.93333 , 0.167186 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.80667 , 0.539987 ) 
         ( -0.481778 , 0.540253 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 Colour1 = -3 
      PolygonObject Polyline Connection ( -0.93333 , 0.76665 ) 
         ( -0.93333 , 0.763745 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.93333 , 0.74998 ) 
         ( -0.93333 , 0.74729 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.93333 , 0.73332 ) 
         ( -0.93333 , 0.730516 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.916785 , 0.756862 ) 
         ( -0.91667 , 0.756647 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.85001 , 0.756647 ) 
         ( -0.85 , 0.756647 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.71666 , 0.756647 ) 
         ( -0.479997 , 0.756862 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.916875 , 0.740305 ) 
         ( -0.91667 , 0.739987 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.85001 , 0.739987 ) 
         ( -0.85 , 0.739987 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.71666 , 0.739987 ) 
         ( -0.482463 , 0.740305 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.93333 , 0.56665 ) 
         ( -0.93333 , 0.563846 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.93333 , 0.54998 ) 
         ( -0.93333 , 0.547186 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.93333 , 0.58332 ) 
         ( -0.93333 , 0.580516 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.93333 , 0.53332 ) 
         ( -0.93333 , 0.530516 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.93333 , 0.51665 ) 
         ( -0.93333 , 0.513846 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.91685 , 0.523583 ) 
         ( -0.89667 , 0.523317 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.80999 , 0.523317 ) 
         ( -0.76667 , 0.523317 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.73333 , 0.523317 ) 
         ( -0.69667 , 0.523317 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.66333 , 0.523317 ) 
         ( -0.481778 , 0.523583 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.86333 , 0.523317 ) 
         ( -0.84333 , 0.523317 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.93333 , 0.66665 ) 
         ( -0.93333 , 0.663846 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.93333 , 0.64998 ) 
         ( -0.93333 , 0.630516 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.93333 , 0.49998 ) 
         ( -0.93333 , 0.497186 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.93333 , 0.48332 ) 
         ( -0.93333 , 0.463856 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.88333 , 0.506647 ) 
         ( -0.87667 , 0.506647 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.81333 , 0.506647 ) 
         ( -0.481641 , 0.506913 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.91685 , 0.490253 ) 
         ( -0.91667 , 0.489987 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.78333 , 0.489987 ) 
         ( -0.481778 , 0.490253 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.78333 , 0.923317 ) 
         ( -0.78334 , 0.923317 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.71668 , 0.923317 ) 
         ( -0.66667 , 0.923317 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.78333 , 0.906647 ) 
         ( -0.481805 , 0.906913 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.91685 , 0.623583 ) 
         ( -0.91667 , 0.623317 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.85001 , 0.623317 ) 
         ( -0.83333 , 0.623317 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.76667 , 0.623317 ) 
         ( -0.481778 , 0.623583 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.91685 , 0.606913 ) 
         ( -0.91667 , 0.606646 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.85001 , 0.606646 ) 
         ( -0.83333 , 0.606646 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.76667 , 0.606646 ) 
         ( -0.481778 , 0.606913 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.916846 , 0.556913 ) 
         ( -0.91667 , 0.556647 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.81667 , 0.556647 ) 
         ( -0.481668 , 0.556913 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.81667 , 0.539987 ) 
         ( -0.81667 , 0.539987 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.91685 , 0.540253 ) 
         ( -0.91667 , 0.539987 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.916851 , 0.160253 ) 
         ( -0.91667 , 0.159987 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.81667 , 0.159987 ) 
         ( -0.481805 , 0.160253 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.916851 , 0.140253 ) 
         ( -0.91667 , 0.139987 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.81667 , 0.139987 ) 
         ( -0.481805 , 0.140253 ) 
         Layer_ = 2
   InteractObjects :
      ProcedureInteract ( -0.8 , -0.8 ) ( 0.8 , 0.8 ) 
         ToggleWindow
         "" : InVar_ LitString "*Info" "" False : InVar_ True 0.0 0.0 0.0 : 
         InVar_ 0.24 0.0 False 0 0 False : OutVar_ "windowenable" 0 
         Layer_ = 1
         Variable = 0.0 
   
   ModuleCode
   EQUATIONBLOCK Code COORD -0.93333, -0.93333 OBJSIZE 0.26666, 0.13333
   Layer_ = 2 :
      IF NewDocument THEN
         ClearString(InternalFileName);
         Concatenate(Filename, FileExtension, InternalFileName, Status);
         NewDocument = Off;
         InitTable = On;
      ENDIF;
   
   ENDDEF (*OpRecipeDocument*);
   
   RecipeDocument = MODULEDEFINITION DateCode_ 323518368
   MODULEPARAMETERS
      Name "IN Module name": string  := "Recipe Documentation";
      FileName "IN Name of the local file containing the recipe document": 
      string  := "RecipeDoc";
      FileExtension "IN File extension for the local file": string  := ".";
      RecipeDocConnection 
      "IN <=> NODE Connection to RecipeManager and/or OperationControlExt": 
      RecipeDocConnType ;
      PrinterType "IN 1= textprinter, 2 = postscript printer", PrinterNo 
      "IN The number of the printer, e.g. 2 if TextPrinter2 is used": integer  
      := 1;
      PrinterSystem "IN System name where printer resides": string  := "";
      AutoPrint "IN If true, the file is printed when it has been created": 
      boolean  := False;
      PageLength 
      "IN Number of lines in page for textfile. If PrinterType = 2 it should be <= (PageLengthPS-1)."
      : integer  := 65;
      PageLengthPS 
      "IN PageLength for PostScript module (PrinterType =2). Controls pagebreak and textsize"
      : integer  := 66;
      PageWidth "IN Number of characters per line": integer  := 80;
      Append "IN Append to existing file": boolean  := False;
      TrailingFormFeed "IN If true then a formfeed is added after the text": 
      boolean  := True;
      LeadingFormFeed 
      "IN If true then a formfeed is inserted  before  the text": boolean  := 
      False;
      FontSize 
      "IN Font size in pop-up window for inspection of documented recipe": 
      integer  := 12;
   LOCALVARIABLES
      R "Common data for line and field modules.": ReportCommon ;
      FirstLine "Used by library modules.", LastLine "Used by library modules."
      , HeaderFirstLine "Used by library modules.", HeaderEndLine 
      "Used by library modules.": LineConnection ;
      ExecuteState "Used by library modules.": boolean State;
      NewDocument 
      "Used by library modules. True when a new recipe document is initiated.": 
      boolean ;
      InitTable: boolean  := False;
      ControlRecipe 
      "Used by library modules. True when recipe is a control recipe. False if it's a master recipe."
      , StartOfParallel, EndOfParallel, StartOfAlternative, EndOfAlternative, 
      LastStep, MoreSteps, Jump, Direct, NormalOperation: boolean ;
      CurrentOperation: ReportRecStepType ;
      InternalFileName: string ;
      Status: integer ;
      PreDirectOpRecName: string ;
      JumpDestOpName: IdentString ;
   SUBMODULES
      icon Invocation
         ( -1.0 , -1.0 , 0.0 , 2.0 , 2.0 
          Layer_ = 1
          ZoomLimits = 0.5 0.01 ) : RecipeDocumentIcon (
      error => R.error);
      
      RecHeadMasterLine2 Invocation
         ( -0.93333 , 0.79998 , 0.0 , 0.16479 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      ReportControl => R);
      
      RecMasterModLine2 Invocation
         ( -0.93333 , 0.76665 , 0.0 , 0.16479 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      ReportControl => R);
      
      RecHeadControlLine2 Invocation
         ( -0.93333 , 0.73332 , 0.0 , 0.16479 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => ControlRecipe, 
      ReportControl => R);
      
      RecHeadControlMod2 Invocation
         ( -0.93333 , 0.69998 , 0.0 , 0.16479 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => ControlRecipe, 
      ReportControl => R);
      
      RecHeadBatchIdLine Invocation
         ( -0.93333 , 0.68332 , 0.0 , 0.16479 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => ControlRecipe, 
      ReportControl => R);
      
      RecHeadProductLine2 Invocation
         ( -0.93333 , 0.64998 , 0.0 , 0.16485 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      ReportControl => R);
      
      RecHeadMasterLine1 Invocation
         ( -0.93333 , 0.81665 , 0.0 , 0.16479 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      ReportControl => R);
      
      RecHeadMasterMod1 Invocation
         ( -0.93333 , 0.78332 , 0.0 , 0.16479 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      ReportControl => R);
      
      RecHeadControlLine1 Invocation
         ( -0.93333 , 0.74998 , 0.0 , 0.16479 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => ControlRecipe, 
      ReportControl => R);
      
      RecHeadControlMod1 Invocation
         ( -0.93333 , 0.71665 , 0.0 , 0.16479 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => ControlRecipe, 
      ReportControl => R);
      
      RecHeadProductLine1 Invocation
         ( -0.93333 , 0.66665 , 0.0 , 0.16479 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      ReportControl => R);
      
      RecHeadScaleFactLine Invocation
         ( -0.93333 , 0.63332 , 0.0 , 0.16479 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      ReportControl => R);
      
      RecHeadLoggingLine Invocation
         ( -0.93333 , 0.61665 , 0.0 , 0.1648 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      ReportControl => R);
      
      RecHeadEmptyLine Invocation
         ( -0.93333 , 0.59998 , 0.0 , 0.1648 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      ReportControl => R);
      
      RecHeadTitleLine1 Invocation
         ( -0.93333 , 0.84998 , 0.0 , 0.1648 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      ReportControl => R);
      
      ProcedureTitleLine1 Invocation
         ( -0.93333 , 0.56665 , 0.0 , 0.1648 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      ReportControl => R);
      
      RecHeadTitleLine2 Invocation
         ( -0.93333 , 0.83332 , 0.0 , 0.1648 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      ReportControl => R);
      
      ProcedureTitleLine2 Invocation
         ( -0.93333 , 0.54998 , 0.0 , 0.1648 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      ReportControl => R);
      
      Dummyline1 Invocation
         ( -0.36667 , 0.85665 , 0.0 , 0.16601 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => False, 
      ReportControl => R);
      
      DummyLine2 Invocation
         ( 0.28332 , 0.85665 , 0.0 , 0.16601 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => False, 
      ReportControl => R);
      
      AcceptLine Invocation
         ( -0.93333 , 0.49998 , 0.0 , 0.16601 , 0.17333 
          Layer_ = 2
          ) : ReportControlAccept (
      ReportControl => R);
      
      ReportRecipeTrace Invocation
         ( -0.93333 , 0.48332 , 0.0 , 0.16485 , 0.17333 
          Layer_ = 2
          ) : ReportRecipeTrace (
      ReadFirstStep => InitTable, 
      Recipe => RecipeDocConnection.Recipe, 
      CurrentOperation => CurrentOperation, 
      StartOfParallel => StartOfParallel, 
      EndOfParallel => EndOfParallel, 
      StartOfAlternative => StartOfAlternative, 
      EndOfAlternative => EndOfAlternative, 
      LastStep => LastStep, 
      MoreSteps => MoreSteps, 
      Direct => Direct, 
      NormalOperation => NormalOperation, 
      Jump => Jump, 
      ReportControl => R, 
      PreDirectOpRecName => PreDirectOpRecName, 
      JumpDestOpName => JumpDestOpName);
      
      StartParLine Invocation
         ( -0.93333 , 0.46665 , 0.0 , 0.16484 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => StartOfParallel, 
      ReportControl => R);
      
      StartAltLine Invocation
         ( -0.93333 , 0.44999 , 0.0 , 0.1648 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => StartOfAlternative, 
      ReportControl => R);
      
      OperationNameLine Invocation
         ( -0.93333 , 0.43332 , 0.0 , 0.16485 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => NormalOperation, 
      ReportControl => R);
      
      OperationDescrLine Invocation
         ( -0.93333 , 0.41665 , 0.0 , 0.16485 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => NormalOperation, 
      ReportControl => R);
      
      AutoBooleanLine Invocation
         ( -0.93333 , 0.16666 , 0.0 , 0.16485 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => NormalOperation, 
      ReportControl => R);
      
      OpRecipeLine Invocation
         ( -0.93333 , 0.14999 , 0.0 , 0.16485 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      ReportControl => R);
      
      JumpLine1 Invocation
         ( -0.93333 , 0.39832 , 0.0 , 0.16485 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => Jump, 
      ReportControl => R);
      
      ProcedureEmptyLine Invocation
         ( -0.93333 , 0.53332 , 0.0 , 0.16485 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      ReportControl => R);
      
      DirectTransitionLine Invocation
         ( -0.93333 , 0.34999 , 0.0 , 0.16485 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => Direct, 
      ReportControl => R);
      
      JumpLine2 Invocation
         ( -0.93333 , 0.38165 , 0.0 , 0.16485 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => Jump, 
      ReportControl => R);
      
      PhaseStateLine1 Invocation
         ( -0.93333 , 0.31665 , 0.0 , 0.16485 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => CurrentOperation.Connected1, 
      ReportControl => R);
      
      PhaseStateLine2 Invocation
         ( -0.93333 , 0.28332 , 0.0 , 0.16485 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableWriteToFile => CurrentOperation.Connected2, 
      ReportControl => R);
      
      PhaseStateLine3 Invocation
         ( -0.93333 , 0.24999 , 0.0 , 0.16485 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => CurrentOperation.Connected3, 
      ReportControl => R);
      
      PhaseStateLine4 Invocation
         ( -0.93333 , 0.21665 , 0.0 , 0.16485 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableWriteToFile => CurrentOperation.Connected4, 
      ReportControl => R);
      
      PhaseStateLine5 Invocation
         ( -0.93333 , 0.18332 , 0.0 , 0.16485 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => CurrentOperation.Connected5, 
      ReportControl => R);
      
      AllocPhaseLine1 Invocation
         ( -0.93333 , 0.33332 , 0.0 , 0.16485 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => CurrentOperation.Connected1, 
      ReportControl => R);
      
      AllocPhaseLine2 Invocation
         ( -0.93333 , 0.29999 , 0.0 , 0.16485 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableWriteToFile => CurrentOperation.Connected2, 
      ReportControl => R);
      
      AllocPhaseLine3 Invocation
         ( -0.93333 , 0.26665 , 0.0 , 0.16485 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => CurrentOperation.Connected3, 
      ReportControl => R);
      
      AllocPhaseLine4 Invocation
         ( -0.93333 , 0.23332 , 0.0 , 0.16485 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => CurrentOperation.Connected4, 
      ReportControl => R);
      
      AllocPhaseLine5 Invocation
         ( -0.93333 , 0.19999 , 0.0 , 0.16485 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => CurrentOperation.Connected5, 
      ReportControl => R);
      
      EndStepLine Invocation
         ( -0.93333 , 0.36499 , 0.0 , 0.16485 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => CurrentOperation.Operation.RecipeProcedure.EndStep, 
      ReportControl => R);
      
      RequiredUnitLine Invocation
         ( -0.93333 , 0.11666 , 0.0 , 0.16479 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => CurrentOperation.Operation.RequiredUnit.Used, 
      ReportControl => R);
      
      EquipIntLine Invocation
         ( -0.93333 , 0.08332 , 0.0 , 0.16479 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => CurrentOperation.Operation.EquipmentRequirement.MinVolume
      .Used, 
      ReportControl => R);
      
      EquipBooleanLine Invocation
         ( -0.93333 , 0.06666 , 0.0 , 0.16479 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => CurrentOperation.Operation.EquipmentRequirement.
      AgitatorPresent.Used, 
      ReportControl => R);
      
      EndAltLine Invocation
         ( -0.93333 , -0.06668 , 0.0 , 0.16479 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => EndOfALternative, 
      ReportControl => R);
      
      EndParLine Invocation
         ( -0.93333 , -0.08334 , 0.0 , 0.16479 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => EndOfParallel, 
      ReportControl => R);
      
      DivertLine Invocation
         ( -0.93333 , -0.10001 , 0.0 , 0.16667 , 0.17396 
          Layer_ = 2
          ) : ReportControlDivert (
      Continue => LastStep, 
      Divert => MoreSteps, 
      ReportControl => R);
      
      PageHeaderLine1 Invocation
         ( -0.93333 , 0.91665 , 0.0 , 0.16479 , 0.17333 
          Layer_ = 2
          ) : ReportLine (
      ReportControl => R);
      
      HeaderLine2 Invocation
         ( -0.93333 , 0.89998 , 0.0 , 0.16333 , 0.1718 
          Layer_ = 2
          ) : ReportLine (
      EnableModule => ControlRecipe, 
      ReportControl => R);
      
      MasterRecipeName Invocation
         ( -0.91667 , 0.91665 , 0.0 , 0.06667 , 0.00666659 
          Layer_ = 2
          ) : ReportString (
      Value => RecipeDocConnection.Recipe.Header.MasterRecipeName, 
      Width => 40, 
      Left => True, 
      ReportControl => R);
      
      MasterRecName Invocation
         ( -0.85 , 0.81665 , 0.0 , 0.06667 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => RecipeDocConnection.Recipe.Header.MasterRecipeName, 
      Width => 40, 
      Left => True, 
      ReportControl => R);
      
      MasterRecModAuthor Invocation
         ( -0.81667 , 0.78332 , 0.0 , 0.06667 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => RecipeDocConnection.Recipe.Header.MasterModifyAuthor, 
      Width => 40, 
      Left => True, 
      ReportControl => R);
      
      ControlRecName Invocation
         ( -0.85 , 0.74998 , 0.0 , 0.06667 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => RecipeDocConnection.Recipe.Header.ControlRecipeName, 
      Width => 40, 
      Left => True, 
      ReportControl => R);
      
      ControlRecModAuthor Invocation
         ( -0.81667 , 0.71665 , 0.0 , 0.06667 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => RecipeDocConnection.Recipe.Header.ControlModifyAuthor, 
      Width => 40, 
      Left => True, 
      ReportControl => R);
      
      ProductCode Invocation
         ( -0.88333 , 0.66665 , 0.0 , 0.06667 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => RecipeDocConnection.Recipe.Header.ProductCode, 
      Width => 40, 
      Left => True, 
      ReportControl => R);
      
      ScaleFactor Invocation
         ( -0.85 , 0.63332 , 0.0 , 0.01667 , 0.0066666 
          Layer_ = 2
          ) : ReportReal (
      Value => RecipeDocConnection.Recipe.Header.ScaleFactor, 
      Width => 10, 
      ReportControl => R);
      
      LogAlarms Invocation
         ( -0.88333 , 0.61665 , 0.0 , 0.025 , 0.0066666 
          Layer_ = 2
          ) : ReportBoolean (
      Value => RecipeDocConnection.Recipe.Header.LogAlarms, 
      OnText => "Alarms ON", 
      OffText => "Alarms OFF", 
      Left => True, 
      Width => 15, 
      ReportControl => R);
      
      LogInteraction Invocation
         ( -0.83333 , 0.61665 , 0.0 , 0.025 , 0.0066666 
          Layer_ = 2
          ) : ReportBoolean (
      Value => RecipeDocConnection.Recipe.Header.LogInteraction, 
      OnText => "Interaction ON", 
      OffText => "Interaction OFF", 
      Left => True, 
      Width => 15, 
      ReportControl => R);
      
      LogHistory Invocation
         ( -0.78334 , 0.61665 , 0.0 , 0.025 , 0.0066666 
          Layer_ = 2
          ) : ReportBoolean (
      Value => RecipeDocConnection.Recipe.Header.LogHistory, 
      OnText => "History ON", 
      OffText => "History OFF", 
      Left => True, 
      Width => 15, 
      ReportControl => R);
      
      AutoAllocation Invocation
         ( -0.86667 , 0.16666 , 0.0 , 0.03333 , 0.00666659 
          Layer_ = 2
          ) : ReportBoolean (
      Value => CurrentOperation.Operation.Header.AutoAllocation, 
      OnText => "Autoallocation ON", 
      OffText => "Autoallocation OFF", 
      Left => True, 
      Width => 20, 
      ReportControl => R);
      
      AutoStart Invocation
         ( -0.8 , 0.16666 , 0.0 , 0.025 , 0.0066666 
          Layer_ = 2
          ) : ReportBoolean (
      Value => CurrentOperation.Operation.Header.AutoStart, 
      OnText => "Autostart ON", 
      OffText => "Autostart OFF", 
      Left => True, 
      Width => 15, 
      ReportControl => R);
      
      AutoExecution Invocation
         ( -0.75 , 0.16666 , 0.0 , 0.03333 , 0.00666659 
          Layer_ = 2
          ) : ReportBoolean (
      Value => CurrentOperation.Operation.Header.AutoExecution, 
      OnText => "Autoexecution ON", 
      OffText => "Autoexecution OFF", 
      Left => True, 
      Width => 20, 
      ReportControl => R);
      
      LogTracking Invocation
         ( -0.73334 , 0.61665 , 0.0 , 0.025 , 0.0066666 
          Layer_ = 2
          ) : ReportBoolean (
      Value => RecipeDocConnection.Recipe.Header.LogTracking, 
      OnText => "Tracking ON", 
      OffText => "Tracking OFF", 
      Left => True, 
      Width => 15, 
      ReportControl => R);
      
      ControlRecipeName Invocation
         ( -0.91667 , 0.89998 , 0.0 , 0.06667 , 0.00666659 
          Layer_ = 2
          ) : ReportString (
      Value => RecipeDocConnection.Recipe.Header.ControlRecipeName, 
      Width => 40, 
      Left => True, 
      ReportControl => R);
      
      ReportGenTime Invocation
         ( -0.78334 , 0.91665 , 0.0 , 0.03333 , 0.00666659 
          Layer_ = 2
          ) : ReportTime (
      Value => R.TimeOfReportGen, 
      Width => 20, 
      Left => True, 
      ReportControl => R);
      
      PageNo Invocation
         ( -0.71667 , 0.91665 , 0.0 , 0.01667 , 0.00666659 
          Layer_ = 2
          ) : ReportInteger (
      Value => R.CurrentPage, 
      Width => 5, 
      LeadingSpaces => 15, 
      ReportControl => R);
      
      StartParallel Invocation
         ( -0.91667 , 0.46665 , 0.0 , 0.05 , 0.00666659 
          Layer_ = 2
          ) : ReportString (
      Value => "- Parallel branch -", 
      Width => 30, 
      Left => True, 
      ReportControl => R);
      
      StartAlternative Invocation
         ( -0.91667 , 0.44999 , 0.0 , 0.05 , 0.00666659 
          Layer_ = 2
          ) : ReportString (
      Value => "- Alternative branch -", 
      Width => 30, 
      Left => True, 
      ReportControl => R);
      
      OperationName Invocation
         ( -0.91667 , 0.43332 , 0.0 , 0.03333 , 0.00666659 
          Layer_ = 2
          ) : ReportString (
      Value => CurrentOperation.Operation.Header.Name, 
      Width => 20, 
      Left => True, 
      ReportControl => R);
      
      OperationDescription Invocation
         ( -0.9 , 0.41665 , 7.94729E-07 , 0.06667 , 0.00666646 
          Layer_ = 2
          ) : ReportString (
      Value => CurrentOperation.Operation.Header.Description, 
      Width => 40, 
      LeadingSpaces => 5, 
      Left => True, 
      ReportControl => R);
      
      DirectTransitionText Invocation
         ( -0.91667 , 0.34999 , 7.94729E-07 , 0.08333 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => "No operation, direct conditional transition", 
      Width => 50, 
      Left => True, 
      ReportControl => R);
      
      AutoText Invocation
         ( -0.9 , 0.16666 , 0.0 , 0.01667 , 0.00666659 
          Layer_ = 2
          ) : ReportString (
      Value => "Auto", 
      Width => 10, 
      LeadingSpaces => 5, 
      Left => True, 
      ReportControl => R);
      
      OpRecipeText Invocation
         ( -0.9 , 0.14999 , 0.0 , 0.03333 , 0.00666659 
          Layer_ = 2
          ) : ReportString (
      Value => "Operation recipe", 
      Width => 20, 
      LeadingSpaces => 5, 
      Left => True, 
      ReportControl => R);
      
      OpRecipe Invocation
         ( -0.83333 , 0.14999 , 0.0 , 0.03333 , 0.00666655 
          Layer_ = 2
          ) : ReportBoolean (
      Value => NormalOperation, 
      OnText => CurrentOperation.Operation.OperationRecipe, 
      OffText => PreDirectOpRecName, 
      Left => True, 
      Width => 20, 
      ReportControl => R);
      
      RequiredUnitText Invocation
         ( -0.9 , 0.11666 , 0.0 , 0.03333 , 0.00666659 
          Layer_ = 2
          ) : ReportString (
      Value => "Required unit", 
      Width => 20, 
      LeadingSpaces => 5, 
      Left => True, 
      EnableModule => NormalOperation, 
      ReportControl => R);
      
      RequiredUnit Invocation
         ( -0.83333 , 0.11666 , 0.0 , 0.03333 , 0.00666659 
          Layer_ = 2
          ) : ReportString (
      Value => CurrentOperation.Operation.RequiredUnit.Value, 
      Width => 20, 
      EnableModule => NormalOperation, 
      ReportControl => R);
      
      EquipIntText Invocation
         ( -0.9 , 0.08332 , 0.0 , 0.03333 , 0.00666655 
          Layer_ = 2
          ) : ReportString (
      Value => "Minimum Volume : ", 
      Width => 20, 
      LeadingSpaces => 5, 
      Left => True, 
      EnableModule => NormalOperation, 
      ReportControl => R);
      
      EquipInt Invocation
         ( -0.83333 , 0.08332 , 0.0 , 0.01667 , 0.0066666 
          Layer_ = 2
          ) : ReportInteger (
      Value => CurrentOperation.Operation.EquipmentRequirement.MinVolume.Value, 
      EnableModule => NormalOperation, 
      ReportControl => R);
      
      EquipBooleanText Invocation
         ( -0.9 , 0.06666 , 0.0 , 0.05 , 0.00666655 
          Layer_ = 2
          ) : ReportBoolean (
      Value => CurrentOperation.Operation.EquipmentRequirement.AgitatorPresent.
      Value, 
      OnText => "Agitator is present", 
      OffText => "Agitator is NOT present", 
      Left => True, 
      Width => 30, 
      LeadingSpaces => 5, 
      EnableModule => NormalOperation, 
      ReportControl => R);
      
      JumpStr Invocation
         ( -0.91667 , 0.39832 , 0.0 , 0.05 , 0.00666651 
          Layer_ = 2
          ) : ReportBoolean (
      Value => CurrentOperation.Operation.RecipeProcedure.Jump.Parallel, 
      OnText => "- Parallel jump to ", 
      OffText => "- Alternative jump to ", 
      Left => True, 
      Width => 30, 
      EnableModule => NormalOperation, 
      ReportControl => R);
      
      AllocPhaseText1 Invocation
         ( -0.9 , 0.33332 , 0.0 , 0.03333 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => "AllocationPhase1", 
      Width => 20, 
      LeadingSpaces => 5, 
      Left => True, 
      ReportControl => R);
      
      AllocPhaseText2 Invocation
         ( -0.9 , 0.29999 , 0.0 , 0.03333 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => "AllocationPhase2", 
      Width => 20, 
      LeadingSpaces => 5, 
      Left => True, 
      ReportControl => R);
      
      AllocPhaseText3 Invocation
         ( -0.9 , 0.26665 , 0.0 , 0.03333 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => "AllocationPhase3", 
      Width => 20, 
      LeadingSpaces => 5, 
      Left => True, 
      ReportControl => R);
      
      AllocPhaseText4 Invocation
         ( -0.9 , 0.23332 , 0.0 , 0.03333 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => "AllocationPhase4", 
      Width => 20, 
      LeadingSpaces => 5, 
      Left => True, 
      ReportControl => R);
      
      AllocPhaseText5 Invocation
         ( -0.9 , 0.19999 , 0.0 , 0.03333 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => "AllocationPhase5", 
      Width => 20, 
      LeadingSpaces => 5, 
      Left => True, 
      ReportControl => R);
      
      AllocPhase1 Invocation
         ( -0.83333 , 0.33332 , 0.0 , 0.03333 , 0.00666659 
          Layer_ = 2
          ) : ReportString (
      Value => CurrentOperation.AllocationPhase1, 
      Width => 20, 
      Left => True, 
      ReportControl => R);
      
      AllocPhase2 Invocation
         ( -0.83333 , 0.29999 , 0.0 , 0.03333 , 0.00666659 
          Layer_ = 2
          ) : ReportString (
      Value => CurrentOperation.AllocationPhase2, 
      Width => 20, 
      Left => True, 
      ReportControl => R);
      
      AllocPhase3 Invocation
         ( -0.83333 , 0.26665 , 0.0 , 0.03333 , 0.00666659 
          Layer_ = 2
          ) : ReportString (
      Value => CurrentOperation.AllocationPhase3, 
      Width => 20, 
      Left => True, 
      ReportControl => R);
      
      AllocPhase4 Invocation
         ( -0.83333 , 0.23332 , 0.0 , 0.03333 , 0.00666659 
          Layer_ = 2
          ) : ReportString (
      Value => CurrentOperation.AllocationPhase4, 
      Width => 20, 
      Left => True, 
      ReportControl => R);
      
      AllocPhase5 Invocation
         ( -0.83333 , 0.19999 , 0.0 , 0.03333 , 0.00666659 
          Layer_ = 2
          ) : ReportString (
      Value => CurrentOperation.AllocationPhase5, 
      Width => 20, 
      Left => True, 
      ReportControl => R);
      
      PhaseStateText1 Invocation
         ( -0.9 , 0.31665 , 0.0 , 0.03333 , 0.00666659 
          Layer_ = 2
          ) : ReportString (
      Value => "PhaseState1", 
      Width => 20, 
      LeadingSpaces => 5, 
      Left => True, 
      ReportControl => R);
      
      PhaseStateText2 Invocation
         ( -0.9 , 0.28332 , 0.0 , 0.03333 , 0.00666659 
          Layer_ = 2
          ) : ReportString (
      Value => "PhaseState", 
      Width => 20, 
      LeadingSpaces => 5, 
      Left => True, 
      ReportControl => R);
      
      PhaseStateText3 Invocation
         ( -0.9 , 0.24999 , 0.0 , 0.03333 , 0.00666659 
          Layer_ = 2
          ) : ReportString (
      Value => "PhaseState3", 
      Width => 20, 
      LeadingSpaces => 5, 
      Left => True, 
      ReportControl => R);
      
      PhaseStateText4 Invocation
         ( -0.9 , 0.21665 , 0.0 , 0.03333 , 0.00666659 
          Layer_ = 2
          ) : ReportString (
      Value => "PhaseState4", 
      Width => 20, 
      LeadingSpaces => 5, 
      Left => True, 
      ReportControl => R);
      
      PhaseStateText5 Invocation
         ( -0.9 , 0.18332 , 0.0 , 0.03333 , 0.00666659 
          Layer_ = 2
          ) : ReportString (
      Value => "PhaseState5", 
      Width => 20, 
      LeadingSpaces => 5, 
      Left => True, 
      ReportControl => R);
      
      PhaseState1 Invocation
         ( -0.83333 , 0.31665 , 0.0 , 0.01667 , 0.0066666 
          Layer_ = 2
          ) : ReportInteger (
      Value => CurrentOperation.PhaseState1, 
      ReportControl => R);
      
      PhaseState2 Invocation
         ( -0.83333 , 0.28332 , 0.0 , 0.01667 , 0.0066666 
          Layer_ = 2
          ) : ReportInteger (
      Value => CurrentOperation.PhaseState2, 
      ReportControl => R);
      
      PhaseState3 Invocation
         ( -0.83333 , 0.24999 , 0.0 , 0.01667 , 0.0066666 
          Layer_ = 2
          ) : ReportInteger (
      Value => CurrentOperation.PhaseState3, 
      ReportControl => R);
      
      PhaseState4 Invocation
         ( -0.83333 , 0.21665 , 0.0 , 0.01667 , 0.0066666 
          Layer_ = 2
          ) : ReportInteger (
      Value => CurrentOperation.PhaseState4, 
      ReportControl => R);
      
      PhaseState5 Invocation
         ( -0.83333 , 0.18332 , 0.0 , 0.01667 , 0.0066666 
          Layer_ = 2
          ) : ReportInteger (
      Value => CurrentOperation.PhaseState5, 
      ReportControl => R);
      
      EndStepStr Invocation
         ( -0.91667 , 0.36499 , 0.0 , 0.01667 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => "End step", 
      Left => True, 
      EnableModule => NormalOperation, 
      ReportControl => R);
      
      JumpDest Invocation
         ( -0.81667 , 0.39832 , 0.0 , 0.03333 , 0.00666659 
          Layer_ = 2
          ) : ReportString (
      Value => JumpDestOpName, 
      Width => 20, 
      Left => True, 
      EnableModule => NormalOperation, 
      ReportControl => R);
      
      JumpAllocPhaseStr Invocation
         ( -0.91667 , 0.38165 , 0.0 , 0.05 , 0.00666651 
          Layer_ = 2
          ) : ReportString (
      Value => "Jump,  allocation phase : ", 
      Width => 30, 
      Left => True, 
      EnableModule => NormalOperation, 
      ReportControl => R);
      
      JumpAllocPhase Invocation
         ( -0.81667 , 0.38165 , 0.0 , 0.03333 , 0.00666651 
          Layer_ = 2
          ) : ReportString (
      Value => CurrentOperation.Operation.RecipeProcedure.Jump.AllocationPhase, 
      Width => 20, 
      Left => True, 
      EnableModule => NormalOperation, 
      ReportControl => R);
      
      JumpPhaseStateStr Invocation
         ( -0.75 , 0.38165 , 0.0 , 0.03333 , 0.00666651 
          Layer_ = 2
          ) : ReportString (
      Value => "Phase state ", 
      Width => 20, 
      Left => True, 
      EnableModule => NormalOperation, 
      ReportControl => R);
      
      JumpResultInt Invocation
         ( -0.68334 , 0.38165 , 0.0 , 0.01667 , 0.0066666 
          Layer_ = 2
          ) : ReportInteger (
      Value => CurrentOperation.Operation.RecipeProcedure.Jump.PhaseState, 
      EnableModule => NormalOperation, 
      ReportControl => R);
      
      AlternativeEnd Invocation
         ( -0.91667 , -0.06668 , 0.0 , 0.05 , 0.00666659 
          Layer_ = 2
          ) : ReportString (
      Value => "- End of alternative branch ", 
      Width => 30, 
      Left => True, 
      ReportControl => R);
      
      ParallelEnd Invocation
         ( -0.91667 , -0.08334 , 0.0 , 0.05 , 0.00666659 
          Layer_ = 2
          ) : ReportString (
      Value => "- End of parallel branch", 
      Width => 30, 
      Left => True, 
      ReportControl => R);
      
      MasterRecText Invocation
         ( -0.91667 , 0.81665 , 0.0 , 0.03333 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => "Master recipe", 
      Width => 20, 
      Left => True, 
      ReportControl => R);
      
      MasterRecModText Invocation
         ( -0.91667 , 0.78332 , 0.0 , 0.05 , 0.00666659 
          Layer_ = 2
          ) : ReportString (
      Value => "Master recipe modified by: ", 
      Width => 30, 
      Left => True, 
      ReportControl => R);
      
      ControlRecText Invocation
         ( -0.91667 , 0.74998 , 0.0 , 0.03333 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => "Control recipe", 
      Width => 20, 
      Left => True, 
      ReportControl => R);
      
      ControlRecModText Invocation
         ( -0.91667 , 0.71665 , 0.0 , 0.05 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => "Control recipe modified by: ", 
      Width => 30, 
      Left => True, 
      ReportControl => R);
      
      ProductText Invocation
         ( -0.91667 , 0.66665 , 0.0 , 0.01667 , 0.00666659 
          Layer_ = 2
          ) : ReportString (
      Value => "Product", 
      Width => 10, 
      Left => True, 
      ReportControl => R);
      
      ScaleFactorText Invocation
         ( -0.91667 , 0.63332 , 0.0 , 0.03333 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => "Scale factor", 
      Width => 20, 
      Left => True, 
      ReportControl => R);
      
      LogText Invocation
         ( -0.91667 , 0.61665 , 0.0 , 0.01667 , 0.00666659 
          Layer_ = 2
          ) : ReportString (
      Value => "Logging", 
      Width => 10, 
      Left => True, 
      ReportControl => R);
      
      RecipeHeaderTitle1 Invocation
         ( -0.91667 , 0.84998 , 0.0 , 0.03333 , 0.00666651 
          Layer_ = 2
          ) : ReportString (
      Value => "RECIPE HEADER", 
      Width => 20, 
      Left => True, 
      ReportControl => R);
      
      ProcedureText Invocation
         ( -0.91667 , 0.56665 , 0.0 , 0.01667 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => "PROCEDURE", 
      Width => 10, 
      Left => True, 
      ReportControl => R);
      
      RecipeHeaderTitle2 Invocation
         ( -0.91667 , 0.83332 , 0.0 , 0.03333 , 0.00666659 
          Layer_ = 2
          ) : ReportString (
      Value => "--------------", 
      Width => 20, 
      Left => True, 
      ReportControl => R);
      
      ProcedureTextUndersc Invocation
         ( -0.91667 , 0.54998 , 0.0 , 0.01667 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => "----------", 
      Width => 10, 
      Left => True, 
      ReportControl => R);
      
      MasterRecAuthor Invocation
         ( -0.88333 , 0.79998 , 0.0 , 0.03333 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => RecipeDocConnection.Recipe.Header.MasterRecipeAuthor, 
      Width => 20, 
      LeadingSpaces => 10, 
      Left => True, 
      ReportControl => R);
      
      MasterRecModComment Invocation
         ( -0.88333 , 0.76665 , 0.0 , 0.03333 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => RecipeDocConnection.Recipe.Header.MasterModifyComment, 
      Width => 20, 
      LeadingSpaces => 10, 
      Left => True, 
      ReportControl => R);
      
      ControlRecAuthor Invocation
         ( -0.88333 , 0.73332 , 0.0 , 0.03333 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => RecipeDocConnection.Recipe.Header.ControlRecipeAuthor, 
      Width => 20, 
      LeadingSpaces => 10, 
      Left => True, 
      ReportControl => R);
      
      ControlRecModComment Invocation
         ( -0.88333 , 0.69998 , 0.0 , 0.03333 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => RecipeDocConnection.Recipe.Header.ControlModifyComment, 
      Width => 20, 
      LeadingSpaces => 10, 
      Left => True, 
      ReportControl => R);
      
      BatchIdText Invocation
         ( -0.91667 , 0.68332 , 0.0 , 0.01667 , 0.00666651 
          Layer_ = 2
          ) : ReportString (
      Value => "Batch id ", 
      Width => 10, 
      Left => True, 
      ReportControl => R);
      
      ProductDescription Invocation
         ( -0.85 , 0.64998 , 0.0 , 0.06667 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => RecipeDocConnection.Recipe.Header.ProductDescription, 
      Width => 40, 
      LeadingSpaces => 10, 
      Left => True, 
      ReportControl => R);
      
      MasterRecDate Invocation
         ( -0.78334 , 0.79998 , 0.0 , 0.03333 , 0.0066666 
          Layer_ = 2
          ) : ReportTime (
      Value => RecipeDocConnection.Recipe.Header.MasterRecipeDate, 
      Width => 20, 
      LeadingSpaces => 10, 
      Left => True, 
      ReportControl => R);
      
      MasterRecModDate Invocation
         ( -0.65 , 0.78332 , 0.0 , 0.03333 , 0.0066666 
          Layer_ = 2
          ) : ReportTime (
      Value => RecipeDocConnection.Recipe.Header.MasterModifyDate, 
      Width => 20, 
      LeadingSpaces => 10, 
      Left => True, 
      ReportControl => R);
      
      ControlRecDate Invocation
         ( -0.78334 , 0.73332 , 0.0 , 0.03333 , 0.0066666 
          Layer_ = 2
          ) : ReportTime (
      Value => RecipeDocConnection.Recipe.Header.ControlRecipeDate, 
      Width => 20, 
      LeadingSpaces => 10, 
      Left => True, 
      ReportControl => R);
      
      ControlRecModDate Invocation
         ( -0.65 , 0.71665 , 0.0 , 0.03333 , 0.0066666 
          Layer_ = 2
          ) : ReportTime (
      Value => RecipeDocConnection.Recipe.Header.ControlModifyDate, 
      Width => 20, 
      LeadingSpaces => 10, 
      Left => True, 
      ReportControl => R);
      
      BatchId Invocation
         ( -0.88333 , 0.68332 , 0.0 , 0.06667 , 0.0066666 
          Layer_ = 2
          ) : ReportString (
      Value => RecipeDocConnection.Recipe.Header.BatchIdentification, 
      Width => 40, 
      Left => True, 
      ReportControl => R);
      
      RecipeDocControl Invocation
         ( 0.8 , -0.8 , 0.0 , 0.1 , 0.1 
          Layer_ = 2
          ) : RecDocumentControl (
      Name => Name, 
      MasterRecipeName => RecipeDocConnection.Recipe.Header.MasterRecipeName, 
      ControlRecipeName => RecipeDocConnection.Recipe.Header.ControlRecipeName, 
      DocumenterPresent => RecipeDocConnection.DocumenterPresent, 
      ExecuteDocument => RecipeDocConnection.ExecuteDocument, 
      DocumentReady => RecipeDocConnection.DocumentReady, 
      DocumentReadyOk => RecipeDocConnection.DocumentReadyOk, 
      R => R, 
      FirstLine => FirstLine, 
      LastLine => LastLine, 
      HeaderFirstLine => HeaderFirstLine, 
      HeaderEndLine => HeaderEndLine, 
      FileName => FileName, 
      PageLength => PageLength, 
      PageLengthPS => PageLengthPS, 
      PageWidth => PageWidth, 
      Append => Append, 
      TrailingFormFeed => TrailingFormFeed, 
      LeadingFormFeed => LeadingFormFeed, 
      FontSize => FontSize, 
      AutoPrint => AutoPrint, 
      PrinterType => PrinterType, 
      PrinterNo => PrinterNo, 
      PrinterSystem => PrinterSystem, 
      NewDocument => NewDocument, 
      ControlRecipe => ControlRecipe);
      
   
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   Two_Layers_ LayerLimit_ = 0.95
   Zoomable
   Grid = 0.005
   GraphObjects :
      TextObject ( 0.96 , -0.06 ) ( 0.08 , 0.06 ) 
         "RecipeDocConnection" 
         ConnectionNode ( 1.0 , 0.0 ) 
         
         OutlineColour : Colour0 = -3 
      RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
         OutlineColour : Colour0 = -3 
      TextObject ( -0.96 , 0.76 ) ( 0.96 , 0.96 ) 
         "RecipeDocument" 
         OutlineColour : Colour0 = -3 
      RectangleObject ( -1.0 , -1.0 ) ( 0.99998 , 0.99998 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = -2 
      TextObject ( -0.92667 , 0.87665 ) ( -0.89667 , 0.88331 ) 
         "FirstLine" 
         ConnectionNode ( -0.93333 , 0.87998 ) 
         LeftAligned 
         Layer_ = 2
         Enable_ = True : InVar_ False 
         OutlineColour : Colour0 = -3 
      TextObject ( 0.22999 , -0.74667 ) ( 0.33665 , -0.72 ) 
         "LastLine" 
         ConnectionNode ( 0.28332 , -0.69334 ) 
         
         Layer_ = 2
         Enable_ = True : InVar_ False 
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.93333 , -0.06668 ) 
         ( -0.93333 , -0.0694736 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.93333 , -0.08334 ) 
         ( -0.93333 , -0.0860932 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      TextObject ( -0.92667 , 0.89331 ) ( -0.88 , 0.88665 ) 
         "HeaderEndLine" 
         ConnectionNode ( -0.93333 , 0.88998 ) 
         LeftAligned 
         Layer_ = 2
         Enable_ = True : InVar_ False 
         OutlineColour : Colour0 = -3 
      TextObject ( -0.92667 , 0.97665 ) ( -0.87667 , 0.96998 ) 
         "HeaderFirstLine" 
         ConnectionNode ( -0.93333 , 0.97331 ) 
         LeftAligned 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.93333 , 0.81665 ) 
         ( -0.93333 , 0.813846 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.93333 , 0.78332 ) 
         ( -0.93333 , 0.780516 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.93333 , 0.66665 ) 
         ( -0.93333 , 0.663846 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      TextObject ( -0.92 , 0.94665 ) ( -0.65 , 0.95665 ) 
         "Page Header" LeftAligned 
         Layer_ = 2
         Enable_ = True : InVar_ False 
         OutlineColour : Colour0 = 70 
      TextObject ( -0.65 , 0.89331 ) ( -0.65 , 0.87665 ) 
         "80" RightAligned 
         Layer_ = 2
         Enable_ = True : InVar_ False 
         OutlineColour : Colour0 = 70 
      TextObject ( -0.08334 , 0.89331 ) ( -0.08334 , 0.87665 ) 
         "80" RightAligned 
         Layer_ = 2
         Enable_ = True : InVar_ False 
         OutlineColour : Colour0 = 70 
      TextObject ( 0.56665 , 0.89665 ) ( 0.56665 , 0.87998 ) 
         "80" RightAligned 
         Layer_ = 2
         Enable_ = True : InVar_ False 
         OutlineColour : Colour0 = 70 
      TextObject ( -0.48001 , 0.89331 ) ( -0.48001 , 0.87665 ) 
         "132" RightAligned 
         Layer_ = 2
         Enable_ = True : InVar_ False 
         OutlineColour : Colour0 = 70 
      TextObject ( 0.08666 , 0.89331 ) ( 0.08666 , 0.87665 ) 
         "132" RightAligned 
         Layer_ = 2
         Enable_ = True : InVar_ False 
         OutlineColour : Colour0 = 70 
      TextObject ( 0.73665 , 0.89665 ) ( 0.73665 , 0.87998 ) 
         "132" RightAligned 
         Layer_ = 2
         Enable_ = True : InVar_ False 
         OutlineColour : Colour0 = 70 
      PolygonObject Polyline Connection ( -0.916851 , 0.923583 ) 
         ( -0.91667 , 0.923317 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.78333 , 0.923317 ) 
         ( -0.78334 , 0.923317 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.71668 , 0.923317 ) 
         ( -0.71667 , 0.923317 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.68333 , 0.923317 ) 
         ( -0.481805 , 0.923583 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.93333 , 0.97331 ) 
         ( -0.93333 , 0.930516 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.93333 , 0.91665 ) 
         ( -0.93333 , 0.913724 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 41 
      PolygonObject Polyline Connection ( -0.93333 , 0.89998 ) 
         ( -0.93333 , 0.88998 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 41 
      LineObject ( -0.48001 , 0.94998 ) ( -0.48001 , -0.66334 ) 
         Layer_ = 2
         Enable_ = True : InVar_ False 
         OutlineColour : Colour0 = 70 
      LineObject ( 0.08666 , 0.94998 ) ( 0.08666 , -0.66334 ) 
         Layer_ = 2
         Enable_ = True : InVar_ False 
         OutlineColour : Colour0 = 70 
      LineObject ( 0.73665 , 0.94998 ) ( 0.73665 , -0.66334 ) 
         Layer_ = 2
         Enable_ = True : InVar_ False 
         OutlineColour : Colour0 = 70 
      LineObject ( -0.65 , 0.94998 ) ( -0.65 , -0.66667 ) 
         Layer_ = 2
         Enable_ = True : InVar_ False 
         OutlineColour : Colour0 = 70 
      LineObject ( -0.08334 , 0.94998 ) ( -0.08334 , -0.66667 ) 
         Layer_ = 2
         Enable_ = True : InVar_ False 
         OutlineColour : Colour0 = 70 
      LineObject ( 0.56665 , 0.94998 ) ( 0.56665 , -0.66667 ) 
         Layer_ = 2
         Enable_ = True : InVar_ False 
         OutlineColour : Colour0 = 70 
      PolygonObject Polyline Connection ( -0.916846 , 0.473583 ) 
         ( -0.91667 , 0.473317 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.91685 , 0.456923 ) 
         ( -0.91667 , 0.456657 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.93333 , -0.0930516 ) 
         ( -0.95 , 0.36665 ) ( -0.93333 , 0.506913 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.916997 , 0.906852 ) 
         ( -0.91667 , 0.906647 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.78333 , 0.906647 ) 
         ( -0.485806 , 0.906852 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.916851 , 0.823583 ) 
         ( -0.91667 , 0.823317 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.916851 , 0.790253 ) 
         ( -0.91667 , 0.789987 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.916851 , 0.756913 ) 
         ( -0.91667 , 0.756647 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.916851 , 0.723583 ) 
         ( -0.91667 , 0.723317 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.916851 , 0.673583 ) 
         ( -0.91667 , 0.673317 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.916851 , 0.640253 ) 
         ( -0.91667 , 0.639987 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.91685 , 0.623583 ) 
         ( -0.91667 , 0.623317 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.85 , 0.823317 ) 
         ( -0.85001 , 0.823317 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.81667 , 0.789987 ) 
         ( -0.81667 , 0.789987 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.85 , 0.756647 ) 
         ( -0.85001 , 0.756647 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.81667 , 0.723317 ) 
         ( -0.81667 , 0.723317 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.85 , 0.639987 ) 
         ( -0.85001 , 0.639987 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.71666 , 0.823317 ) 
         ( -0.481805 , 0.823583 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.71666 , 0.756647 ) 
         ( -0.481805 , 0.756913 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.74999 , 0.673317 ) 
         ( -0.481805 , 0.673583 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.81666 , 0.639987 ) 
         ( -0.481805 , 0.640253 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.88333 , 0.806647 ) 
         ( -0.916851 , 0.806913 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.88333 , 0.773317 ) 
         ( -0.916851 , 0.773583 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.88333 , 0.739987 ) 
         ( -0.916851 , 0.740253 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.88333 , 0.706647 ) 
         ( -0.916851 , 0.706913 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.916851 , 0.690253 ) 
         ( -0.91667 , 0.689986 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.85 , 0.656647 ) 
         ( -0.916845 , 0.656913 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.85 , 0.81665 ) 
         ( -0.88333 , 0.813313 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.81667 , 0.806647 ) 
         ( -0.78334 , 0.806647 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.81667 , 0.739987 ) 
         ( -0.78334 , 0.739987 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.71668 , 0.806647 ) 
         ( -0.481805 , 0.806913 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.71668 , 0.739987 ) 
         ( -0.481805 , 0.740253 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.74999 , 0.689987 ) 
         ( -0.481805 , 0.690253 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.71666 , 0.656647 ) 
         ( -0.481641 , 0.656913 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.93333 , 0.647186 ) 
         ( -0.93333 , 0.64998 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.93333 , 0.630516 ) 
         ( -0.93333 , 0.63332 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.83333 , 0.623317 ) 
         ( -0.83333 , 0.623317 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.68334 , 0.623317 ) 
         ( -0.481778 , 0.623583 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.93333 , -0.10001 ) 
         ( -0.93333 , -0.69334 ) ( -0.40001 , -0.69334 ) 
         ( -0.40001 , 0.89998 ) ( -0.36667 , 0.89998 ) 
         ( -0.36667 , 0.870516 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.36667 , 0.85665 ) 
         ( -0.36667 , -0.69334 ) ( 0.23332 , -0.69334 ) 
         ( 0.23332 , 0.89998 ) ( 0.28332 , 0.89998 ) 
         ( 0.28332 , 0.870516 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( 0.28332 , 0.85665 ) 
         ( 0.28332 , -0.69334 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.350069 , 0.863583 ) 
         ( 0.0881974 , 0.863583 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( 0.299921 , 0.863583 ) 
         ( 0.738187 , 0.863583 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      PolygonObject Polyline Connection ( -0.916845 , 0.490253 ) 
         ( -0.481641 , 0.490253 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = 12 
      TextObject ( -0.91667 , 0.86665 ) ( -0.65 , 0.87665 ) 
         "Recipe header:" LeftAligned 
         Layer_ = 2
         OutlineColour : Colour0 = 70 
      TextObject ( -0.91667 , 0.58332 ) ( -0.65 , 0.59332 ) 
         "Procedure:" LeftAligned 
         Layer_ = 2
         OutlineColour : Colour0 = 70 
      TextObject ( -0.91667 , 0.51665 ) ( -0.65 , 0.52665 ) 
         "Table of operations" LeftAligned 
         Layer_ = 2
         OutlineColour : Colour0 = 70 
      PolygonObject Polyline Connection ( -0.91685 , 0.856913 ) 
         ( -0.91667 , 0.856646 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.91685 , 0.573583 ) 
         ( -0.91667 , 0.573317 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.91685 , 0.840253 ) 
         ( -0.91667 , 0.839987 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.91685 , 0.556913 ) 
         ( -0.91667 , 0.556647 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.85001 , 0.856646 ) 
         ( -0.481778 , 0.856913 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.85001 , 0.839987 ) 
         ( -0.481778 , 0.840253 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.93333 , 0.87998 ) 
         ( -0.93333 , 0.863846 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.93333 , 0.56665 ) 
         ( -0.93333 , 0.563846 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      TextObject ( -0.91667 , 0.10332 ) ( -0.65 , 0.11332 ) 
         "Equipment  requirement (application specific)..." LeftAligned 
         Layer_ = 2
         OutlineColour : Colour0 = 70 
      TextObject ( -0.91667 , 0.13332 ) ( -0.65 , 0.14332 ) 
         "Required unit" LeftAligned 
         Layer_ = 2
         OutlineColour : Colour0 = 70 
      TextObject ( -0.91667 , -0.04001 ) ( -0.65 , -0.03001 ) 
         "End of branches:" LeftAligned 
         Layer_ = 2
         OutlineColour : Colour0 = 70 
      PolygonObject Polyline Connection ( -0.93333 , 0.61665 ) 
         ( -0.93333 , 0.613846 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.93333 , 0.59998 ) 
         ( -0.93333 , 0.580516 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.91685 , 0.606913 ) 
         ( -0.481778 , 0.606913 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.68333 , 0.789987 ) 
         ( -0.65 , 0.789987 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.58334 , 0.789987 ) 
         ( -0.481805 , 0.790253 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.81667 , 0.773317 ) 
         ( -0.481805 , 0.773583 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.68333 , 0.723317 ) 
         ( -0.65 , 0.723317 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.58334 , 0.723317 ) 
         ( -0.481805 , 0.723583 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.81667 , 0.706647 ) 
         ( -0.481805 , 0.706913 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.93333 , 0.83332 ) 
         ( -0.93333 , 0.830516 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.93333 , 0.79998 ) 
         ( -0.93333 , 0.797186 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.93333 , 0.76665 ) 
         ( -0.93333 , 0.763846 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.93333 , 0.74998 ) 
         ( -0.93333 , 0.747186 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.93333 , 0.73332 ) 
         ( -0.93333 , 0.730516 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.93333 , 0.71665 ) 
         ( -0.93333 , 0.713846 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.93333 , 0.69998 ) 
         ( -0.93333 , 0.697186 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.93333 , 0.84998 ) 
         ( -0.93333 , 0.847186 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.93333 , 0.68332 ) 
         ( -0.93333 , 0.680516 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.916845 , 0.340253 ) 
         ( -0.9 , 0.339987 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.916845 , 0.306923 ) 
         ( -0.9 , 0.306657 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.916845 , 0.273583 ) 
         ( -0.9 , 0.273317 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.916845 , 0.240253 ) 
         ( -0.9 , 0.239987 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.916845 , 0.206923 ) 
         ( -0.9 , 0.206657 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.916845 , 0.323583 ) 
         ( -0.9 , 0.323317 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.916845 , 0.290253 ) 
         ( -0.9 , 0.289987 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.916845 , 0.256923 ) 
         ( -0.9 , 0.256657 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.916845 , 0.223583 ) 
         ( -0.9 , 0.223317 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.916845 , 0.190253 ) 
         ( -0.9 , 0.189987 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.916845 , 0.371923 ) 
         ( -0.91667 , 0.371657 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.88333 , 0.371657 ) 
         ( -0.481641 , 0.371923 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.79999 , 0.0899866 ) 
         ( -0.481805 , 0.0902532 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.916851 , 0.0902532 ) 
         ( -0.9 , 0.0899865 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.83334 , 0.0899865 ) 
         ( -0.83333 , 0.0899866 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.916851 , 0.0735932 ) 
         ( -0.9 , 0.0733266 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.8 , 0.0733266 ) 
         ( -0.481805 , 0.0735932 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.916845 , 0.540253 ) 
         ( -0.481641 , 0.540253 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.88333 , 0.573317 ) 
         ( -0.481778 , 0.573583 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.88333 , 0.556647 ) 
         ( -0.481778 , 0.556913 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.93333 , 0.49998 ) 
         ( -0.93333 , 0.497186 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.93333 , 0.48332 ) 
         ( -0.93333 , 0.480516 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.93333 , 0.46665 ) 
         ( -0.93333 , 0.463856 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.78333 , 0.623317 ) 
         ( -0.78334 , 0.623317 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.73334 , 0.623317 ) 
         ( -0.73334 , 0.623317 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.93333 , 0.16666 ) 
         ( -0.93333 , 0.163856 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.93333 , 0.14999 ) 
         ( -0.93333 , 0.130526 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.80001 , 0.173327 ) 
         ( -0.8 , 0.173327 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.75 , 0.173327 ) 
         ( -0.75 , 0.173327 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.68334 , 0.173327 ) 
         ( -0.481641 , 0.173593 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.916845 , 0.156923 ) 
         ( -0.9 , 0.156657 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.83334 , 0.156657 ) 
         ( -0.83333 , 0.156657 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.76667 , 0.156657 ) 
         ( -0.481641 , 0.156923 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.93333 , 0.11666 ) 
         ( -0.93333 , 0.0971864 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.93333 , 0.06666 ) 
         ( -0.93333 , -0.0528136 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.93333 , 0.08332 ) 
         ( -0.93333 , 0.0805264 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.88333 , 0.689986 ) 
         ( -0.88333 , 0.689987 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.88333 , 0.673317 ) 
         ( -0.88333 , 0.673317 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.88333 , 0.623317 ) 
         ( -0.88333 , 0.623317 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.79999 , 0.323317 ) 
         ( -0.481641 , 0.323583 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.79999 , 0.289987 ) 
         ( -0.481641 , 0.290253 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.79999 , 0.256657 ) 
         ( -0.481641 , 0.256923 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.79999 , 0.223317 ) 
         ( -0.481641 , 0.223583 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.79999 , 0.189987 ) 
         ( -0.481641 , 0.190253 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.83334 , 0.339987 ) 
         ( -0.83333 , 0.339987 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.83334 , 0.306657 ) 
         ( -0.83333 , 0.306657 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.83334 , 0.273317 ) 
         ( -0.83333 , 0.273317 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.83334 , 0.239987 ) 
         ( -0.83333 , 0.239987 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.83334 , 0.206657 ) 
         ( -0.83333 , 0.206657 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.76667 , 0.339987 ) 
         ( -0.481641 , 0.340253 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.76667 , 0.306657 ) 
         ( -0.481641 , 0.306923 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.76667 , 0.273317 ) 
         ( -0.481641 , 0.273583 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.76667 , 0.239987 ) 
         ( -0.481641 , 0.240253 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.76667 , 0.206657 ) 
         ( -0.481641 , 0.206923 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.83334 , 0.323317 ) 
         ( -0.83333 , 0.323317 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.83334 , 0.289987 ) 
         ( -0.83333 , 0.289987 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.83334 , 0.256657 ) 
         ( -0.83333 , 0.256657 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.83334 , 0.223317 ) 
         ( -0.83333 , 0.223317 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.83334 , 0.189987 ) 
         ( -0.83333 , 0.189987 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.916845 , 0.440253 ) 
         ( -0.91667 , 0.439987 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.85001 , 0.439987 ) 
         ( -0.481641 , 0.440253 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.916845 , 0.173593 ) 
         ( -0.9 , 0.173327 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.86667 , 0.173327 ) 
         ( -0.86666 , 0.173327 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.76667 , 0.123327 ) 
         ( -0.481805 , 0.123593 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.83334 , 0.123327 ) 
         ( -0.83333 , 0.123327 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.916851 , 0.123593 ) 
         ( -0.9 , 0.123327 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.916851 , -0.0597468 ) 
         ( -0.91667 , -0.0600134 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.81667 , -0.0600134 ) 
         ( -0.481805 , -0.0597468 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.916851 , -0.0764068 ) 
         ( -0.91667 , -0.0766734 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.81667 , -0.0766734 ) 
         ( -0.481805 , -0.0764068 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.916845 , 0.405253 ) 
         ( -0.91667 , 0.404987 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.75001 , 0.404987 ) 
         ( -0.481641 , 0.405253 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.65 , 0.388317 ) 
         ( -0.481641 , 0.388583 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.68334 , 0.388317 ) 
         ( -0.68334 , 0.388317 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.75001 , 0.388317 ) 
         ( -0.75 , 0.388317 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.916845 , 0.388583 ) 
         ( -0.91667 , 0.388317 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.93333 , 0.39832 ) 
         ( -0.93333 , 0.395516 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.81667 , 0.388317 ) 
         ( -0.81667 , 0.388317 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.81667 , 0.404987 ) 
         ( -0.81667 , 0.404987 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.93333 , 0.38165 ) 
         ( -0.93333 , 0.378856 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.93333 , 0.43332 ) 
         ( -0.93333 , 0.430516 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.81667 , 0.473317 ) 
         ( -0.481668 , 0.473583 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.81667 , 0.456657 ) 
         ( -0.481778 , 0.456923 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.93333 , 0.54998 ) 
         ( -0.93333 , 0.547186 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.93333 , 0.53332 ) 
         ( -0.93333 , 0.513846 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.9 , 0.423316 ) 
         ( -0.916845 , 0.423583 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.916845 , 0.356923 ) 
         ( -0.91667 , 0.356657 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.76666 , 0.423317 ) 
         ( -0.481641 , 0.423583 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.75001 , 0.356657 ) 
         ( -0.481641 , 0.356923 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.93333 , 0.34999 ) 
         ( -0.93333 , 0.347186 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.93333 , 0.33332 ) 
         ( -0.93333 , 0.330516 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.93333 , 0.31665 ) 
         ( -0.93333 , 0.313856 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.93333 , 0.29999 ) 
         ( -0.93333 , 0.297186 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.93333 , 0.28332 ) 
         ( -0.93333 , 0.280516 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.93333 , 0.26665 ) 
         ( -0.93333 , 0.263856 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.93333 , 0.24999 ) 
         ( -0.93333 , 0.247186 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.93333 , 0.23332 ) 
         ( -0.93333 , 0.230516 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.93333 , 0.21665 ) 
         ( -0.93333 , 0.213856 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.93333 , 0.19999 ) 
         ( -0.93333 , 0.197186 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.93333 , 0.18332 ) 
         ( -0.93333 , 0.180526 ) 
         Layer_ = 2
      PolygonObject Polyline Connection ( -0.93333 , 0.41665 ) 
         ( -0.93333 , 0.412186 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.93333 , 0.44999 ) 
         ( -0.93333 , 0.447186 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.93333 , 0.36499 ) 
         ( -0.93333 , 0.363856 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
   InteractObjects :
      ProcedureInteract ( -0.8 , -0.8 ) ( 0.8 , 0.8 ) 
         ToggleWindow
         "" : InVar_ LitString "*Info" "" : InVar_ "Name" False : InVar_ True 
         0.0 0.0 0.0 : InVar_ 0.24 0.0 False 0 0 False 0 
         Layer_ = 1
         Variable = 0.0 
   
   ModuleCode
   EQUATIONBLOCK Code COORD 0.3, -0.9 OBJSIZE 0.3, 0.1
   Layer_ = 2 :
      IF NewDocument THEN
         ClearString(InternalFileName);
         Concatenate(Filename, FileExtension, InternalFileName, Status);
         NewDocument = Off;
         InitTable = On;
      ENDIF;
   
   ENDDEF (*RecipeDocument*);
   
   TestBaControlStatus1
   (* 1. Function
      
      2. Relation to other modules
      
      3. Comments on connection list
      
      4. Operators interface
      4.1 Pop-up windows
      
      4.2 Logging of operator interaction
      
      4.3 Modules accessable through pathstring
      "ModuleName*SelectButton"
      "ModuleName*Info"
      
      5. Scangroups
      Inherit/ProgStationData.GroupProg
      
      6. Opsave and secure
      
      7. Advice for usage *)
    = MODULEDEFINITION DateCode_ 477679776
   MODULEPARAMETERS
      BatchControl: BatchControlType ;
      BatchStatus: BatchStatusType ;
   LOCALVARIABLES
      InitOpSave "Only init first time": boolean OpSave := True;
   SUBMODULES
      L1 Invocation
         ( -1.0 , -1.0 , 0.0 , 2.0 , 2.0 
          ) : MODULEDEFINITION DateCode_ 385059829 ( Frame_Module ) 
      SUBMODULES
         L2 Invocation
            ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0 
             LayerModule ) : MODULEDEFINITION DateCode_ 385059829 ( 
         Frame_Module ) 
         SUBMODULES
            Info Invocation
               ( 0.0508 , 0.1688 , 0.0 , 0.74 , 0.74 
                ) : MODULEDEFINITION DateCode_ 385059829 ( Frame_Module ) 
            SUBMODULES
               ExecuteIcon1 Invocation
                  ( 0.5 , 0.8 , 0.0 , 0.05 , 0.05 
                   ) : ExecuteIcon;
               
               ExecuteIcon2 Invocation
                  ( 0.5 , 0.7 , 0.0 , 0.05 , 0.05 
                   ) : ExecuteIcon;
               
            
            ModuleDef
            ClippingBounds = ( 0.0 , -0.2 ) ( 0.55 , 1.1 )
            Grid = 0.01
            GraphObjects :
               RectangleObject ( 0.0 , -0.2 ) ( 0.55 , 1.1 ) 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.0 , 0.1 ) ( 0.4 , 0.15 ) 
                  "CommandStatus" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.0 , 0.05 ) ( 0.4 , 0.1 ) 
                  "AsyncStatus" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( 1.11759E-08 , 1.86265E-09 ) 
                  ( 0.4 , 0.05 ) 
                  "DocumentAsyncStatus" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( 3.35276E-08 , -0.05 ) 
                  ( 0.4 , -3.72529E-09 ) 
                  "BatchJou1 create error" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( 3.35276E-08 , -0.1 ) 
                  ( 0.4 , -0.05 ) 
                  "BatchJou2 create error" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.0 , 0.15 ) ( 0.4 , 0.2 ) 
                  "AllocationInhibited" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.0 , 0.2 ) ( 0.4 , 0.25 ) 
                  "AllocationAllowed" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( -3.72529E-09 , 0.25 ) 
                  ( 0.4 , 0.3 ) 
                  "Activity" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( -7.45058E-09 , 0.3 ) 
                  ( 0.4 , 0.35 ) 
                  "Unit" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( -7.45058E-09 , 0.75 ) 
                  ( 0.4 , 0.8 ) 
                  "Activate operation" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( -1.11759E-08 , 1.0 ) 
                  ( 0.4 , 1.05 ) 
                  "Master recipe name" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.08 , 1.05 ) ( 0.48 , 1.1 ) 
                  "Control of Batch Manager" 
                  OutlineColour : Colour0 = -3 
               TextObject ( -1.49012E-08 , 0.95 ) 
                  ( 0.4 , 1.0 ) 
                  "Control recipe name" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( -1.86265E-08 , 0.9 ) 
                  ( 0.4 , 0.95 ) 
                  "BatchIdentification" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( -1.86265E-08 , 0.85 ) 
                  ( 0.4 , 0.9 ) 
                  "Scalefactor" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( -1.86265E-08 , 0.8 ) 
                  ( 0.4 , 0.85 ) 
                  "" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( -3.72529E-09 , 0.55 ) 
                  ( 0.4 , 0.6 ) 
                  "Inhibit allocation" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( -3.72529E-09 , 0.5 ) 
                  ( 0.4 , 0.55 ) 
                  "Allow allocation" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( -3.72529E-09 , 0.45 ) 
                  ( 0.4 , 0.5 ) 
                  "Terminate batch" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( -3.72529E-09 , 0.4 ) 
                  ( 0.4 , 0.45 ) 
                  "Cancel recipe" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( -3.72529E-09 , 0.35 ) 
                  ( 0.4 , 0.4 ) 
                  "Execute documentation" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.4 , 0.3 ) ( 0.55 , 0.35 ) 
                  "BatchStatus.UnitName" VarName Width_ = 5  ValueFraction = 2  
                  LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.4 , 0.25 ) ( 0.55 , 0.3 ) 
                  "BatchStatus.Activity" VarName Width_ = 5 : InVar_ 5  
                  ValueFraction = 2  LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.4 , 0.1 ) ( 0.55 , 0.15 ) 
                  "BatchStatus.CommandStatus" VarName Width_ = 5 : InVar_ 5  
                  ValueFraction = 2  LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.4 , 0.05 ) ( 0.55 , 0.1 ) 
                  "BatchStatus.AsyncStatus" VarName Width_ = 5 : InVar_ 5  
                  ValueFraction = 2  LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.4 , 0.0 ) ( 0.55 , 0.05 ) 
                  "BatchStatus.DocumentAsyncStatus" VarName Width_ = 5 : InVar_ 
                  5  ValueFraction = 2  LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.4 , 0.2 ) ( 0.55 , 0.25 ) 
                  "Yes" LeftAligned 
                  Enable_ = True : InVar_ "BatchStatus.AllocationAllowed" 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.4 , 0.15 ) ( 0.55 , 0.2 ) 
                  "Yes" LeftAligned 
                  Enable_ = True : InVar_ "BatchStatus.AllocationInhibited" 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.4 , -0.05 ) ( 0.55 , 1.49012E-08 ) 
                  "Yes" LeftAligned 
                  Enable_ = True : InVar_ "BatchStatus.ErrorCreBatchJou1" 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.4 , -0.1 ) ( 0.55 , -0.05 ) 
                  "Yes" LeftAligned 
                  Enable_ = True : InVar_ "BatchStatus.ErrorCreBatchJou2" 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.4 , 0.2 ) ( 0.55 , 0.25 ) 
                  "No" LeftAligned 
                  Enable_ = True : ( NOT BatchStatus.AllocationAllowed) 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.4 , 0.15 ) ( 0.55 , 0.2 ) 
                  "No" LeftAligned 
                  Enable_ = True : ( NOT BatchStatus.AllocationInhibited) 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.4 , -0.05 ) ( 0.55 , 1.49012E-08 ) 
                  "No" LeftAligned 
                  Enable_ = True : ( NOT BatchStatus.ErrorCreBatchJou1) 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.4 , -0.1 ) ( 0.55 , -0.05 ) 
                  "No" LeftAligned 
                  Enable_ = True : ( NOT BatchStatus.ErrorCreBatchJou2) 
                  OutlineColour : Colour0 = -3 
            InteractObjects :
               TextBox_ ( 0.4 , 1.0 ) ( 0.55 , 1.05 ) 
                  String_Value
                  Variable = "" : OutVar_ 
                  "BatchControl.CreateControlRecipe.MasterRecipeName" 
                  CenterAligned Abs_ Digits_
                  
                  FillColour : Colour0 = 9 Colour1 = -1 
               TextBox_ ( 0.4 , 0.95 ) ( 0.55 , 1.0 ) 
                  String_Value
                  Variable = "" : OutVar_ 
                  "BatchControl.CreateControlRecipe.ControlRecipeName" 
                  CenterAligned Abs_ Digits_
                  
                  FillColour : Colour0 = 9 Colour1 = -1 
               TextBox_ ( 0.4 , 0.9 ) ( 0.55 , 0.95 ) 
                  String_Value
                  Variable = "" : OutVar_ 
                  "BatchControl.CreateControlRecipe.BatchIdentification" 
                  CenterAligned Abs_ Digits_
                  
                  FillColour : Colour0 = 9 Colour1 = -1 
               TextBox_ ( 0.4 , 0.85 ) ( 0.55 , 0.9 ) 
                  Real_Value
                  Variable = 0.0 : OutVar_ 
                  "BatchControl.CreateControlRecipe.ScaleFactor" CenterAligned 
                  Abs_ Digits_
                  NoOf_ = 6 : InVar_ 3 
                  
                  FillColour : Colour0 = 9 Colour1 = -1 
               TextBox_ ( 0.4 , 0.75 ) ( 0.55 , 0.8 ) 
                  String_Value
                  Variable = "" : OutVar_ "BatchControl.ActivateOperation.Name" 
                  CenterAligned Abs_ Digits_
                  
                  FillColour : Colour0 = 9 Colour1 = -1 
               ComBut_ ( 0.5 , 0.8 ) ( 0.55 , 0.85 ) 
                  Bool_Value
                  Variable = False : OutVar_ 
                  "BatchControl.CreateControlRecipe.Execute" SetAction
                  Abs_ SetApp_
                  
               ComBut_ ( 0.5 , 0.7 ) ( 0.55 , 0.75 ) 
                  Bool_Value
                  Variable = False : OutVar_ 
                  "BatchControl.ActivateOperation.Execute" SetAction
                  Abs_ SetApp_
                  
               ComBut_ ( 0.4 , 0.55 ) ( 0.55 , 0.6 ) 
                  Bool_Value
                  Variable = False : OutVar_ "BatchControl.InhibitAllocation" 
                  SetAction
                  Abs_ SetApp_
                  
               ComBut_ ( 0.4 , 0.5 ) ( 0.55 , 0.55 ) 
                  Bool_Value
                  Variable = False : OutVar_ "BatchControl.AllowAllocation" 
                  SetAction
                  Abs_ SetApp_
                  
               ComBut_ ( 0.4 , 0.45 ) ( 0.55 , 0.5 ) 
                  Bool_Value
                  Variable = False : OutVar_ "BatchControl.TerminateBatch" 
                  ToggleAction
                  Abs_ SetApp_
                  
               ComBut_ ( 0.4 , 0.4 ) ( 0.55 , 0.45 ) 
                  Bool_Value
                  Variable = False : OutVar_ "BatchControl.CancelRecipe" 
                  ToggleAction
                  Abs_ SetApp_
                  
               ComBut_ ( 0.4 , 0.35 ) ( 0.55 , 0.4 ) 
                  Bool_Value
                  Variable = False : OutVar_ 
                  "BatchControl.ExecuteDocumentation" ToggleAction
                  Abs_ SetApp_
                  
            
            ENDDEF (*Info*);
            
         
         ModuleDef
         ClippingBounds = ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
         GraphObjects :
            RectangleObject ( 0.0 , 0.0 ) ( 1.0 , 1.0 ) 
               OutlineColour : Colour0 = -3 
               FillColour : Colour0 = -2 
         
         ENDDEF (*L2*);
         
         Icon Invocation
            ( -5.96046E-08 , 2.98023E-08 , 0.0 , 1.0 , 1.0 
             ) : ParIcon;
         
      
      ModuleDef
      ClippingBounds = ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
      ZoomLimits = 0.94193 0.01
      Zoomable
      InteractObjects :
         ProcedureInteract ( 0.1 , 0.1 ) ( 0.9 , 0.9 ) 
            ToggleWindow
            "" : InVar_ LitString "++Info" "" False : InVar_ True 0.0 : InVar_ 
            0.1 0.0 : InVar_ -0.1 0.0 : InVar_ 0.24 0.0 False 0 0 False 0 
            Variable = 0.0 
      
      ENDDEF (*L1*);
      
   
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   
   ENDDEF (*TestBaControlStatus1*);
   
   TestOpControlStatus1
   (* 1. Function
      
      2. Relation to other modules
      
      3. Comments on connection list
      
      4. Operators interface
      4.1 Pop-up windows
      
      4.2 Logging of operator interaction
      
      4.3 Modules accessable through pathstring
      "ModuleName*SelectButton"
      "ModuleName*Info"
      
      5. Scangroups
      Inherit/ProgStationData.GroupProg
      
      6. Opsave and secure
      
      7. Advice for usage *)
    = MODULEDEFINITION DateCode_ 478413888
   MODULEPARAMETERS
      UnitName: string ;
      OperationControl: OperationControlType ;
      OperationStatus: OperationStatusType ;
   LOCALVARIABLES
      InitOpSave "Only init first time": boolean OpSave := True;
   SUBMODULES
      L1 Invocation
         ( -1.0 , -1.0 , 0.0 , 2.0 , 2.0 
          ) : MODULEDEFINITION DateCode_ 385285516 ( Frame_Module ) 
      SUBMODULES
         L2 Invocation
            ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0 
             LayerModule ) : MODULEDEFINITION DateCode_ 385285516 ( 
         Frame_Module ) 
         SUBMODULES
            Info Invocation
               ( 0.0508 , 0.0488 , 0.0 , 0.82 , 0.82 
                ) : MODULEDEFINITION DateCode_ 385285516 ( Frame_Module ) 
            SUBMODULES
               ExecuteIcon1 Invocation
                  ( 0.5 , 0.8 , 0.0 , 0.05 , 0.05 
                   ) : ExecuteIcon;
               
            
            ModuleDef
            ClippingBounds = ( 0.0 , 0.0 ) ( 0.55 , 1.1 )
            Grid = 0.01
            GraphObjects :
               RectangleObject ( 0.0 , 0.0 ) ( 0.55 , 1.1 ) 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.0 , 0.1 ) ( 0.4 , 0.15 ) 
                  "CommandStatus" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.0 , 0.05 ) ( 0.4 , 0.1 ) 
                  "AsyncStatus" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( 1.11759E-08 , 1.86265E-09 ) 
                  ( 0.4 , 0.05 ) 
                  "DocumentAsyncStatus" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.0 , 0.15 ) ( 0.4 , 0.2 ) 
                  "Unit inhibited" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.0 , 0.2 ) ( 0.4 , 0.25 ) 
                  "OpRecipe manual mode" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( -3.72529E-09 , 0.25 ) 
                  ( 0.4 , 0.3 ) 
                  "OpRecipe status" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( -7.45058E-09 , 0.3 ) 
                  ( 0.4 , 0.35 ) 
                  "Unit" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( -7.45058E-09 , 0.65 ) 
                  ( 0.4 , 0.7 ) 
                  "Send control recipe" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( -1.11759E-08 , 1.0 ) 
                  ( 0.4 , 1.05 ) 
                  "Master recipe name" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.08 , 1.05 ) ( 0.48 , 1.1 ) 
                  "Control of Unit supervisor server" 
                  OutlineColour : Colour0 = -3 
               TextObject ( -1.49012E-08 , 0.95 ) 
                  ( 0.4 , 1.0 ) 
                  "Control recipe name" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( -1.86265E-08 , 0.9 ) 
                  ( 0.4 , 0.95 ) 
                  "BatchIdentification" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( -1.86265E-08 , 0.85 ) 
                  ( 0.4 , 0.9 ) 
                  "Scalefactor" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( 3.72529E-09 , 0.6 ) ( 0.4 , 0.65 ) 
                  "Cancel control recipe" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( -3.72529E-09 , 0.55 ) 
                  ( 0.4 , 0.6 ) 
                  "Start control recipe" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( -3.72529E-09 , 0.5 ) 
                  ( 0.4 , 0.55 ) 
                  "Stop control recipe" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( -3.72529E-09 , 0.45 ) 
                  ( 0.4 , 0.5 ) 
                  "Automatic" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( -3.72529E-09 , 0.4 ) 
                  ( 0.4 , 0.45 ) 
                  "Manual" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( -3.72529E-09 , 0.35 ) 
                  ( 0.4 , 0.4 ) 
                  "Execute documentation" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.4 , 0.15 ) ( 0.55 , 0.2 ) 
                  "Yes" LeftAligned 
                  Enable_ = True : InVar_ "OperationStatus.UnitInhibited" 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.4 , 0.2 ) ( 0.55 , 0.25 ) 
                  "Yes" LeftAligned 
                  Enable_ = True : InVar_ "OperationStatus.OpRecipeManualMode" 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.4 , 0.3 ) ( 0.55 , 0.35 ) 
                  "UnitName" VarName Width_ = 5  ValueFraction = 2  LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.4 , 0.25 ) ( 0.55 , 0.3 ) 
                  "OperationStatus.OpRecipeStatus" VarName Width_ = 5  
                  ValueFraction = 2  LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.4 , 0.0999998 ) ( 0.55 , 0.15 ) 
                  "OperationStatus.CommandStatus" VarName Width_ = 5 : InVar_ 5  
                  ValueFraction = 2  LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.4 , 0.05 ) ( 0.55 , 0.1 ) 
                  "OperationStatus.AsyncStatus" VarName Width_ = 5 : InVar_ 5  
                  ValueFraction = 2  LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.4 , 0.0 ) ( 0.55 , 0.05 ) 
                  "OperationStatus.DocumentAsyncStatus" VarName Width_ = 5 : 
                  InVar_ 5  ValueFraction = 2  LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.4 , 0.15 ) ( 0.55 , 0.2 ) 
                  "No" LeftAligned 
                  Enable_ = True : ( NOT OperationStatus.UnitInhibited) 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.4 , 0.2 ) ( 0.55 , 0.25 ) 
                  "No" LeftAligned 
                  Enable_ = True : ( NOT OperationStatus.OpRecipeManualMode) 
                  OutlineColour : Colour0 = -3 
            InteractObjects :
               TextBox_ ( 0.4 , 1.0 ) ( 0.55 , 1.05 ) 
                  String_Value
                  Variable = "" : OutVar_ 
                  "OperationControl.CreateControlRecipe.MasterRecipeName" 
                  CenterAligned Abs_ Digits_
                  
                  FillColour : Colour0 = 9 Colour1 = -1 
               TextBox_ ( 0.4 , 0.95 ) ( 0.55 , 1.0 ) 
                  String_Value
                  Variable = "" : OutVar_ 
                  "OperationControl.CreateControlRecipe.ControlRecipeName" 
                  CenterAligned Abs_ Digits_
                  
                  FillColour : Colour0 = 9 Colour1 = -1 
               TextBox_ ( 0.4 , 0.9 ) ( 0.55 , 0.95 ) 
                  String_Value
                  Variable = "" : OutVar_ 
                  "OperationControl.CreateControlRecipe.BatchIdentification" 
                  CenterAligned Abs_ Digits_
                  
                  FillColour : Colour0 = 9 Colour1 = -1 
               TextBox_ ( 0.4 , 0.85 ) ( 0.55 , 0.9 ) 
                  Real_Value
                  Variable = 0.0 : OutVar_ 
                  "OperationControl.CreateControlRecipe.ScaleFactor" 
                  CenterAligned Abs_ Digits_
                  NoOf_ = 6 : InVar_ 3 
                  
                  FillColour : Colour0 = 9 Colour1 = -1 
               ComBut_ ( 0.5 , 0.8 ) ( 0.55 , 0.85 ) 
                  Bool_Value
                  Variable = False : OutVar_ 
                  "OperationControl.CreateControlRecipe.Execute" SetAction
                  Abs_ SetApp_
                  
               ComBut_ ( 0.4 , 0.65 ) ( 0.55 , 0.7 ) 
                  Bool_Value
                  Variable = False : OutVar_ 
                  "OperationControl.SendControlRecipe" SetAction
                  Abs_ SetApp_
                  
               ComBut_ ( 0.4 , 0.6 ) ( 0.55 , 0.65 ) 
                  Bool_Value
                  Variable = False : OutVar_ 
                  "OperationControl.CancelControlRecipe" SetAction
                  Abs_ SetApp_
                  
               ComBut_ ( 0.4 , 0.55 ) ( 0.55 , 0.6 ) 
                  Bool_Value
                  Variable = False : OutVar_ 
                  "OperationControl.StartControlRecipe" SetAction
                  Abs_ SetApp_
                  
               ComBut_ ( 0.4 , 0.5 ) ( 0.55 , 0.55 ) 
                  Bool_Value
                  Variable = False : OutVar_ 
                  "OperationControl.StopControlRecipe" SetAction
                  Abs_ SetApp_
                  
               ComBut_ ( 0.4 , 0.45 ) ( 0.55 , 0.5 ) 
                  Bool_Value
                  Variable = False : OutVar_ "OperationControl.Automatic" 
                  ToggleAction
                  Abs_ SetApp_
                  
               ComBut_ ( 0.4 , 0.4 ) ( 0.55 , 0.45 ) 
                  Bool_Value
                  Variable = False : OutVar_ "OperationControl.Manual" 
                  ToggleAction
                  Abs_ SetApp_
                  
               ComBut_ ( 0.4 , 0.35 ) ( 0.55 , 0.4 ) 
                  Bool_Value
                  Variable = False : OutVar_ 
                  "OperationControl.ExecuteDocumentation" ToggleAction
                  Abs_ SetApp_
                  
            
            ENDDEF (*Info*);
            
         
         ModuleDef
         ClippingBounds = ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
         GraphObjects :
            RectangleObject ( 0.0 , 0.0 ) ( 1.0 , 1.0 ) 
               OutlineColour : Colour0 = -3 
               FillColour : Colour0 = -2 
         
         ENDDEF (*L2*);
         
         Icon Invocation
            ( -5.96046E-08 , 2.98023E-08 , 0.0 , 1.0 , 1.0 
             ) : ParIcon;
         
      
      ModuleDef
      ClippingBounds = ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
      ZoomLimits = 0.94193 0.01
      Zoomable
      GraphObjects :
         TextObject ( 0.04 , 0.7 ) ( 0.96 , 1.0 ) 
            "OP" 
      InteractObjects :
         ProcedureInteract ( 0.1 , 0.1 ) ( 0.9 , 0.9 ) 
            ToggleWindow
            "" : InVar_ LitString "++Info" "" False : InVar_ True 0.0 : InVar_ 
            0.1 0.0 : InVar_ -0.1 0.0 : InVar_ 0.24 0.0 False 0 0 False 0 
            Variable = 0.0 
      
      ENDDEF (*L1*);
      
   
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   
   ENDDEF (*TestOpControlStatus1*);
   
   BatchDemoVersion
   (* The usages of this master module will be found in Sattline reference manual. 
   *)
    = MODULEDEFINITION DateCode_ 523735360
   SUBMODULES
      L1 Invocation
         ( -2.38419E-07 , -5.21541E-08 , 0.0 , 1.0 , 1.0 
          ) : MODULEDEFINITION DateCode_ 523160960 ( Frame_Module ) 
      SUBMODULES
         L2 Invocation
            ( -1.0 , -0.7 , 0.0 , 1.0 , 1.0 
             LayerModule ) : MODULEDEFINITION DateCode_ 523161040 ( 
         Frame_Module ) 
         
         
         ModuleDef
         ClippingBounds = ( 0.0 , 0.0 ) ( 2.0 , 1.4 )
         GraphObjects :
            TextObject ( 0.0 , 0.9 ) ( 2.0 , 1.4 ) 
               "BatchDemo" LeftAligned 
               OutlineColour : Colour0 = -3 
            TextObject ( 0.0 , 0.7 ) ( 2.0 , 0.9 ) 
               "SattLine Demo Picture" LeftAligned 
               OutlineColour : Colour0 = -3 
         
         ENDDEF (*L2*);
         
      
      ModuleDef
      ClippingBounds = ( -1.0 , -0.7 ) ( 1.0 , 0.7 )
      ZoomLimits = 0.84653 0.01
      Zoomable
      GraphObjects :
         RectangleObject ( -1.0 , -0.7 ) ( 1.0 , 0.7 ) 
            OutlineColour : Colour0 = -3 
         TextObject ( -1.0 , 0.3 ) ( 1.0 , 0.7 ) 
            "BatchDemo" LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( -1.0 , -0.2 ) ( 1.0 , 0.2 ) 
            "§Version" LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( -1.0 , -0.7 ) ( 1.0 , -0.3 ) 
            "§Date" LeftAligned 
            OutlineColour : Colour0 = -3 
      
      ENDDEF (*L1*);
      
   
   ModuleDef
   ClippingBounds = ( -1.0 , -0.7 ) ( 1.0 , 0.7 )
   
   ENDDEF (*BatchDemoVersion*);
   
   OpStationBatch = MODULEDEFINITION DateCode_ 546497202 ( GroupConn = 
   ScanGroup ) 
   MODULEPARAMETERS
      ScanGroup: GroupData  := Default;
      ProcessManagerNumber: integer ;
      JournalSystem1, JournalSystem2, RecipeSystem, RecipeDirectory, 
      PrinterSystem "IN": String ;
      PrinterNo "IN": Integer ;
      RecipeRevServer, RevisionDelimiter, OpName: string ;
      EnableInteraction, EnableEdit, EnableEditRestricted, EnableControl, 
      EnableStart: boolean ;
   LOCALVARIABLES
      RecipeCopy: OperationRecipeType ;
      EditorAndDocConn: OpRecipeDisplayType ;
      RecipeEditConn: RecipeEditConnType ;
      OpRecipeEditConn: OpRecipeEditConnType ;
      Formula1Display: Formula1DisplayType ;
      Formula2Display: Formula2DisplayType ;
      Formula3Display: Formula3DisplayType ;
      ExecuteReport, ReportReady: boolean ;
      BatchID: string ;
      ReportIsActive: boolean ;
      StartTime: Time ;
      StopTime: time  := Time_Value "2999-12-31-01:00:00.000";
      TestProcManager: TestProcManType ;
      UnitList: UnitSystemType ;
      Status: integer ;
   SUBMODULES
      ProcessManager Invocation
         ( 0.3 , 0.48 , 0.0 , 0.24 , 0.24 
          ) : MODULEDEFINITION DateCode_ 372951652
      MODULEPARAMETERS
         Name "IN Name of the module": string  := "Process Manager";
         JournalSystem1 
         "IN Name of system where batchjournals reside. Note ! There must be a system name"
         : string ;
         JournalSystem2 "IN The batch journals are also created on this system"
         : string  := "";
         RecipeSystem 
         "IN Name of the system where the recipes and operation recipes reside"
         : string ;
         RecipeDirectory 
         "IN Name of the directory where the recipes and operation recipes reside"
         , RecipeRevServer 
         "IN Name of the file revision server. The revison handling is activated if this name is defined"
         : string  := "";
         RevisionDelimiter 
         "IN The delimiter between filename and revision number. See description of module RestoreRecipe"
         : string  := "_v";
         ProcessManagerNumber 
         "IN Uniqe identity of this process manager (1-99)": integer ;
         EnableEdit "IN Enable edit of recipes", EnableEditRestricted 
         "IN Enable restricted edit of recipes": boolean  := True;
         EditSeverity "IN Severity 0-127": integer  := 0;
         EditClass "IN Class 1-98": integer  := 1;
         EnableControl "IN Enable control of control recipes": boolean  := True
         ;
         ControlSeverity "IN Severity 0-127": integer  := 0;
         ControlClass "IN Class 1-98": integer  := 1;
         EnableModule "IN Tells if process manager is enabled": boolean  := 
         True;
         Error "OUT Tells if any error in module": boolean  := Default;
         TestProcManager: TestProcManType  := Default;
         PrinterSystem "IN Printer system": String ;
         PrinterNo "IN Printer No.": Integer ;
      LOCALVARIABLES
         cSendingUnitName: tagstring Const := "batchmanagerxyz";
         cInfoUnitSuperServer: identstring Const := "InfoUSS";
         AccessableUnits: AccessableUnitsType ;
         Act1, Act2, Act3, Act4: integer ;
         AllConn1, AllConn2, AllConn3, AllConn4: AllocatorConnectType ;
         AllocationError, AutoDocumentation: boolean ;
         BatchUnitConnection 
         "Connection between BatchManager and UnitSupervisorServer modules": 
         BatchUnitConnectType ;
         ErrorBM1, ErrorBM2, ErrorBM3, ErrorBM4, ErrorUSS1, ErrorUSS2, 
         ErrorUSS3, ErrorUSS4, ErrorUSS5, ErrorUSS6, ManualMode1, ManualMode2, 
         ManualMode3, ManualMode4: boolean ;
         OpRecipe1, OpRecipe2, OpRecipe3, OpRecipe4, OpRecipe5, OpRecipe6: 
         OperationRecipeType ;
         OpRecipeDocConn: OpRecipeDocConnType ;
         OpRecipeCopy: OperationRecipeType ;
         OpRecipeControl: OpRecipeControlType ;
         OprecipeStatus: OpRecipeStatusType ;
         OpRecipeRestoreConn: OpRecipeRestConnType ;
         OpRecipeEditConn: OpRecipeEditConnType ;
         RecipeRestoreConn: RecipeRestConnType ;
         Recipe, Recipe1, Recipe2, Recipe3, Recipe4: RecipeType ;
         RecipeDocConnection: RecipeDocConnType ;
         RecipeEditConnection 
         "Connection between editor/documenter and extensin modules": 
         RecipeEditConnType ;
         UnitList, UnitSystemList: UnitSystemType ;
      SUBMODULES
         Icon Invocation
            ( -1.0 , -1.0 , 0.0 , 2.0 , 2.0 
             Layer_ = 1
             ) : ProcessManagerIcon;
         
         InfoFrame Invocation
            ( -1.0 , -0.96 , 0.0 , 1.12 , 1.12 
             Layer_ = 2
             ) : MODULEDEFINITION DateCode_ 525194880 ( Frame_Module ) 
         SUBMODULES
            InfoUSS Invocation
               ( 0.25 , 0.82 , 0.0 , 0.74 , 0.74 
                ) : MODULEDEFINITION DateCode_ 525194964 ( Frame_Module ) 
            SUBMODULES
               UnitSuperServer1 Invocation
                  ( 3.72529E-09 , -0.10009 , 0.0 , 0.05 , 0.05 
                   ) : UnitSupervisorServer (
               UnitName => UnitList.Unit1, 
               UnitSystemList => UnitSystemList, 
               JournalSystem1 => JournalSystem1, 
               JournalSystem2 => JournalSystem2, 
               ProcessManagerNumber => ProcessManagerNumber, 
               OpRecipeControl => TestProcManager.OperationControl1, 
               OpRecipeStatus => TestProcManager.OperationStatus1, 
               OperationRecipe => OpRecipe1, 
               OpRecipeRestoreConn => OpRecipeRestoreConn, 
               OpRecipeDocConn => OpRecipeDocConn, 
               AutoDocumentation => AutoDocumentation, 
               EnableControl => EnableControl, 
               ControlSeverity => ControlSeverity, 
               ControlClass => ControlClass, 
               Error => ErrorUSS1, 
               EnableModule => EnableModule);
               
               UnitSuperServer2 Invocation
                  ( 0.0 , -0.15009 , 0.0 , 0.05 , 0.05 
                   ) : UnitSupervisorServer (
               UnitName => UnitList.Unit2, 
               UnitSystemList => UnitSystemList, 
               JournalSystem1 => JournalSystem1, 
               JournalSystem2 => JournalSystem2, 
               ProcessManagerNumber => ProcessManagerNumber, 
               OpRecipeControl => TestProcManager.OperationControl2, 
               OpRecipeStatus => TestProcManager.OperationStatus2, 
               OperationRecipe => OpRecipe2, 
               OpRecipeRestoreConn => OpRecipeRestoreConn, 
               OpRecipeDocConn => OpRecipeDocConn, 
               AutoDocumentation => AutoDocumentation, 
               EnableControl => EnableControl, 
               ControlSeverity => ControlSeverity, 
               ControlClass => ControlClass, 
               Error => ErrorUSS2, 
               EnableModule => EnableModule);
               
               UnitSuperServer3 Invocation
                  ( -3.72529E-09 , -0.20009 , 0.0 , 0.05 , 0.05 
                   ) : UnitSupervisorServer (
               UnitName => UnitList.Unit3, 
               UnitSystemList => UnitSystemList, 
               JournalSystem1 => JournalSystem1, 
               JournalSystem2 => JournalSystem2, 
               ProcessManagerNumber => ProcessManagerNumber, 
               OpRecipeControl => TestProcManager.OperationControl3, 
               OpRecipeStatus => TestProcManager.OperationStatus3, 
               OperationRecipe => OpRecipe3, 
               OpRecipeRestoreConn => OpRecipeRestoreConn, 
               OpRecipeDocConn => OpRecipeDocConn, 
               AutoDocumentation => AutoDocumentation, 
               EnableControl => EnableControl, 
               ControlSeverity => ControlSeverity, 
               ControlClass => ControlClass, 
               Error => ErrorUSS3, 
               EnableModule => EnableModule);
               
               UnitSuperServer4 Invocation
                  ( 0.0 , -0.25009 , 0.0 , 0.05 , 0.05 
                   ) : UnitSupervisorServer (
               UnitName => UnitList.Unit4, 
               UnitSystemList => UnitSystemList, 
               JournalSystem1 => JournalSystem1, 
               JournalSystem2 => JournalSystem2, 
               ProcessManagerNumber => ProcessManagerNumber, 
               OpRecipeControl => TestProcManager.OperationControl4, 
               OpRecipeStatus => TestProcManager.OperationStatus4, 
               OperationRecipe => OpRecipe4, 
               OpRecipeRestoreConn => OpRecipeRestoreConn, 
               OpRecipeDocConn => OpRecipeDocConn, 
               AutoDocumentation => AutoDocumentation, 
               EnableControl => EnableControl, 
               ControlSeverity => ControlSeverity, 
               ControlClass => ControlClass, 
               Error => ErrorUSS4, 
               EnableModule => EnableModule);
               
               UnitSuperServer5 Invocation
                  ( -3.72529E-09 , -0.30009 , 0.0 , 0.05 , 0.05 
                   ) : UnitSupervisorServer (
               UnitName => UnitList.Unit5, 
               UnitSystemList => UnitSystemList, 
               JournalSystem1 => JournalSystem1, 
               JournalSystem2 => JournalSystem2, 
               ProcessManagerNumber => ProcessManagerNumber, 
               OpRecipeControl => TestProcManager.OperationControl5, 
               OpRecipeStatus => TestProcManager.OperationStatus5, 
               OperationRecipe => OpRecipe5, 
               OpRecipeRestoreConn => OpRecipeRestoreConn, 
               OpRecipeDocConn => OpRecipeDocConn, 
               AutoDocumentation => AutoDocumentation, 
               EnableControl => EnableControl, 
               ControlSeverity => ControlSeverity, 
               ControlClass => ControlClass, 
               Error => ErrorUSS5, 
               EnableModule => EnableModule);
               
               UnitSuperServer6 Invocation
                  ( -3.72529E-09 , -0.35009 , 0.0 , 0.05 , 0.05 
                   ) : UnitSupervisorServer (
               UnitName => UnitList.Unit6, 
               UnitSystemList => UnitSystemList, 
               JournalSystem1 => JournalSystem1, 
               JournalSystem2 => JournalSystem2, 
               ProcessManagerNumber => ProcessManagerNumber, 
               OpRecipeControl => TestProcManager.OperationControl6, 
               OpRecipeStatus => TestProcManager.OperationStatus6, 
               OperationRecipe => OpRecipe6, 
               OpRecipeRestoreConn => OpRecipeRestoreConn, 
               OpRecipeDocConn => OpRecipeDocConn, 
               AutoDocumentation => AutoDocumentation, 
               EnableControl => EnableControl, 
               ControlSeverity => ControlSeverity, 
               ControlClass => ControlClass, 
               Error => ErrorUSS6, 
               EnableModule => EnableModule);
               
            
            ModuleDef
            ClippingBounds = ( 0.0 , -0.35 ) ( 2.0 , 0.0 )
            Zoomable
            Grid = 0.01
            GraphObjects :
               RectangleObject ( 0.0 , -0.35 ) ( 2.0 , 0.0 ) 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.38 , -0.05 ) ( 0.61 , 0.0 ) 
                  "Batch Id:" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.92 , -0.05 ) ( 1.22 , 0.0 ) 
                  "Master op recipe:" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( 1.22 , -0.05 ) ( 1.47 , 0.0 ) 
                  "Operation:" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( 1.47 , -0.05 ) ( 2.0 , 0.0 ) 
                  "Status:" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.1 , -0.05 ) ( 0.38 , 0.0 ) 
                  "Unit:" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.61 , -0.05 ) ( 0.92 , 0.0 ) 
                  "Control op recipe:" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.0 , -0.05 ) ( 0.1 , 0.0 ) 
                  "ProcessManagerNumber" VarName Width_ = 5 : InVar_ 2  
                  ValueFraction = 2  LeftAligned 
            
            ENDDEF (*InfoUSS*);
            
            InfoBM Invocation
               ( 0.23 , 1.64 , 0.0 , 0.73 , 0.73 
                ) : MODULEDEFINITION DateCode_ 525194964 ( Frame_Module ) 
            SUBMODULES
               BatchManager1 Invocation
                  ( 3.72529E-09 , -0.10009 , 0.0 , 0.05 , 0.05009 
                   ) : BatchManager (
               JournalSystem1 => JournalSystem1, 
               JournalSystem2 => JournalSystem2, 
               BatchControl => TestProcManager.BatchControl1, 
               BatchStatus => TestProcManager.BatchStatus1, 
               RecipeRestoreConn => RecipeRestoreConn, 
               Recipe => Recipe1, 
               AllocatorConnection => AllConn1, 
               RecipeDocConnection => RecipeDocConnection, 
               EnableControl => EnableControl, 
               ControlSeverity => ControlSeverity, 
               ControlClass => ControlClass, 
               Error => ErrorBM1, 
               EnableModule => EnableModule, 
               AllocationError => AllocationError);
               
               BatchManager2 Invocation
                  ( 0.0 , -0.15009 , 0.0 , 0.05 , 0.05 
                   ) : BatchManager (
               JournalSystem1 => JournalSystem1, 
               JournalSystem2 => JournalSystem2, 
               BatchControl => TestProcManager.BatchControl2, 
               BatchStatus => TestProcManager.BatchStatus2, 
               RecipeRestoreConn => RecipeRestoreConn, 
               Recipe => Recipe2, 
               AllocatorConnection => AllConn2, 
               RecipeDocConnection => RecipeDocConnection, 
               EnableControl => EnableControl, 
               ControlSeverity => ControlSeverity, 
               ControlClass => ControlClass, 
               Error => ErrorBM2, 
               EnableModule => EnableModule, 
               AllocationError => AllocationError);
               
               BatchManager3 Invocation
                  ( 0.0 , -0.20009 , 0.0 , 0.05 , 0.05 
                   ) : BatchManager (
               JournalSystem1 => JournalSystem1, 
               JournalSystem2 => JournalSystem2, 
               BatchControl => TestProcManager.BatchControl3, 
               BatchStatus => TestProcManager.BatchStatus3, 
               RecipeRestoreConn => RecipeRestoreConn, 
               Recipe => Recipe3, 
               AllocatorConnection => AllConn3, 
               RecipeDocConnection => RecipeDocConnection, 
               EnableControl => EnableControl, 
               ControlSeverity => ControlSeverity, 
               ControlClass => ControlClass, 
               Error => ErrorBM3, 
               EnableModule => EnableModule, 
               AllocationError => AllocationError);
               
               BatchManager4 Invocation
                  ( -3.72529E-09 , -0.25009 , 0.0 , 0.05 , 0.05 
                   ) : BatchManager (
               JournalSystem1 => JournalSystem1, 
               JournalSystem2 => JournalSystem2, 
               BatchControl => TestProcManager.BatchControl4, 
               BatchStatus => TestProcManager.BatchStatus4, 
               RecipeRestoreConn => RecipeRestoreConn, 
               Recipe => Recipe4, 
               AllocatorConnection => AllConn4, 
               RecipeDocConnection => RecipeDocConnection, 
               EnableControl => EnableControl, 
               ControlSeverity => ControlSeverity, 
               ControlClass => ControlClass, 
               Error => ErrorBM4, 
               EnableModule => EnableModule, 
               AllocationError => AllocationError);
               
               WindowIcon1 Invocation
                  ( 1.95 , -0.05 , 0.0 , 0.05 , 0.05 
                   ) : WindowIcon;
               
               UnitIcon1 Invocation
                  ( 1.955 , -0.045 , 0.0 , 0.04 , 0.04 
                   ) : ProcessUnitIcon;
               
            
            ModuleDef
            ClippingBounds = ( 0.0 , -0.25 ) ( 2.0 , 0.0 )
            Zoomable
            Grid = 0.005
            GraphObjects :
               RectangleObject ( -7.45058E-09 , -0.25 ) 
                  ( 2.0 , 0.0 ) 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.38 , -0.05 ) ( 0.65 , 0.0 ) 
                  "Master recipe:" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.65 , -0.05 ) ( 0.94 , 0.0 ) 
                  "Control recipe:" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.1 , -0.05 ) ( 0.38 , 0.0 ) 
                  "Batch Id:" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( 1.21 , -0.05 ) ( 1.65 , 0.0 ) 
                  "Status:" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.0 , -0.05 ) ( 0.1 , 0.0 ) 
                  "ProcessManagerNumber" VarName Width_ = 5 : InVar_ 2  
                  ValueFraction = 2  LeftAligned 
               CompositeObject 
               CompositeObject 
               CompositeObject 
               CompositeObject 
               TextObject ( 0.94 , -0.05 ) ( 1.21 , 0.0 ) 
                  "Scale factor:" LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( 1.65 , -0.05 ) ( 1.9 , 0.0 ) 
                  "Allocation:" LeftAligned 
                  OutlineColour : Colour0 = -3 
            InteractObjects :
               ComButProc_ ( 1.95 , -0.05 ) ( 2.0 , 0.0 ) 
                  ToggleWindow
                  "" : InVar_ "cInfoUnitSuperServer" "" : InVar_ "Name" False 
                  0.0 : InVar_ 0.02 0.0 : InVar_ 0.05 0.0 : InVar_ 0.96 0.0 : 
                  InVar_ 0.0 False 0 0 False 0 
                  Variable = 0.0 
            
            ENDDEF (*InfoBM*);
            
            RecipeEditor1 Invocation
               ( 0.08 , 1.44 , 0.0 , 0.06 , 0.06 
                ) : RecipeEditor (
            EnableEdit => EnableEdit, 
            EnableEditRestricted => EnableEditRestricted, 
            EditSeverity => EditSeverity, 
            EditClass => EditClass, 
            EnableControl => EnableControl, 
            ControlSeverity => ControlSeverity, 
            ControlClass => ControlClass, 
            OpRecipeRestoreConn => OpRecipeRestoreConn);
            
            UnitAllocator1 Invocation
               ( 1.75 , 1.58 , 0.0 , 0.02 , 0.02 
                ) : UnitAllocator (
            Recipe => Recipe1, 
            IdentificationNo => 1, 
            UnitSystemList => UnitSystemList, 
            AccessableUnits => AccessableUnits, 
            AllocatorConnection => AllConn1, 
            ManualMode => ManualMode1, 
            UnitName => cSendingUnitName, 
            Activity => Act1);
            
            UnitAllocator2 Invocation
               ( 1.75 , 1.54 , 0.0 , 0.02 , 0.02 
                ) : UnitAllocator (
            Recipe => Recipe2, 
            IdentificationNo => 2, 
            UnitSystemList => UnitSystemList, 
            AccessableUnits => AccessableUnits, 
            AllocatorConnection => AllConn2, 
            ManualMode => ManualMode2, 
            UnitName => cSendingUnitName, 
            Activity => Act2);
            
            UnitAllocator3 Invocation
               ( 1.75 , 1.5 , 0.0 , 0.02 , 0.02 
                ) : UnitAllocator (
            Recipe => Recipe3, 
            IdentificationNo => 3, 
            UnitSystemList => UnitSystemList, 
            AccessableUnits => AccessableUnits, 
            AllocatorConnection => AllConn3, 
            ManualMode => ManualMode3, 
            UnitName => cSendingUnitName, 
            Activity => Act3);
            
            UnitAllocator4 Invocation
               ( 1.75 , 1.46 , 0.0 , 0.02 , 0.02 
                ) : UnitAllocator (
            Recipe => Recipe4, 
            IdentificationNo => 4, 
            UnitSystemList => UnitSystemList, 
            AccessableUnits => AccessableUnits, 
            AllocatorConnection => AllConn4, 
            ManualMode => ManualMode4, 
            UnitName => cSendingUnitName, 
            Activity => Act4);
            
            OpRecGraphDoc2 Invocation
               ( 0.08 , 0.32 , 0.0 , 0.06 , 0.06 
                ) : OpRecGraphDoc (
            OpRecipeDocConn => OpRecipeDocConn, 
            PrinterSystem => PrinterSystem, 
            PrinterNo => PrinterNo, 
            FileExtension => ".psc", 
            MasterRecipe => False);
            
            ReadRecipe1 Invocation
               ( 0.08 , 0.96 , 0.0 , 0.06 , 0.06 
                ) : RestoreRecipe (
            RecipeSystem => RecipeSystem, 
            RecipeDirectory => RecipeDirectory, 
            RecipeRevServer => RecipeRevServer, 
            RevisionDelimiter => RevisionDelimiter, 
            RecipeRestoreConn => RecipeRestoreConn);
            
            ReadOpRecipe1 Invocation
               ( 0.08 , 0.1 , 0.0 , 0.06 , 0.06 
                ) : RestoreOpRecipe (
            RecipeSystem => RecipeSystem, 
            RecipeDirectory => RecipeDirectory, 
            RecipeRevServer => RecipeRevServer, 
            RevisionDelimiter => RevisionDelimiter, 
            OpRecipeRestoreConn => OpRecipeRestoreConn);
            
            OpRecipeEditor Invocation
               ( 0.08 , 0.64 , 0.0 , 0.06 , 0.06 
                ) : OpRecipeEditor (
            OpRecipeEditConn => OpRecipeEditConn, 
            OpRecipeControl => OpRecipeControl, 
            OpRecipeStatus => OprecipeStatus, 
            EnableEdit => EnableEdit, 
            EnableEditRestricted => EnableEditRestricted, 
            EditSeverity => EditSeverity, 
            EditClass => EditClass, 
            EnableControl => False);
            
            RecipeGraphDoc2 Invocation
               ( 0.08 , 1.16 , 0.0 , 0.06 , 0.06 
                ) : RecipeGraphDoc (
            RecipeDocConn => RecipeDocConnection, 
            PrinterSystem => PrinterSystem, 
            PrinterNo => PrinterNo, 
            FileExtension => ".psc", 
            MasterRecipe => False);
            
         
         ModuleDef
         ClippingBounds = ( 0.0 , 0.0 ) ( 1.78 , 1.68 )
         Grid = 0.01
         GraphObjects :
            TextObject ( 0.04 , 1.29 ) ( 0.13 , 1.31 ) 
               "RecipeEditConnection" 
               ConnectionNode ( 0.16 , 1.3 ) 
               RightAligned 
               OutlineColour : Colour0 = 2 
            TextObject ( 0.08 , 0.83 ) ( 0.17 , 0.85 ) 
               "BatchUnitConnection" 
               ConnectionNode ( 0.2 , 0.84 ) 
               RightAligned 
               OutlineColour : Colour0 = 2 
            TextObject ( 0.04 , 0.45 ) ( 0.13 , 0.47 ) 
               "OpRecipeEditConn" 
               ConnectionNode ( 0.16 , 0.46 ) 
               RightAligned 
               OutlineColour : Colour0 = 2 
            PolygonObject Polyline Connection ( 0.14 , 1.44 ) 
               ( 0.16 , 1.44 ) ( 0.16 , 1.3 ) 
               OutlineColour : Colour0 = -3 
            PolygonObject Polyline Connection ( 0.230001 , 1.6035 ) 
               ( 0.18 , 1.6 ) ( 0.18 , 1.29 ) ( 0.16 , 1.3 ) 
               OutlineColour : Colour0 = -3 
            PolygonObject Polyline Connection ( 0.230001 , 1.56693 ) 
               ( 0.18 , 1.56 ) ( 0.18 , 1.29 ) ( 0.16 , 1.3 ) 
               OutlineColour : Colour0 = -3 
            PolygonObject Polyline Connection ( 0.230001 , 1.53043 ) 
               ( 0.18 , 1.51 ) ( 0.18 , 1.29 ) ( 0.16 , 1.3 ) 
               OutlineColour : Colour0 = -3 
            PolygonObject Polyline Connection ( 0.230001 , 1.58522 ) 
               ( 0.2 , 1.59 ) ( 0.2 , 0.84 ) ( 0.2 , 0.84 ) 
               OutlineColour : Colour0 = -3 
            PolygonObject Polyline Connection ( 0.230001 , 1.54868 ) 
               ( 0.2 , 1.54 ) ( 0.2 , 0.84 ) ( 0.2 , 0.84 ) 
               OutlineColour : Colour0 = -3 
            PolygonObject Polyline Connection ( 0.230001 , 1.51218 ) 
               ( 0.2 , 1.49 ) ( 0.2 , 0.84 ) ( 0.2 , 0.84 ) 
               OutlineColour : Colour0 = -3 
            PolygonObject Polyline Connection ( 0.25 , 0.764433 ) 
               ( 0.2 , 0.76 ) ( 0.2 , 0.84 ) ( 0.2 , 0.84 ) 
               OutlineColour : Colour0 = -3 
            PolygonObject Polyline Connection ( 0.25 , 0.782933 ) 
               ( 0.16 , 0.78 ) ( 0.16 , 0.46 ) ( 0.16 , 0.46 ) 
               OutlineColour : Colour0 = -3 
            PolygonObject Polyline Connection ( 0.25 , 0.727433 ) 
               ( 0.2 , 0.72 ) ( 0.2 , 0.84 ) ( 0.2 , 0.84 ) 
               OutlineColour : Colour0 = -3 
            PolygonObject Polyline Connection ( 0.25 , 0.690433 ) 
               ( 0.2 , 0.68 ) ( 0.2 , 0.84 ) ( 0.2 , 0.84 ) 
               OutlineColour : Colour0 = -3 
            PolygonObject Polyline Connection ( 0.25 , 0.745933 ) 
               ( 0.16 , 0.74 ) ( 0.16 , 0.46 ) ( 0.16 , 0.46 ) 
               OutlineColour : Colour0 = -3 
            PolygonObject Polyline Connection ( 0.25 , 0.708933 ) 
               ( 0.16 , 0.7 ) ( 0.16 , 0.46 ) ( 0.16 , 0.46 ) 
               OutlineColour : Colour0 = -3 
            PolygonObject Polyline Connection ( 0.230001 , 1.49393 ) 
               ( 0.18 , 1.46 ) ( 0.18 , 1.29 ) ( 0.16 , 1.29 ) 
               ( 0.16 , 1.3 ) 
            PolygonObject Polyline Connection ( 0.230001 , 1.47568 ) 
               ( 0.2 , 1.47 ) ( 0.2 , 0.88 ) ( 0.2 , 0.84 ) 
            PolygonObject Polyline Connection ( 0.25 , 0.671933 ) 
               ( 0.16 , 0.66 ) ( 0.16 , 0.46 ) ( 0.16 , 0.46 ) 
            PolygonObject Polyline Connection ( 0.25 , 0.634933 ) 
               ( 0.16 , 0.62 ) ( 0.16 , 0.46 ) ( 0.16 , 0.46 ) 
            PolygonObject Polyline Connection ( 0.25 , 0.597933 ) 
               ( 0.16 , 0.58 ) ( 0.16 , 0.46 ) ( 0.16 , 0.46 ) 
            PolygonObject Polyline Connection ( 0.25 , 0.653433 ) 
               ( 0.2 , 0.64 ) ( 0.2 , 0.84 ) ( 0.2 , 0.84 ) 
            PolygonObject Polyline Connection ( 0.25 , 0.616433 ) 
               ( 0.2 , 0.6 ) ( 0.2 , 0.84 ) ( 0.2 , 0.84 ) 
            PolygonObject Polyline Connection ( 0.25 , 0.579433 ) 
               ( 0.2 , 0.56 ) ( 0.2 , 0.84 ) ( 0.2 , 0.84 ) 
         
         ENDDEF (*InfoFrame*);
         
      
      ModuleDef
      ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
      Two_Layers_ LayerLimit_ = 0.95
      Zoomable
      GraphObjects :
         RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         TextObject ( -1.0 , 0.92 ) ( 1.0 , 1.0 ) 
            "ProcessManager" LeftAligned 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         TextObject ( -0.2 , -0.88 ) ( 0.16 , -0.8 ) 
            "RecipeDirectory" 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         TextObject ( -0.6 , -0.88 ) ( -0.24 , -0.8 ) 
            "RecipeSystem" 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         TextObject ( 0.2 , -0.88 ) ( 0.56 , -0.8 ) 
            "JournalSystem1" 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         TextObject ( 0.6 , -0.88 ) ( 0.96 , -0.8 ) 
            "JournalSystem2" 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         TextObject ( 0.6 , -0.96 ) ( 0.96 , -0.88 ) 
            "JournalSystem2" VarName Width_ = 5  ValueFraction = 2  
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         TextObject ( -0.2 , -0.96 ) ( 0.16 , -0.88 ) 
            "RecipeDirectory" VarName Width_ = 5  ValueFraction = 2  
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         TextObject ( -0.6 , -0.96 ) ( -0.24 , -0.88 ) 
            "RecipeSystem" VarName Width_ = 5  ValueFraction = 2  
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         TextObject ( 0.2 , -0.96 ) ( 0.56 , -0.88 ) 
            "JournalSystem1" VarName Width_ = 5  ValueFraction = 2  
            Layer_ = 2
            OutlineColour : Colour0 = -3 
      InteractObjects :
         ProcedureInteract ( -0.8 , -0.8 ) ( 0.8 , 0.8 ) 
            ToggleWindow
            "" : InVar_ LitString "*InfoBM" "" : InVar_ "Name" False 0.0 : 
            InVar_ 0.02 0.0 : InVar_ 0.05 0.0 : InVar_ 0.96 0.0 : InVar_ 0.0 
            False 0 0 False 0 
            Layer_ = 1
            Variable = 0.0 
      
      ModuleCode
      EQUATIONBLOCK CheckError COORD -0.76, -0.92 OBJSIZE 0.16, 0.12
      Layer_ = 2 :
         Error = ErrorBM1 OR ErrorBM2 OR ErrorBM3 OR ErrorBM4 OR ErrorUSS1 OR 
            ErrorUSS2 OR ErrorUSS3 OR ErrorUSS4 OR ErrorUSS5 OR ErrorUSS6;
      
      ENDDEF (*ProcessManager*) (
      JournalSystem1 => JournalSystem1, 
      JournalSystem2 => JournalSystem2, 
      RecipeSystem => RecipeSystem, 
      RecipeDirectory => RecipeDirectory, 
      RecipeRevServer => RecipeRevServer, 
      RevisionDelimiter => RevisionDelimiter, 
      ProcessManagerNumber => ProcessManagerNumber, 
      EnableEdit => EnableEdit, 
      EnableEditRestricted => EnableEditRestricted, 
      EnableControl => EnableControl, 
      TestProcManager => TestProcManager, 
      PrinterSystem => PrinterSystem, 
      PrinterNo => PrinterNo);
      
      JournalListServer Invocation
         ( 1.22 , 0.1 , 0.0 , 0.08 , 0.08 
          ) : joulistserver (
      Name => "JournalListServer");
      
      BatchJournalList Invocation
         ( 1.04 , 0.1 , 0.0 , 0.08 , 0.08 
          ) : joulisteventlog (
      Name => "JournalListServer", 
      JournalName => "BatchID", 
      JournalSystem => GLOBAL OPname, 
      PageWidth => 132, 
      TextPrinterNo => PrinterNo, 
      PrinterSystem => PrinterSystem, 
      EnableEdit => EnableEdit);
      
      OperationEndReport Invocation
         ( 0.86 , 0.1 , 0.0 , 0.08 , 0.08 
          ) : MODULEDEFINITION DateCode_ 556671681 ( GroupConn = ScanGroup ) 
      MODULEPARAMETERS
         Name "IN Module name (= name of report)", FileName 
         "IN Name of the local file containing the report", OperationName "IN": 
         string ;
         StartTime "IN Start of operation", StopTime "IN Stop of operation": 
         time ;
         JournalSystem "IN Data to be printed in report, defined by the user", 
         JournalName "IN Data to be printed in report, defined by the user": 
         string ;
         PageLength "IN No. of lines per page": integer  := 64;
         PageWidth "IN No. of characters per line.": integer  := 80;
         EnableSpreadSheet "IN If true, use line and field delimiters": boolean  
         := False;
         LineDelimiter "IN Line delimiter for spreadsheet files", 
         FieldDelimiter "IN Field delimiter for spreadsheet files", 
         StringDelimiter "IN Inserted before and after strings in spreadsheets"
         : identstring  := "";
         Append "IN Append to existing file": boolean  := True;
         TrailingFormFeed 
         "IN If true then a formfeed is added after the report text": boolean  
         := False;
         FontSize "IN For edit-file objects": integer  := 15;
         Execute "IN Generate a report", Ready "OUT Generation ready": boolean 
         ;
         ReadyOK "OUT Report succesfully generated": boolean  := Default;
         ReportIsActive 
         "OUT USed to trig global cycletime control of report scan groups": 
         boolean ;
         ScanGroup "IN/OUT Scan group for this module": GroupData ;
      LOCALVARIABLES
         R "Common data for line and field modules.": ReportCommon ;
         FirstLine "Used by library modules.", LastLine 
         "Used by library modules.", HeaderFirstLine "Used by library modules."
         , HeaderEndLine "Used by library modules.": LineConnection ;
         ExecuteState "Used by library modules.": boolean State;
         StatValues: ReportStatistics ;
         Event: LoggedEvent ;
         InitJournalRead, NoMoreEntries, MoreEntries: boolean ;
         TimeOfEvent: time ;
         Alarm_NoInteraction, Alarm_Interaction, Interaction, OldExecute: 
         boolean ;
         ReportExtension: string  := ".R";
         Star: string  := "*";
         Tag "for filtering events from eventlog": string ;
         truevar: boolean  := True;
         InternalFilename: string ;
         status: integer ;
      SUBMODULES
         L1 Invocation
            ( -1.0 , -1.0 , 0.0 , 2.0 , 2.0 
             ) : MODULEDEFINITION DateCode_ 525195048 ( Frame_Module ) 
         SUBMODULES
            L2 Invocation
               ( 0.0 , 0.0 , 0.0 , 0.33333 , 0.33333 
                LayerModule ) : MODULEDEFINITION DateCode_ 525195048 ( 
            Frame_Module ) 
            SUBMODULES
               Code Invocation
                  ( 2.86 , 0.14 , 0.0 , 0.12 , 0.12 
                   ) : ReportMasterCode (
               R => R, 
               FirstLine => FirstLine, 
               LastLine => LastLine, 
               HeaderFirstLine => HeaderFirstLine, 
               HeaderEndLine => HeaderEndLine, 
               FileName => InternalFileName, 
               PageLength => PageLength, 
               PageWidth => PageWidth, 
               EnableSpreadSheet => EnableSpreadSheet, 
               LineDelimiter => LineDelimiter, 
               FieldDelimiter => FieldDelimiter, 
               StringDelimiter => StringDelimiter, 
               Append => Append, 
               TrailingFormFeed => trailingformfeed, 
               Execute => Execute, 
               Ready => Ready, 
               ReadyOK => ReadyOK);
               
               Line1 Invocation
                  ( 0.1 , 1.92 , 0.0 , 1.0 , 1.0 
                   ) : ReportControlAccept (
               ReportControl => R);
               
               Line99 Invocation
                  ( 0.1 , 1.32 , 0.0 , 1.0 , 1.0 
                   ) : ReportControlDivert (
               Continue => NoMoreEntries, 
               Divert => MoreEntries, 
               ReportControl => R);
               
               Line2 Invocation
                  ( 0.1 , 2.8 , 0.0 , 1.0 , 1.0 
                   ) : ReportLine (
               EnableModule => False, 
               ReportControl => R);
               
               TopLine Invocation
                  ( 0.1 , 2.1 , 0.0 , 1.0 , 1.0 
                   ) : ReportLine (
               EnableModule => False, 
               ReportControl => R);
               
               TopLine2 Invocation
                  ( 0.1 , 2.42 , 0.0 , 1.0 , 1.0 
                   ) : ReportLine (
               ReportControl => R);
               
               TopLine6 Invocation
                  ( 0.1 , 2.22 , 0.0 , 1.0 , 1.0 
                   ) : ReportLine (
               ReportControl => R);
               
               TopLine3 Invocation
                  ( 0.1 , 2.52 , 0.0 , 1.0 , 1.0 
                   ) : ReportLine (
               ReportControl => R);
               
               TopLine5 Invocation
                  ( 0.1 , 2.32 , 0.0 , 1.0 , 1.0 
                   ) : ReportLine (
               ReportControl => R);
               
               AlarmLine Invocation
                  ( 0.1 , 1.72 , 0.0 , 1.0 , 1.0 
                   ) : ReportLine (
               ReportControl => R);
               
               AlarmLine2 Invocation
                  ( 0.1 , 1.62 , 0.0 , 1.0 , 1.0 
                   ) : ReportLine (
               EnableModule => Alarm_INteraction, 
               ReportControl => R);
               
               Line3 Invocation
                  ( 0.1 , 1.82 , 0.0 , 1.0 , 1.0 
                   ) : ReportJourTableKey (
               ReportControl => R, 
               SingleReadMode => True, 
               InitSingleRead => InitJournalRead, 
               JournalName => JournalName, 
               JournalSystem => JournalSystem, 
               Tag => "Event", 
               Time1 => StartTime, 
               Time2 => StopTime, 
               InitialKeyValue => Tag, 
               KeyValue => Event.Id.Objecttag, 
               KeySwitches => truevar, 
               Value => Event, 
               TimeOfFoundEntry => TimeOfEvent, 
               NoMoreValues => NoMoreEntries, 
               MoreValues => MoreEntries);
               
               Pres Invocation
                  ( 1.98 , 0.02 , 0.0 , 0.99571 , 0.99571 
                   ) : ReportPres (
               Name => name, 
               Filename => internalfilename, 
               R => r, 
               Fontsize => fontsize, 
               Execute => execute, 
               Ready => ready);
               
               RepEventClassifyer Invocation
                  ( 0.24 , 1.72 , 0.0 , 0.07 , 0.04 
                   ) : MODULEDEFINITION DateCode_ 525195720
               MODULEPARAMETERS
                  Event "IN Event to be classified": LoggedEvent ;
                  EnableModule "IN if false, no classification is made.": 
                  boolean  := True;
                  Alarm_NoInteraction "OUT Event was alon, aloff, autoinhibit", 
                  Alarm_Interaction 
                  "OUT Event was alack,inhibit, cancel inhibit", Interaction 
                  "OUT Event was an operator interaction": boolean ;
                  ReportControl: ReportCommon ;
                  Prev "IN NODE In from previous field", Next 
                  "OUT NODE Out to next field": FieldConnection ;
               LOCALVARIABLES
                  error: boolean ;
               SUBMODULES
                  L1 Invocation
                     ( 5.96046E-08 , 0.0 , 0.0 , 2.0 , 2.0 
                      IgnoreMaxModule ) : MODULEDEFINITION DateCode_ 525195804 
                  ( Frame_Module ) 
                  SUBMODULES
                     L2
                     (*  *)
                      Invocation
                        ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0 
                         LayerModule ) : MODULEDEFINITION DateCode_ 525195804 ( 
                     Frame_Module ) 
                     
                     
                     ModuleDef
                     ClippingBounds = ( 0.0 , 0.0 ) 
                     ( 1.0 , 1.0 )
                     GraphObjects :
                        RectangleObject ( 0.0 , 0.0 ) 
                           ( 1.0 , 1.0 ) 
                           OutlineColour : Colour0 = -3 
                     
                     ModuleCode
                     EQUATIONBLOCK Classify COORD 0.12, 0.04 OBJSIZE 0.66, 0.9 
                     :
                        IF Prev.Execute THEN
                           (*  Work when previous field is ready *);
                           Prev.Execute = Off;
                           (* Classify event according to event types
                              to suit different presentation formats *);
                           SetBooleanValue(Alarm_NoInteraction, (Event.Id.Alon 
                           OR Event.Id.Aloff OR Event.Id.AutoInh OR Event.Id.
                           AutoInhOff) AND EnableModule);
                           SetBooleanValue(Alarm_Interaction, (Event.Id.Ack OR 
                           Event.Id.Inh OR Event.Id.CanInh OR Event.Id.
                           Opinteract) AND EnableModule);
                           SetBooleanValue(Interaction, Event.Id.OpInteract AND 
                           EnableModule);
                           Next.Execute = On;
                        ENDIF;
                     
                     ENDDEF (*L2*);
                     
                     FuncDisplay Invocation
                        ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0 
                         Enable_ = True : InVar_ False ) : MODULEDEFINITION 
                     DateCode_ 525195804 ( Frame_Module ) 
                     
                     
                     ModuleDef
                     ClippingBounds = ( 0.0 , 0.0 ) 
                     ( 1.0 , 1.0 )
                     GraphObjects :
                        RectangleObject ( 0.0 , 0.0 ) 
                           ( 1.0 , 1.0 ) 
                           OutlineColour : Colour0 = -3 
                           FillColour : Colour0 = 5 
                        TextObject ( 0.0 , 0.32 ) 
                           ( 0.48 , 0.66 ) 
                           "Prev" 
                           ConnectionNode ( 0.0 , 0.5 ) 
                           LeftAligned 
                           Enable_ = True : InVar_ False 
                           OutlineColour : Colour0 = -3 
                        TextObject ( 0.48 , 0.32 ) 
                           ( 0.98 , 0.66 ) 
                           "Next" 
                           ConnectionNode ( 1.0 , 0.5 ) 
                           RightAligned 
                           Enable_ = True : InVar_ False 
                           OutlineColour : Colour0 = -3 
                        TextObject ( 1.0 , 1.0 ) 
                           ( -1.11759E-08 , 7.45058E-09 ) 
                           "EventClassify" 
                           OutlineColour : Colour0 = -3 Colour1 = 12 
                     
                     ENDDEF (*FuncDisplay*);
                     
                  
                  ModuleDef
                  ClippingBounds = ( 0.0 , 0.0 ) 
                  ( 1.0 , 1.0 )
                  ZoomLimits = 0.84165 0.01
                  Zoomable
                  
                  ENDDEF (*L1*);
                  
               
               ModuleDef
               ClippingBounds = ( 0.0 , 0.0 ) ( 2.0 , 2.0 )
               
               ENDDEF (*RepEventClassifyer*) (
               Event => Event, 
               EnableModule => True, 
               Alarm_NoInteraction => Alarm_NoInteraction, 
               Alarm_Interaction => Alarm_Interaction, 
               Interaction => Interaction, 
               ReportControl => R);
               
               EventTime Invocation
                  ( 0.22 , 1.82 , 0.0 , 0.09 , 0.04 
                   ) : ReportTime (
               Value => TimeOfEvent, 
               TimeFormat => GLOBAL Progstationdata.Timeformats.time, 
               Width => 10, 
               Left => True, 
               ReportControl => R);
               
               Tag Invocation
                  ( 0.42 , 1.82 , 0.0 , 0.19 , 0.04 
                   ) : ReportString (
               Value => Event.id.objecttag, 
               Width => 20, 
               Left => True, 
               ReportControl => R);
               
               user1 Invocation
                  ( 0.42 , 1.72 , 0.0 , 0.19 , 0.04 
                   ) : ReportString (
               Value => "Username:", 
               Width => 20, 
               Left => True, 
               EnableModule => Alarm_INteraction, 
               ReportControl => R);
               
               data Invocation
                  ( 1.42 , 1.82 , 0.0 , 0.09 , 0.04 
                   ) : ReportString (
               Value => event.data, 
               ReportControl => R);
               
               Description Invocation
                  ( 0.82 , 1.82 , 0.0 , 0.29 , 0.04 
                   ) : ReportString (
               Value => Event.description, 
               Width => 30, 
               Left => True, 
               ReportControl => R);
               
               user Invocation
                  ( 0.82 , 1.72 , 0.0 , 0.29 , 0.04 
                   ) : ReportString (
               Value => Event.id.user, 
               Width => 20, 
               Left => True, 
               EnableModule => Alarm_INteraction, 
               ReportControl => R);
               
               dataold Invocation
                  ( 1.62 , 1.82 , 0.0 , 0.09 , 0.04 
                   ) : ReportString (
               Value => Event.dataold, 
               EnableModule => Interaction, 
               ReportControl => R);
               
               OpName Invocation
                  ( 0.3 , 2.1 , 0.0 , 0.25 , 0.04 
                   ) : ReportString (
               Value => OperationName, 
               Width => 20, 
               Left => True, 
               ReportControl => R);
               
               starttime Invocation
                  ( 0.84 , 2.1 , 0.0 , 0.18 , 0.04 
                   ) : ReportTime (
               Value => StartTime, 
               TimeFormat => GLOBAL Progstationdata.Timeformats.DateandTime, 
               Width => 20, 
               Left => True, 
               ReportControl => r);
               
               stoptime Invocation
                  ( 1.32 , 2.1 , 0.0 , 0.18 , 0.04 
                   ) : ReportTime (
               Value => StopTime, 
               TimeFormat => GLOBAL Progstationdata.Timeformats.DateandTime, 
               Width => 20, 
               LeadingSpaces => 2, 
               Left => True, 
               ReportControl => r);
               
               line Invocation
                  ( 1.22 , 2.1 , 0.0 , 0.04 , 0.04 
                   ) : ReportString (
               Value => "-", 
               Width => 1, 
               ReportControl => R);
               
               TopText Invocation
                  ( 0.3 , 2.32 , 0.0 , 0.5 , 0.04 
                   ) : ReportString (
               Value => "Events during the operation:", 
               Width => 40, 
               Left => True, 
               ReportControl => R);
               
               TopText_ Invocation
                  ( 0.3 , 2.22 , 0.0 , 0.5 , 0.04 
                   ) : ReportString (
               Value => "----------------------------", 
               Width => 40, 
               Left => True, 
               ReportControl => R);
               
            
            ModuleDef
            ClippingBounds = ( 0.0 , 0.0 ) ( 3.0 , 3.0 )
            GraphObjects :
               RectangleObject ( 0.0 , 0.0 ) ( 3.0 , 3.0 ) 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.14 , 2.62 ) ( 0.3 , 2.66 ) 
                  "FirstLine" 
                  ConnectionNode ( 0.1 , 2.64 ) 
                  LeftAligned 
                  Enable_ = True : InVar_ False 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.02 , 0.04 ) ( 0.18 , 0.08 ) 
                  "LastLine" 
                  ConnectionNode ( 0.1 , 0.12 ) 
                  
                  Enable_ = True : InVar_ False 
                  OutlineColour : Colour0 = -3 
               LineObject ( 1.8 , 2.98 ) ( 1.8 , -0.02 ) 
                  Enable_ = True : InVar_ False 
                  OutlineColour : Colour0 = -3 ColourStyle = 75.0 
               LineObject ( 0.2 , 2.99 ) ( 0.2 , -0.00999999 ) 
                  Enable_ = True : InVar_ False 
                  OutlineColour : Colour0 = -3 ColourStyle = 75.0 
               LineObject ( 2.84 , 3.0 ) ( 2.84 , -5.96046E-08 ) 
                  Enable_ = True : InVar_ False 
                  OutlineColour : Colour0 = -3 ColourStyle = 75.0 
               TextObject ( 0.14 , 2.72 ) ( 0.4 , 2.68 ) 
                  "HeaderEndLine" 
                  ConnectionNode ( 0.1 , 2.7 ) 
                  LeftAligned 
                  Enable_ = True : InVar_ False 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.14 , 2.98 ) ( 0.4 , 2.94 ) 
                  "HeaderFirstLine" 
                  ConnectionNode ( 0.1 , 2.96 ) 
                  LeftAligned 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.58 , 2.92 ) ( 1.36 , 3.0 ) 
                  "Header" 
                  Enable_ = True : InVar_ False 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.58 , 2.62 ) ( 1.36 , 2.72 ) 
                  "Page" 
                  Enable_ = True : InVar_ False 
                  OutlineColour : Colour0 = -3 
               TextObject ( 1.8 , 2.72 ) ( 1.8 , 2.62 ) 
                  "80" RightAligned 
                  Enable_ = True : InVar_ False 
                  OutlineColour : Colour0 = 22 
               TextObject ( 2.84 , 2.72 ) ( 2.84 , 2.62 ) 
                  "132" RightAligned 
                  Enable_ = True : InVar_ False 
                  OutlineColour : Colour0 = 22 
               PolygonObject Polyline Connection 
                  ( 0.2 , 2.84 ) ( 2.84 , 2.84 ) 
                  OutlineColour : Colour0 = -3 
                  FillColour : Colour0 = 47 
               LineObject ( 1.8 , 2.7 ) ( 1.8 , 0.3 ) 
                  Enable_ = True : InVar_ False 
                  OutlineColour : Colour0 = 22 
               PolygonObject Polyline Connection 
                  ( 0.1 , 2.96 ) ( 0.1 , 2.88 ) 
                  OutlineColour : Colour0 = -3 
               PolygonObject Polyline Connection 
                  ( 0.1 , 2.8 ) ( 0.1 , 2.7 ) 
                  OutlineColour : Colour0 = -3 
               PolygonObject Polyline Connection 
                  ( 0.1 , 1.9 ) ( 0.1 , 1.92 ) 
                  OutlineColour : Colour0 = -3 
               TextObject ( 0.2 , 2.02 ) ( 1.8 , 2.07 ) 
                  "Events :" LeftAligned 
                  OutlineColour : Colour0 = 22 
               PolygonObject Polyline Connection 
                  ( 0.4 , 1.86 ) ( 0.42 , 1.86 ) 
                  OutlineColour : Colour0 = -3 
               PolygonObject Polyline Connection 
                  ( 0.8 , 1.86 ) ( 0.82 , 1.86 ) 
                  OutlineColour : Colour0 = -3 
               PolygonObject Polyline Connection 
                  ( 0.42 , 1.82 ) ( 0.42 , 1.8 ) 
                  OutlineColour : Colour0 = -3 
               PolygonObject Polyline Connection 
                  ( 0.82 , 1.82 ) ( 0.82 , 1.8 ) 
                  OutlineColour : Colour0 = -3 
               PolygonObject Polyline Connection 
                  ( 0.1 , 1.36 ) ( 0.04 , 1.54 ) 
                  ( 0.04 , 1.96 ) ( 0.1 , 1.96 ) 
                  OutlineColour : Colour0 = -3 
               PolygonObject Polyline Connection 
                  ( 0.1 , 1.82 ) ( 0.1 , 1.8 ) 
                  OutlineColour : Colour0 = -3 
               PolygonObject Polyline Connection 
                  ( 0.1 , 1.72 ) ( 0.1 , 1.7 ) 
                  OutlineColour : Colour0 = -3 
               PolygonObject Polyline Connection 
                  ( 0.1 , 1.62 ) ( 0.1 , 1.4 ) 
                  OutlineColour : Colour0 = -3 
               PolygonObject Polyline Connection 
                  ( 0.1 , 0.12 ) ( 0.1 , 1.32 ) 
                  OutlineColour : Colour0 = -3 
               PolygonObject Polyline Connection 
                  ( 0.1 , 2.0 ) ( 0.1 , 2.1 ) 
                  OutlineColour : Colour0 = -3 
               PolygonObject Polyline Connection 
                  ( 2.84 , 2.14 ) ( 1.68 , 2.14 ) 
                  OutlineColour : Colour0 = -3 
               PolygonObject Polyline Connection 
                  ( 0.2 , 2.14 ) ( 0.3 , 2.14 ) 
                  OutlineColour : Colour0 = -3 
               PolygonObject Polyline Connection 
                  ( 0.8 , 2.14 ) ( 0.84 , 2.14 ) 
                  OutlineColour : Colour0 = -3 
               PolygonObject Polyline Connection 
                  ( 1.2 , 2.14 ) ( 1.22 , 2.14 ) 
                  OutlineColour : Colour0 = -3 
               PolygonObject Polyline Connection 
                  ( 1.3 , 2.14 ) ( 1.32 , 2.14 ) 
                  OutlineColour : Colour0 = -3 
               PolygonObject Polyline Connection 
                  ( 0.1 , 2.64 ) ( 0.1 , 2.6 ) 
                  OutlineColour : Colour0 = -3 
               PolygonObject Polyline Connection 
                  ( 0.1 , 2.52 ) ( 0.1 , 2.5 ) 
                  OutlineColour : Colour0 = -3 
               PolygonObject Polyline Connection 
                  ( 0.1 , 2.42 ) ( 0.1 , 2.4 ) 
                  OutlineColour : Colour0 = -3 
               PolygonObject Polyline Connection 
                  ( 0.1 , 2.32 ) ( 0.1 , 2.3 ) 
                  OutlineColour : Colour0 = -3 
               PolygonObject Polyline Connection 
                  ( 0.1 , 2.22 ) ( 0.1 , 2.18 ) 
                  OutlineColour : Colour0 = -3 
               PolygonObject Polyline Connection 
                  ( 0.2 , 2.56 ) ( 2.84 , 2.56 ) 
                  OutlineColour : Colour0 = -3 
               PolygonObject Polyline Connection 
                  ( 0.2 , 2.46 ) ( 2.84 , 2.46 ) 
                  OutlineColour : Colour0 = -3 
               PolygonObject Polyline Connection 
                  ( 0.2 , 2.36 ) ( 0.3 , 2.36 ) 
                  OutlineColour : Colour0 = -3 
               PolygonObject Polyline Connection 
                  ( 1.3 , 2.36 ) ( 2.84 , 2.36 ) 
                  OutlineColour : Colour0 = -3 
               PolygonObject Polyline Connection 
                  ( 0.2 , 2.26 ) ( 0.3 , 2.26 ) 
                  OutlineColour : Colour0 = -3 
               PolygonObject Polyline Connection 
                  ( 1.3 , 2.26 ) ( 2.84 , 2.26 ) 
                  OutlineColour : Colour0 = -3 
               PolygonObject Polyline Connection 
                  ( 1.4 , 1.86 ) ( 1.42 , 1.86 ) 
                  OutlineColour : Colour0 = -3 
               PolygonObject Polyline Connection 
                  ( 1.6 , 1.86 ) ( 1.62 , 1.86 ) 
                  OutlineColour : Colour0 = -3 
               PolygonObject Polyline Connection 
                  ( 0.8 , 1.76 ) ( 0.82 , 1.76 ) 
                  OutlineColour : Colour0 = -3 
               PolygonObject Polyline Connection 
                  ( 0.2 , 1.86 ) ( 0.22 , 1.86 ) 
                  OutlineColour : Colour0 = -3 
               PolygonObject Polyline Connection 
                  ( 1.8 , 1.86 ) ( 2.84 , 1.86 ) 
                  OutlineColour : Colour0 = -3 
               PolygonObject Polyline Connection 
                  ( 0.2 , 1.76 ) ( 0.24 , 1.76 ) 
                  OutlineColour : Colour0 = -3 
               PolygonObject Polyline Connection 
                  ( 0.38 , 1.76 ) ( 0.42 , 1.76 ) 
                  OutlineColour : Colour0 = -3 
               PolygonObject Polyline Connection 
                  ( 1.4 , 1.76 ) ( 2.84 , 1.76 ) 
                  OutlineColour : Colour0 = -3 
               PolygonObject Polyline Connection 
                  ( 0.2 , 1.66 ) ( 2.84 , 1.66 ) 
                  OutlineColour : Colour0 = -3 
            
            ModuleCode
            EQUATIONBLOCK Code COORD 1.56, 0.02 OBJSIZE 0.4, 0.1 :
               ReportIsActive = Off;
               IF Execute AND  NOT Ready THEN
                  (* Kick watchdog while I'm active *);
                  ReportIsActive = On;
               ENDIF;
               IF Execute AND  NOT OldExecute THEN
                  InitJournalRead = On;
                  ClearString(InternalFilename);
                  InsertString(InternalFilename, Filename, StringLength(
                  Filename), Status);
                  InsertString(InternalFilename, ReportExtension, StringLength(
                  ReportExtension), Status);
                  (* Search string for events:  "*OperationName*"    *);
                  ClearString(Tag);
                  InsertString(Tag, Star, StringLength(Star), Status);
                  InsertString(Tag, Operationname, StringLength(Operationname), 
                  Status);
                  InsertString(Tag, Star, StringLength(Star), Status);
               ENDIF;
               OldExecute = Execute;
            
            ENDDEF (*L2*);
            
            icon Invocation
               ( 2.98023E-08 , -3.72529E-08 , 0.0 , 1.0 , 1.0 
                ) : ReportMasterIcon (
            error => R.error);
            
         
         ModuleDef
         ClippingBounds = ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
         ZoomLimits = 0.94193 0.01
         Zoomable
         InteractObjects :
            ProcedureInteract ( 0.0 , -5.96046E-08 ) 
               ( 1.0 , 1.0 ) 
               ToggleWindow
               "" : InVar_ LitString "+L2+Pres" "" False : InVar_ True 0.0 0.0 
               0.0 : InVar_ 0.24 0.0 False 0 0 False 0 
               Variable = 0.0 
         
         ENDDEF (*L1*);
         
      
      ModuleDef
      ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
      
      ENDDEF (*OperationEndReport*) (
      Name => "ReportName", 
      FileName => BatchID, 
      OperationName => "", 
      StartTime => StartTime, 
      StopTime => StopTime, 
      JournalSystem => JournalSystem1, 
      JournalName => BatchID, 
      Append => False, 
      Execute => ExecuteReport, 
      Ready => ReportReady, 
      ReportIsActive => ReportIsActive, 
      ScanGroup => ScanGroup);
      
      TestBaControlStatus1 Invocation
         ( 0.92 , 0.78 , 0.0 , 0.06 , 0.06 
          ) : TestBaControlStatus1 (
      BatchControl => TestProcManager.BatchControl1, 
      BatchStatus => TestProcManager.BatchStatus1);
      
      TestOpControlStatus1 Invocation
         ( 1.2 , 0.78 , 0.0 , 0.06 , 0.06 
          ) : TestOpControlStatus1 (
      UnitName => UnitList.Unit1, 
      OperationControl => TestProcManager.OperationControl1, 
      OperationStatus => TestProcManager.OperationStatus1);
      
      TestOpControlStatus2 Invocation
         ( 1.2 , 0.62 , 0.0 , 0.06 , 0.06 
          ) : TestOpControlStatus1 (
      UnitName => UnitList.Unit2, 
      OperationControl => TestProcManager.OperationControl2, 
      OperationStatus => TestProcManager.OperationStatus2);
      
      TestOpControlStatus3 Invocation
         ( 1.2 , 0.46 , 0.0 , 0.06 , 0.06 
          ) : TestOpControlStatus1 (
      UnitName => UnitList.Unit3, 
      OperationControl => TestProcManager.OperationControl3, 
      OperationStatus => TestProcManager.OperationStatus3);
      
      TestOpControlStatus4 Invocation
         ( 1.2 , 0.3 , 0.0 , 0.06 , 0.06 
          ) : TestOpControlStatus1 (
      UnitName => UnitList.Unit4, 
      OperationControl => TestProcManager.OperationControl4, 
      OperationStatus => TestProcManager.OperationStatus4);
      
      TestBaControlStatus2 Invocation
         ( 0.92 , 0.62 , 0.0 , 0.06 , 0.06 
          ) : TestBaControlStatus1 (
      BatchControl => TestProcManager.BatchControl2, 
      BatchStatus => TestProcManager.BatchStatus2);
      
      TestBaControlStatus3 Invocation
         ( 0.92 , 0.46 , 0.0 , 0.06 , 0.06 
          ) : TestBaControlStatus1 (
      BatchControl => TestProcManager.BatchControl3, 
      BatchStatus => TestProcManager.BatchStatus3);
      
      TestBaControlStatus4 Invocation
         ( 0.92 , 0.3 , 0.0 , 0.06 , 0.06 
          ) : TestBaControlStatus1 (
      BatchControl => TestProcManager.BatchControl4, 
      BatchStatus => TestProcManager.BatchStatus4);
      
   
   ModuleDef
   ClippingBounds = ( 0.0 , 0.0 ) ( 1.4 , 0.90111 )
   GraphObjects :
      RectangleObject ( 1.3411E-07 , 1.86265E-08 ) 
         ( 1.4 , 0.9 ) 
         OutlineColour : Colour0 = -3 
      TextObject ( -1.49012E-08 , 0.74 ) ( 0.3 , 0.8 ) 
         "OpName" VarName Width_ = 5 : InVar_ 5  ValueFraction = 2  
         OutlineColour : Colour0 = -3 
      TextObject ( 0.88 , 0.18 ) ( 1.3 , 0.24 ) 
         "Inspect batch journal" LeftAligned 
         OutlineColour : Colour0 = -3 
      TextObject ( 4.47035E-08 , 0.8 ) ( 0.62 , 0.9 ) 
         "ProcessManager :" 
         OutlineColour : Colour0 = -3 
      TextObject ( 0.1 , 0.14 ) ( 0.34 , 0.2 ) 
         "BatchID:" LeftAligned 
         OutlineColour : Colour0 = -3 
      TextObject ( 0.1 , 0.08 ) ( 0.34 , 0.14 ) 
         "Execute:" LeftAligned 
         OutlineColour : Colour0 = -3 
      TextObject ( 0.1 , 0.02 ) ( 0.34 , 0.08 ) 
         "Ready" LeftAligned 
         Enable_ = True : InVar_ "ReportReady" 
         OutlineColour : Colour0 = -3 
      TextObject ( 0.34 , 0.02 ) ( 0.76 , 0.08 ) 
         "Report is active" LeftAligned 
         Enable_ = True : InVar_ "ReportIsActive" 
         OutlineColour : Colour0 = -3 
      TextObject ( 0.86 , 0.82 ) ( 1.26 , 0.86 ) 
         "UnitList.Unit1" VarName Width_ = 5  ValueFraction = 2  
      TextObject ( 0.86 , 0.66 ) ( 1.26 , 0.7 ) 
         "UnitList.Unit2" VarName Width_ = 5  ValueFraction = 2  
      TextObject ( 0.86 , 0.5 ) ( 1.26 , 0.54 ) 
         "UnitList.Unit3" VarName Width_ = 5  ValueFraction = 2  
      TextObject ( 0.86 , 0.34 ) ( 1.26 , 0.38 ) 
         "UnitList.Unit4" VarName Width_ = 5  ValueFraction = 2  
      TextObject ( 0.62 , 0.8 ) ( 0.82 , 0.9 ) 
         "ProcessManagerNumber" VarName Width_ = 5 : InVar_ 2  ValueFraction = 
         2  LeftAligned 
   InteractObjects :
      TextBox_ ( 0.34 , 0.14 ) ( 0.76 , 0.2 ) 
         String_Value
         Variable = "" : OutVar_ "BatchID" CenterAligned Abs_ Digits_
         
         FillColour : Colour0 = 9 Colour1 = -1 
      ComBut_ ( 0.34 , 0.08 ) ( 0.4 , 0.14 ) 
         Bool_Value
         Variable = False : OutVar_ "ExecuteReport" ToggleAction
         Abs_ SetApp_
         
   
   ENDDEF (*OpStationBatch*);
   
   UnitAllocator
   (* Documentation for the master modules
      is available in the general description of the library.
      
      1. Function
      
      2. Relation to other modules
      
      3. Comments on connection list
      
      4. Operators interface
      4.1 Pop-up windows
      
      4.2 Logging of operator interaction
      
      4.3 Modules accessible through pathstring
      "ModuleName*Info"
      
      5. Execution
      Inherits the scangroup of its surrounding.
      
      6. Opsave
      
      7. Advice for usage *)
    = MODULEDEFINITION DateCode_ 179596466
   MODULEPARAMETERS
      Recipe "IN The recipe": RecipeType ;
      IdentificationNo "IN Unique identification number 0-5": integer ;
      UnitSystemList "IN A list of the units and their systems", 
      AccessableUnits "IN Connect a variable with list of all accessable units"
      : AnyType ;
      AllocatorConnection "IN <=> Connection to UnitSupervisor": 
      AllocatorConnectType ;
      ManualModeIfNotFree 
      "IN If true go to manual allocation if unit suitable but not free": 
      boolean  := False;
      ManualModeIfEndOList 
      "IN If true go to manual mode if end of list and no unit allocated, else continue from start of list"
      : boolean  := True;
      ManualMode "IN/OUT Manual mode": boolean  := Default;
      ContinueModeIfNotFre 
      "IN 1=From start, 2=Form current unit, 3=After current unit": integer  := 
      3;
      EnableInteraction "IN Enable interaction": boolean  := True;
      InteractionSeverity "IN Interaction severity 0-127": integer  := 0;
      InteractionClass "IN Interaction class 1-98": integer  := 1;
      Error "OUT Sum error": boolean  := Default;
      Warning 
      "OUT The operator has specified an operation in a parallel branch": 
      boolean  := Default;
   LOCALVARIABLES
      PrgStep: integer  := 100;
      ExecuteManual, EnableExecuteManual, EnableAbortThisReq: boolean ;
      DisableManAuto: boolean  := True;
      Abort, AbortThisRequest, EnableAbort, SpecificUnit: boolean ;
      InfoTextIndex: integer ;
      UnitNameChanged: boolean ;
      DummyIndex: integer ;
      Operation, Result: OperationType ;
      EmptyString: identstring  := "";
      UnitListIndex, UnitSystemListIndex: integer ;
      UnitSystemListSize: integer  := 1000;
      DummyString: string ;
      NewOperation: boolean ;
      AllocateInquiry: AllocateInquiryType ;
      AllocateResponse: AllocateResponseType ;
      ManualModeState: boolean State;
      ErrorStep, ErrorStatus, ErrorIndex: integer ;
      ErrorLocal, ErrorInSubModule: boolean ;
      Status: integer ;
      Tag "Used for logging of operations": tagstring  := "";
      UnderScore: identstring  := "_";
      A: identstring  := "A";
      Dummy: boolean ;
      Free: boolean State;
      WarningColour: integer  := 32;
      OnColour: integer ;
   SUBMODULES
      Icon Invocation
         ( -1.0 , -1.0 , 0.0 , 2.0 , 2.0 
          Layer_ = 1
          ) : UnitAllocatorIcon (
      Error => Error, 
      Warning => ManualMode, 
      WarningColour => GLOBAL ProgStationData.Colours.WarningColour);
      
      UnitAllocatorCore Invocation
         ( 0.46 , -0.6 , 0.0 , 0.16 , 0.16 
          Layer_ = 2
          ) : UnitAllocatorCore (
      IdentificationNo => IdentificationNo, 
      AllocatorConnection => AllocatorConnection, 
      AllocateInquiry => AllocateInquiry, 
      AllocateResponse => AllocateResponse, 
      Error => ErrorInSubModule, 
      UnitName => UnitName, 
      NewOperation => NewOperation);
      
      BatchErrorText Invocation
         ( -1.0 , 0.58 , 0.0 , 2.0 , 2.0 
          Layer_ = 2
          ) : BatchErrorText (
      ErrorStep => ErrorStep, 
      ErrorStatus => ErrorStatus, 
      ErrorIndex => ErrorIndex);
      
      BatchWindowControl Invocation
         ( 0.1 , -0.6 , 0.0 , 0.16 , 0.16 
          Layer_ = 2
          ) : BatchWindowControl (
      WindowTitle => AllocatorConnection.Allocate.SendingUnitName, 
      ToggleWindow => AllocatorConnection.Allocate.ToggleAllocateWindow, 
      WindowPath => "-+Control", 
      xSize => 0.36, 
      ProgStationData => GLOBAL ProgStationData);
      
      ColourExtraction Invocation
         ( 0.82 , -0.6 , 0.0 , 0.16 , 0.16 
          Layer_ = 2
          ) : ColourExtraction (
      WarningColour => WarningColour, 
      OnColour => OnColour);
      
      Control Invocation
         ( 0.12 , -0.3 , 0.0 , 0.52 , 0.52 
          Layer_ = 2
          ) : MODULEDEFINITION DateCode_ 177914051 ( Frame_Module ) 
      SUBMODULES
         ErrorIcon1 Invocation
            ( 1.4 , 0.4 , 0.0 , 0.1 , 0.1 
             Enable_ = True : InVar_ "Error" ) : ErrorIcon;
         
         OpRecManIcon Invocation
            ( 1.25 , 1.45 , 0.0 , 0.1 , 0.1 
             Dim_ = False : ( NOT (EnableInteraction AND  NOT DisableManAuto)) 
             ) : ManIcon;
         
         OpRecAutoIcon Invocation
            ( 1.38 , 1.45 , 0.0 , 0.1 , 0.1 
             Dim_ = False : ( NOT (EnableInteraction AND  NOT DisableManAuto)) 
             ) : AutoIcon;
         
         WarningIcon Invocation
            ( 1.29 , 0.4 , 0.0 , 0.1 , 0.1 
             Enable_ = True : InVar_ "Warning" ) : WarningIcon;
         
         ExecuteStart Invocation
            ( 1.39 , 0.75 , 0.0 , 0.1 , 0.1 
             Dim_ = False : ( NOT (EnableExecuteManual AND EnableInteraction)) 
             ) : ExecuteIcon;
         
         ExecuteAbort Invocation
            ( 1.39 , 0.65 , 0.0 , 0.1 , 0.1 
             Dim_ = False : ( NOT (EnableAbort AND EnableInteraction)) ) : 
         ExecuteIcon;
         
         ExecuteAbortRequest Invocation
            ( 1.39 , 0.55 , 0.0 , 0.1 , 0.1 
             Dim_ = False : ( NOT (EnableAbortThisReq AND EnableInteraction)) ) 
         : ExecuteIcon;
         
      
      ModuleDef
      ClippingBounds = ( 0.0 , 0.0 ) ( 1.5 , 1.57 )
      Grid = 0.01
      GraphObjects :
         RectangleObject ( 0.0 , 0.0 ) ( 1.5 , 1.57 ) 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.0 , 0.75 ) ( 1.38 , 0.85 ) 
            "Start/Continue allocation:" LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 2.98023E-08 , 0.65 ) ( 1.38 , 0.75 ) 
            "Abort allocation:" LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 2.23517E-08 , 0.55 ) ( 1.38 , 0.65 ) 
            "Abort this request:" LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.0 , 0.3 ) ( 0.7 , 0.4 ) 
            "Requested unit:" LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( -3.72529E-09 , 0.2 ) ( 0.7 , 0.3 ) 
            "Found unit:" LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.7 , 0.3 ) ( 1.5 , 0.4 ) 
            "AllocateInquiry.RemoteUnitName" VarName Width_ = 5  ValueFraction 
            = 2  LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.7 , 0.2 ) ( 1.5 , 0.3 ) 
            "AllocatorConnection.UnitAllocated.UnitName" VarName Width_ = 5  
            ValueFraction = 2  LeftAligned 
            OutlineColour : Colour0 = -3 
         TextObject ( 1.49012E-08 , 0.1 ) ( 0.4 , 0.2 ) 
            "Info:" LeftAligned 
            OutlineColour : Colour0 = -3 
         CompositeObject 
         CompositeObject 
         TextObject ( 0.0 , 1.19 ) ( 1.5 , 1.29 ) 
            "Equipment requirements" 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.0 , 1.34 ) ( 0.6 , 1.44 ) 
            "Operation:" 
            OutlineColour : Colour0 = -3 
         TextObject ( 2.23517E-08 , 1.44 ) ( 1.24 , 1.56 ) 
            "Allocation" 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.0 , 0.4 ) ( 1.28 , 0.5 ) 
            "Status" 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.6 , 1.34 ) ( 1.5 , 1.44 ) 
            "AllocatorConnection.Allocate.OperationName" VarName Width_ = 5 : 
            InVar_ 5  ValueFraction = 2  
            OutlineColour : Colour0 = -3 
      InteractObjects :
         CheckBox_ ( 0.02 , 0.85 ) ( 0.8 , 0.95 ) 
            Bool_Value
            Enable_ = True : (EnableInteraction AND EnableExecuteManual) 
            Variable = False : OutVar_ 
            "AllocatorConnection.Allocate.RequiredUnit.Used" TextObject = "" : 
            InVar_ LitString "Unit" 
            
            FillColour : Colour1 = -1 
         TextBox_ ( 0.8 , 0.85 ) ( 1.49 , 0.95 ) 
            String_Value
            Enable_ = True : (EnableInteraction AND EnableExecuteManual) 
            Variable = "" : OutVar_ 
            "AllocatorConnection.Allocate.RequiredUnit.Value" Event_Text_ = "" 
            : InVar_ LitString "Unit requirements" Event_Tag_ = "" : InVar_ 
            "Tag" Event_Severity_ = 0 : InVar_ "InteractionSeverity" 
            Event_Class_ = 0 : InVar_ "InteractionClass" Visible_ = True : 
            InVar_ "AllocatorConnection.Allocate.RequiredUnit.Used" LeftAligned 
            Abs_ Digits_
            
            FillColour : Colour0 = 9 Colour1 = -1 
         ComBut_ ( 1.39 , 0.75 ) ( 1.49 , 0.85 ) 
            Bool_Value
            Enable_ = True : (EnableExecuteManual AND EnableInteraction) 
            Variable = False : OutVar_ "ExecuteManual" Event_Text_ = "" : 
            InVar_ LitString "Start/Continue allocation" Event_Tag_ = "" : 
            InVar_ "Tag" Event_Severity_ = 0 : InVar_ "InteractionSeverity" 
            Event_Class_ = 0 : InVar_ "InteractionClass" SetAction
            Abs_ 
         ComBut_ ( 1.39 , 0.65 ) ( 1.49 , 0.75 ) 
            Bool_Value
            Enable_ = True : (EnableAbort AND EnableInteraction) Variable = 
            False : OutVar_ "Abort" Event_Text_ = "" : InVar_ LitString 
            "Abort allocation" Event_Tag_ = "" : InVar_ "Tag" Event_Severity_ = 
            0 : InVar_ "InteractionSeverity" Event_Class_ = 0 : InVar_ 
            "InteractionClass" SetAction
            Abs_ 
         ComBut_ ( 1.39 , 0.55 ) ( 1.49 , 0.65 ) 
            Bool_Value
            Enable_ = True : (EnableAbortThisReq AND EnableInteraction) 
            Variable = False : OutVar_ "AbortThisRequest" Event_Text_ = "" : 
            InVar_ LitString "Abort this request" Event_Tag_ = "" : InVar_ 
            "Tag" Event_Severity_ = 0 : InVar_ "InteractionSeverity" 
            Event_Class_ = 0 : InVar_ "InteractionClass" SetAction
            Abs_ 
         ComBut_ ( 1.37 , 1.44 ) ( 1.49 , 1.56 ) 
            Bool_Value
            Enable_ = True : (EnableInteraction AND  NOT DisableManAuto) 
            Variable = False : OutVar_ "ManualMode" Event_Text_ = "" : InVar_ 
            LitString "Manual" Event_Tag_ = "" : InVar_ "Tag" Event_Severity_ = 
            0 : InVar_ "InteractionSeverity" Event_Class_ = 0 : InVar_ 
            "InteractionClass" ResetAction
            Abs_ SetApp_
            
         ComBut_ ( 1.24 , 1.44 ) ( 1.36 , 1.56 ) 
            Bool_Value
            Enable_ = True : (EnableInteraction AND  NOT DisableManAuto) 
            Variable = False : OutVar_ "ManualMode" Event_Text_ = "" : InVar_ 
            LitString "Manual" Event_Tag_ = "" : InVar_ "Tag" Event_Severity_ = 
            0 : InVar_ "InteractionSeverity" Event_Class_ = 0 : InVar_ 
            "InteractionClass" SetAction
            Abs_ SetApp_
            
         CheckBox_ ( 0.02 , 1.05 ) ( 0.8 , 1.15 ) 
            Bool_Value
            Enable_ = True : (EnableInteraction AND EnableExecuteManual) 
            Variable = False : OutVar_ 
            "AllocatorConnection.Allocate.EquipmentRequirement.MinVolume.Used" 
            TextObject = "" : InVar_ LitString "Volume:" 
            
            FillColour : Colour1 = -1 
         CheckBox_ ( 0.02 , 0.95 ) ( 0.8 , 1.05 ) 
            Bool_Value
            Enable_ = True : (EnableInteraction AND EnableExecuteManual) 
            Variable = False : OutVar_ 
            "AllocatorConnection.Allocate.EquipmentRequirement.AgitatorPresent.Used" 
            TextObject = "" : InVar_ LitString "Agitator:" 
            
            FillColour : Colour1 = -1 
         CheckBox_ ( 0.8 , 0.95 ) ( 1.5 , 1.05 ) 
            Bool_Value
            Enable_ = True : (EnableInteraction AND EnableExecuteManual) 
            Variable = False : OutVar_ 
            "AllocatorConnection.Allocate.EquipmentRequirement.AgitatorPresent.Value" 
            Event_Text_ = "" : InVar_ LitString "Agitator" Event_Tag_ = "" : 
            InVar_ "Tag" Event_Severity_ = 0 : InVar_ "InteractionSeverity" 
            Event_Class_ = 0 : InVar_ "InteractionClass" Visible_ = True : 
            InVar_ 
            "AllocatorConnection.Allocate.EquipmentRequirement.AgitatorPresent.Used" 
            TextObject = "" : InVar_ LitString "Present" 
            
            FillColour : Colour1 = -1 
         TextBox_ ( 0.8 , 1.05 ) ( 1.49 , 1.15 ) 
            Int_Value
            Enable_ = True : (EnableInteraction AND EnableExecuteManual) 
            Variable = 0 : OutVar_ 
            "AllocatorConnection.Allocate.EquipmentRequirement.MinVolume.Value" 
            OpMin = 0 : InVar_ 0 OpMax = 2147483647 : InVar_ 1000000000 
            Event_Text_ = "" : InVar_ LitString "Volume" Event_Tag_ = "" : 
            InVar_ "Tag" Event_Severity_ = 0 : InVar_ "InteractionSeverity" 
            Event_Class_ = 0 : InVar_ "InteractionClass" Visible_ = True : 
            InVar_ 
            "AllocatorConnection.Allocate.EquipmentRequirement.MinVolume.Used" 
            LeftAligned Abs_ Digits_
            
            FillColour : Colour0 = 9 Colour1 = -1 
      
      ENDDEF (*Control*);
      
   
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   Two_Layers_ LayerLimit_ = 0.95
   Zoomable
   GraphObjects :
      RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      TextObject ( -1.0 , 0.8 ) ( 1.0 , 0.96 ) 
         "UnitAllocatorMaster" 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
   InteractObjects :
      ProcedureInteract ( -0.8 , -0.8 ) ( 0.8 , 0.8 ) 
         ToggleWindow
         "" : InVar_ LitString "++Control" "" False : InVar_ True 0.0 : InVar_ 
         0.1 0.0 : InVar_ -0.1 0.0 : InVar_ 0.24 0.0 False 0 0 False 0 
         Layer_ = 1
         Variable = 0.0 
      ProcedureInteract ( -0.8 , -0.8 ) ( 0.8 , 0.8 ) 
         ToggleWindow
         "" : InVar_ LitString "+Control" "" : InVar_ 
         "AllocatorConnection.Allocate.SendingUnitName" False : InVar_ True 0.0 
         : InVar_ 0.1 0.0 : InVar_ -0.1 0.0 : InVar_ 0.36 0.0 False 0 0 False 0 
         Layer_ = 1
         Variable = 0.0 
   
   ModuleCode
   EQUATIONBLOCK Error COORD -0.84, 0.04 OBJSIZE 0.36, 0.18
   Layer_ = 2 :
      (* This equation block is added to avoid a loop *);
      (* Update Error *);
      Error = ErrorLocal OR ErrorInSubModule;
   EQUATIONBLOCK Delay COORD -0.84, -0.88 OBJSIZE 0.36, 0.18
   Layer_ = 2 :
      (* This code is added in order to avoid loops *);
      AllocatorConnection.UnitAllocated.Free = Free:Old;
      AllocatorConnection.UnitAllocated.ManualMode = ManualModeState:Old;
   EQUATIONBLOCK Code COORD -0.84, -0.5 OBJSIZE 0.36, 0.36
   Layer_ = 2 :
      (* "Free" is only set during one scan *);
      Free:New = False;
      (* Initiate *);
      IF AllocatorConnection.Allocate.Initiate THEN
         SetBooleanValue(AllocatorConnection.Allocate.Initiate, False);
         ManualMode = AllocatorConnection.Allocate.ManualAllocation;
         InfoTextIndex = 14;
      ENDIF;
      (* Start allocation on command *);
      IF PrgStep == 100 AND AllocatorConnection.Allocate.Execute THEN
         (* Reset *);
         AllocatorConnection.Allocate.Execute = False;
         InfoTextIndex = 1;
         UnitListIndex = 1;
         (* Automatic or manual allocation? *);
         (* Construct tag for logging of operator's interaction                
         *);
         ClearString(Tag);
         CopyVariable(AllocatorConnection.Allocate.SendingUnitName, Tag, Status
         );
         SetStringPos(Tag, StringLength(Tag) + 1, Status);
         InsertString(Tag, UnderScore, 1, Status);
         InsertString(Tag, AllocatorConnection.Allocate.OperationName, 
         StringLength(AllocatorConnection.Allocate.OperationName), Status);
         InsertString(Tag, UnderScore, 1, Status);
         InsertString(Tag, A, 1, Status);
         PrgStep = 200;
      ENDIF;
      (* Get next candidate unit *);
      IF PrgStep == 200 AND ( NOT ManualMode OR ExecuteManual OR Abort) OR 
      PrgStep == 201 THEN
         (* Reset state variables *);
         InfoTextIndex = 0;
         ErrorLocal = False;
         Warning = False;
         IF Abort THEN
            (* Abort allocation *);
            InfoTextIndex = 7;
            (* Reset state variable *);
            Free:New = True;
            PrgStep = 100;
         ELSE
            (* Start allocation *);
            ExecuteManual = False;
            IF  NOT AllocatorConnection.Allocate.RequiredUnit.Used THEN
               (* Get next candidate unit from the list *);
               SpecificUnit = False;
               GetRecordComponent(AccessableUnits, UnitListIndex, 
               AllocateInquiry.RemoteUnitName, Status);
               UnitListIndex = UnitListIndex + 1;
               IF Status > 0 THEN
                  (* Get system in which candidate unit is located              
                  *);
                  PrgStep = 300;
               ELSIF Status ==  -6 THEN
                  (* All units in the list are checked *);
                  InfoTextIndex = 9;
                  IF ManualModeIfEndOList THEN
                     ManualMode = True;
                  ENDIF;
                  UnitListIndex = 1;
               ELSE
                  (* Error *);
                  ErrorLocal = True;
                  ErrorStep = PrgStep;
                  ErrorStatus = Status;
                  ErrorIndex = Status;
                  InfoTextIndex = 6;
                  ManualMode = True;
                  PrgStep = 900;
               ENDIF;
            ELSE
               (* Candidate unit specified *);
               SpecificUnit = True;
               CopyVariable(AllocatorConnection.Allocate.RequiredUnit.Value, 
               AllocateInquiry.RemoteUnitName, Status);
               (* Get system in which the candidate unit is located                
               *);
               PrgStep = 300;
            ENDIF;
         ENDIF;
      ENDIF;
      (* Get system in which the candidate unit is located *);
      IF PrgStep == 300 THEN
         UnitSystemListIndex = 0;
         CopyVariable(AllocateInquiry.RemoteUnitName, DummyString, Status);
         ErrorLocal =  NOT SearchRecComponent(UnitSystemList, 
            UnitSystemListIndex, UnitSystemListSize, DummyString, DummyString, 
            DummyString, Status);
         IF  NOT ErrorLocal AND Status > 0 THEN
            GetRecordComponent(UnitSystemList, UnitSystemListIndex + 1, 
            AllocateInquiry.RemoteUnitSystem, Status);
            IF Status > 0 THEN
               (* Continue allocation *);
               PrgStep = 400;
            ELSE
               (* Error *);
               ErrorLocal = True;
               ErrorStep = PrgStep;
               ErrorStatus = Status;
               ErrorIndex = Status;
               InfoTextIndex = 6;
               ManualMode = True;
               PrgStep = 900;
            ENDIF;
         ELSE
            (* Error *);
            ErrorLocal = True;
            ErrorStep = PrgStep;
            ErrorStatus = Status;
            IF Status > 0 THEN
               (* Can not find candidate unit in system list *);
               InfoTextIndex = 13;
               ErrorIndex = 190;
            ELSE
               (* Other error *);
               InfoTextIndex = 6;
               ErrorIndex = Status;
            ENDIF;
            ManualMode = True;
            PrgStep = 900;
         ENDIF;
      ENDIF;
      (* Send request to candidate unit *);
      IF PrgStep == 400 OR PrgStep == 401 AND (ExecuteManual OR Abort) THEN
         InfoTextIndex = 0;
         IF Abort THEN
            (* Abort allocation *);
            InfoTextIndex = 7;
            Free:New = True;
            PrgStep = 100;
         ELSE
            (* Continue allocation *);
            InfoTextIndex = 10;
            ExecuteManual = False;
            (* Send request to candidate unit *);
            AllocateInquiry.Execute = True;
            PrgStep = 500;
         ENDIF;
      ENDIF;
      (* Wait for answer from candidate unit *);
      IF PrgStep == 500 AND (AllocateResponse.Execute OR AbortThisRequest) THEN
         IF AbortThisRequest THEN
            (* Abort current allocation request. Continue allocation with next candidate unit 
            *);
            AllocateInquiry.Abort = True;
            InfoTextIndex = 11;
            PrgStep = 200;
         ELSE
            (* Continue allocation *);
            IF AllocateResponse.Status ==  -1 THEN
               (* Allocation request aborted due to connection failure *);
               InfoTextIndex = 11;
               ManualMode = True;
               PrgStep = 200;
            ELSIF AllocateResponse.Status == 1 THEN
               (* Candidate unit suitable and free *);
               CopyVarNoSort(AllocateResponse.UnitName, AllocatorConnection.
               UnitAllocated.UnitName, Status);
               Free:New = True;
               InfoTextIndex = 8;
               PrgStep = 100;
            ELSIF AllocateResponse.Status == 2 THEN
               (* Candidate unit suitable, but not free *);
               IF ManualModeIfNotFree THEN
                  ManualMode = True;
               ENDIF;
               (* Choose how to continue *);
               IF SpecificUnit THEN
                  (* If in manual mode wait for operator command, else try again   
                  *);
                  ManualMode = True;
                  InfoTextIndex = 5;
                  UnitListIndex = 1;
                  PrgStep = 200;
               ELSIF ManualMode AND ContinueModeIfNotFre == 1 THEN
                  (* Go back to first unit and wait for operator command   *);
                  InfoTextIndex = 2;
                  UnitListIndex = 1;
                  PrgStep = 200;
               ELSIF ManualMode AND ContinueModeIfNotFre == 2 THEN
                  (* Try with the same unit once more, but wait for operator command 
                  *);
                  InfoTextIndex = 3;
                  PrgStep = 401;
               ELSE
                  (* Get next unit *);
                  InfoTextIndex = 4;
                  PrgStep = 200;
               ENDIF;
            ELSIF AllocateResponse.Status == 3 THEN
               (* Not suitable. Get next unit *);
               IF SpecificUnit THEN
                  ManualMode = True;
                  UnitListIndex = 1;
               ENDIF;
               InfoTextIndex = 12;
               PrgStep = 200;
            ELSE
               (* Error. Undefined response from arbitrator *);
               ErrorLocal = True;
               ErrorStep = PrgStep;
               ErrorStatus = Status;
               ErrorIndex = 191;
               InfoTextIndex = 6;
               ManualMode = True;
               PrgStep = 900;
            ENDIF;
         ENDIF;
      ENDIF;
      (* Error *);
      IF PrgStep == 900 AND (ExecuteManual OR Abort OR  NOT ManualMode) THEN
         (* Reset error indications *);
         Warning = False;
         ErrorLocal = False;
         ErrorStep = 0;
         ErrorStatus = 0;
         ErrorIndex = 0;
         IF Abort THEN
            (* Abort *);
            InfoTextIndex = 7;
            Free:New = True;
            PrgStep = 100;
         ELSE
            (* Continue allocation *);
            PrgStep = 201;
         ENDIF;
         (* Reset commands *);
         ExecuteManual = False;
      ENDIF;
      (* Enable for operator to start/continue allocation *);
      EnableExecuteManual = ManualMode AND (PrgStep == 200 OR PrgStep == 401 OR 
         PrgStep == 900);
      DisableManAuto = PrgStep == 100;
      (* Enable for operator to abort allocation *);
      EnableAbort = ManualMode AND (PrgStep == 200 OR PrgStep == 401 OR PrgStep 
         == 900);
      EnableAbortThisReq = ManualMode AND PrgStep == 500;
      (* Enable yellow frame *);
      (* Reset execute of response to request *);
      AllocateResponse.Execute = False;
      (* Reset manual mode *);
      IF Free:New THEN
         ClearString(AllocateInquiry.RemoteUnitName);
      ENDIF;
      IF AllocatorConnection.Allocate.Reset THEN
         SetBooleanValue(AllocatorConnection.Allocate.Reset, False);
         ManualMode = False;
         InfoTextIndex = 0;
      ENDIF;
      ManualModeState:New = ManualMode;
      Abort = False;
      AbortThisRequest = False;
   
   ENDDEF (*UnitAllocator*);
   
   RecipeGraphDoc
   (* §Version
      §Date
      Documentation for the master modules
      is available in the general description of the library.
      
      1. Function
      
      2. Relation to other modules
      
      3. Comments on connection list
      
      4. Operators interface
      4.1 Pop-up windows
      
      4.2 Logging of operator interaction
      
      4.3 Modules accessible through pathstring
      
      5. Execution
      This module must execute in a workstation with the ScanGroup attribute Prog or system identity.
      
      The module inherits the ScanGroup from the surrounding module.
      
      6. Opsave
      
      7. Advice for usage *)
    = MODULEDEFINITION DateCode_ 371533704
   MODULEPARAMETERS
      Name "IN Module name": String  := "RecipeGraphDoc";
      RecipeDocConn "IN Connect to RecipeManagerCore or UnitSupervisorServer": 
      RecipeDocConnType ;
      EnableInteraction "IN Enable interaction": Boolean  := True;
      PrinterSystem "IN Printer system": String  := "";
      PrinterNo "IN Printer number": Integer  := 1;
      WindowsPrinter 
      "IN If true, Windows printer is assumed, page number will be e.g. 1/10 instead of only 1"
      : Boolean  := False;
      FileExtension 
      "IN Extension to the PostScript file, should be different for master/control recipes"
      : IdentString  := ".ps";
      Error "OUT Error": Boolean  := Default;
      GraphDocControl 
      "IN Commands to control the documentation from an application program": 
      GraphDocControlType  := Default;
      GraphDocStatus "OUT Status of the documentation commands": 
      GraphDocStatusType  := Default;
   LOCALVARIABLES
      ToFirst "NODE Connect to first GraphDoc module", FromLast 
      "NODE Connect to last GraphDoc module": GDConnectionType ;
      ErrorStatus "Error status", ParStepNo "No of generated parameter steps", 
      ParPageNo "No of generated parameter pages for one step", CurrentRow 
      "No of generated rows in the recipe", StatusDisplay 
      "Controls which text that should be presented in the pop-up window": 
      Integer ;
      TopOfPageFileName 
      "Filename of the text that will be included at the top of every page": 
      String  := "TopOfPage.txt";
      ExecuteTopOfPage "Start generation of the text at the top of every page", 
      TopOfPageReady "The text at the top of every page ready", 
      TopOfPageReadyOK "The text at the top of every page ready and OK", 
      MasterRecipe "True if recipe is a master recipe (not a control recipe)": 
      Boolean ;
   SUBMODULES
      RecipeGraphIcon Invocation
         ( -1.0 , -1.0 , 0.0 , 2.0 , 2.0 
          Layer_ = 1
          ) : RecipeGraphIcon (
      Error => Error);
      
      GDControl Invocation
         ( 0.6 , -0.8 , 0.0 , 0.1 , 0.1 
          Layer_ = 2
          ) : GDControl (
      EnableInteraction => EnableInteraction, 
      Error => Error, 
      ErrorStatus => ErrorStatus, 
      PrinterNo => PrinterNo, 
      PrinterSystem => PrinterSystem, 
      RecipeIsRecipe => True, 
      MasterRecipe => MasterRecipe, 
      MasterRecipeName => RecipeDocConn.Recipe.Header.MasterRecipeName, 
      ControlRecipeName => RecipeDocConn.Recipe.Header.ControlRecipeName, 
      FileExtension => FileExtension, 
      DocumenterPresent => RecipeDocConn.DocumenterPresent, 
      ExecuteDocument => RecipeDocConn.ExecuteDocument, 
      DocumentReady => RecipeDocConn.DocumentReady, 
      DocumentReadyOk => RecipeDocConn.DocumentReadyOk, 
      DisplayWindows => RecipeDocConn.DisplayWindows, 
      ParStepNo => ParStepNo, 
      ParPageNo => ParPageNo, 
      CurrentRow => CurrentRow, 
      StatusDisplay => StatusDisplay, 
      TopOfPageFileName => TopOfPageFileName, 
      ExecuteTopOfPage => ExecuteTopOfPage, 
      TopOfPageReady => TopOfPageReady, 
      TopOfPageReadyOK => TopOfPageReadyOK, 
      GraphDocControl => GraphDocControl, 
      GraphDocStatus => GraphDocStatus, 
      WindowsPrinter => WindowsPrinter);
      
      RecipeGDHeader Invocation
         ( -0.7 , 0.4 , 0.0 , 0.1 , 0.1 
          Layer_ = 2
          ) : RecipeGDHeader (
      StatusDisplay => StatusDisplay, 
      Recipe => RecipeDocConn.Recipe, 
      MasterRecipe => MasterRecipe);
      
      GDHeaderExtension Invocation
         ( -0.42 , 0.4 , 0.0 , 0.1 , 0.1 
          Layer_ = 2
          ) : GDHeaderExtension (
      StatusDisplay => StatusDisplay);
      
      D Invocation
         ( 0.42 , 1.49012E-08 , 0.0 , 0.1 , 0.1 
          Layer_ = 2
          ) : MODULEDEFINITION DateCode_ 371196928
      MODULEPARAMETERS
         Name "IN Module name": String  := "D";
         Recipe "IN Recipe": RecipeType ;
         OperationDisplay 
         "IN NODE Equipment requirement values from the current step": 
         OperationDisplayType  := Default;
      LOCALVARIABLES
         DisplayDummy "Dummy variable. Connect to HeaderExt": 
         HeaderExtDisplayType ;
         OpRecEditDummy "Dummy variable. Connect to operation module": 
         OpRecipeEditConnType ;
         OpRecRestoreDummy "Dummy variable. Connect to operation module": 
         OpRecipeRestConnType ;
      SUBMODULES
         Icon Invocation
            ( -1.0 , -1.0 , 0.0 , 2.0 , 2.0 
             Layer_ = 1
             ) : MODULEDEFINITION DateCode_ 370734128
         
         
         ModuleDef
         ClippingBounds = ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
         ZoomLimits = 0.28468 0.01
         GraphObjects :
            RectangleObject ( 0.0 , 0.0 ) ( 1.0 , 1.0 ) 
               OutlineColour : Colour0 = -3 
               FillColour : Colour0 = -2 
            TextObject ( 0.0 , 0.3 ) ( 1.0 , 0.7 ) 
               "Displays" 
               OutlineColour : Colour0 = -3 
         
         ENDDEF (*Icon*);
         
         Operation_D Invocation
            ( -0.1 , 0.2 , 0.0 , 0.1 , 0.1 
             Layer_ = 2
             ) : OperationMaster (
         OperationDisplay => OperationDisplay, 
         OpRecipeEditConn => OpRecEditDummy, 
         OpRecipeRestoreConn => OpRecRestoreDummy);
         
         HeadExt Invocation
            ( -0.1 , -0.7 , 0.0 , 0.1 , 0.1 
             Layer_ = 2
             ) : RecHeaderExt (
         Recipe => Recipe, 
         HeaderExtDisplay => DisplayDummy);
         
      
      ModuleDef
      ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
      Two_Layers_ LayerLimit_ = 0.95
      Zoomable
      GraphObjects :
         RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
            OutlineColour : Colour0 = -3 
         TextObject ( -0.3 , 0.8 ) ( 0.3 , 0.96 ) 
            "OperationDisplay" 
            ConnectionNode ( 0.0 , 1.0 ) 
            
            OutlineColour : Colour0 = -3 
         TextObject ( -1.0 , 0.32 ) ( 1.0 , 0.56 ) 
            "Name" VarName Width_ = 5 : InVar_ 5  ValueFraction = 3  
            Layer_ = 1
            OutlineColour : Colour0 = -3 
         RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
            FillColour : Colour0 = -2 
         TextObject ( -1.0 , 0.8 ) ( 1.0 , 0.96 ) 
            "Name" VarName Width_ = 5 : InVar_ 5  ValueFraction = 3  
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         TextObject ( -0.9 , -0.2 ) ( -0.9 , -0.28 ) 
            "Please put an instance of the RecHeaderExt module here. " 
            LeftAligned 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         TextObject ( -0.9 , -0.28 ) ( -0.9 , -0.36 ) 
            "Name it ""HeadExt"" and connect ""Recipe"" and ""DisplayDummy""." 
            LeftAligned 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         TextObject ( -0.9 , 0.62 ) ( -0.9 , 0.54 ) 
            
            """Operation_D"". Connect OperationDisplay  to the Operation module. " 
            LeftAligned 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         TextObject ( -0.9 , 0.7 ) ( -0.9 , 0.62 ) 
            " Put an instance of the Operation module here, and name it" 
            LeftAligned 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         TextObject ( -0.9 , 0.54 ) ( -0.9 , 0.46 ) 
            "OpRecEditDummy and OpRecRestoreDummy should also" LeftAligned 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         TextObject ( -0.9 , 0.46 ) ( -0.9 , 0.38 ) 
            "be connected." LeftAligned 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
      
      ENDDEF (*D*) (
      Recipe => RecipeDocConn.Recipe);
      
      GDTextFile Invocation
         ( -0.14 , 0.4 , 0.0 , 0.1 , 0.1 
          Layer_ = 2
          ) : GDTextFile (
      TextFile => "TextFile1.txt", 
      StatusDisplay => StatusDisplay);
      
      TopOfPageText Invocation
         ( -0.1 , 0.0 , 0.0 , 0.1 , 0.1 
          Layer_ = 2
          ) : MODULEDEFINITION DateCode_ 370734128 ( GroupConn = ScanGroup ) 
      MODULEPARAMETERS
         Name "IN Module name (= name of report)": String  := "TopOfPageText";
         FileName "IN Name of the local file containing the report": String  := 
         "TopOfPage.txt";
         Recipe "IN Recipe": RecipeType  := Default;
         MasterRecipe "IN Should be true if the Recipe is a master recipe": 
         Boolean  := Default;
         Execute "IN Generate a report": Boolean  := Default;
         Ready "OUT Generation ready": Boolean  := Default;
         ReadyOK "OUT Report succesfully generated": Boolean  := Default;
         ScanGroup "IN Scan group for this module": GroupData  := Default;
      LOCALVARIABLES
         R "Common data for line and field modules.": ReportCommon ;
         FirstLine "Used by library modules.", LastLine 
         "Used by library modules.", HeaderFirstLine "Used by library modules."
         , HeaderEndLine "Used by library modules.": LineConnection ;
         ExecuteState "Used by library modules.": Boolean State;
         PageLength "No. of lines per page": Integer  := 64;
         PageWidth "No. of characters per line.": Integer  := 80;
         EnableSpreadSheet "If true, use line and field delimiters": boolean  
         := False;
         LineDelimiter "Line delimiter for spreadsheet files", FieldDelimiter 
         "Field delimiter for spreadsheet files", StringDelimiter 
         "Inserted before and after strings in spreadsheets": Identstring  := 
         "";
         Append "Append to existing file", TrailingFormFeed 
         "If true then a formfeed is added after the report text", 
         LeadingFormFeed 
         "If true then a formfeed is inserted before  the report text": Boolean  
         := False;
         Fontsize "Fontsize in window when inspecting files": Integer  := 15;
         ControlRecipeWidth "Width of string if the recipe is a control recipe"
         , MasterRecipeWidth "Width of string if the recipe is a master recipe"
         : Integer  := 30;
         OldExecute "Used for edge detection", EnableMaster 
         "Enables master recipe reportstrings", EnableControl 
         "Enables control recipe reportstrings": Boolean ;
      SUBMODULES
         ReportMasterIcon Invocation
            ( -1.0 , -1.0 , 0.0 , 2.0 , 2.0 
             Layer_ = 1
             ZoomLimits = 0.42568 0.01 ) : ReportMasterIcon (
         Error => R.error);
         
         Line2 Invocation
            ( -0.94 , 0.58 , 0.0 , 0.66 , 0.66666 
             Layer_ = 2
             ) : ReportLine (
         ReportControl => R);
         
         Line1 Invocation
            ( -0.94 , 0.66 , 0.0 , 0.66 , 0.66666 
             Layer_ = 2
             ) : ReportLine (
         ReportControl => R);
         
         Line3 Invocation
            ( -0.94 , 0.5 , 0.0 , 0.66 , 0.66666 
             Layer_ = 2
             ) : ReportLine (
         ReportControl => R);
         
         Line4 Invocation
            ( -0.94 , 0.42 , 0.0 , 0.66 , 0.66666 
             Layer_ = 2
             ) : ReportLine (
         ReportControl => R);
         
         Line5 Invocation
            ( -0.94 , 0.34 , 0.0 , 0.66 , 0.66666 
             Layer_ = 2
             ) : ReportLine (
         ReportControl => R);
         
         Line6 Invocation
            ( -0.94 , 0.26 , 0.0 , 0.66 , 0.66666 
             Layer_ = 2
             ) : ReportLine (
         ReportControl => R);
         
         Line0 Invocation
            ( -0.94 , 0.86 , 0.0 , 0.66 , 0.66666 
             Layer_ = 2
             ) : ReportLine (
         ReportControl => R);
         
         AuthorString Invocation
            ( -0.8 , 0.66 , 0.0 , 0.2 , 0.025 
             Layer_ = 2
             ) : ReportString (
         Value => "$_AUTHOR", 
         Width => 30, 
         LeadingSpaces => 5, 
         Left => True, 
         ReportControl => R);
         
         DateString Invocation
            ( -0.8 , 0.58 , 0.0 , 0.2 , 0.025 
             Layer_ = 2
             ) : ReportString (
         Value => "$_RECIPE_DATE", 
         Width => 30, 
         LeadingSpaces => 5, 
         Left => True, 
         ReportControl => R);
         
         ProdDescrString Invocation
            ( -0.8 , 0.5 , 0.0 , 0.2 , 0.025 
             Layer_ = 2
             ) : ReportString (
         Value => "$_PRODUCT_DESCRIPTION", 
         Width => 30, 
         LeadingSpaces => 5, 
         Left => True, 
         ReportControl => R);
         
         ProductCodeString Invocation
            ( -0.8 , 0.42 , 0.0 , 0.2 , 0.025 
             Layer_ = 2
             ) : ReportString (
         Value => "$_PRODUCT_CODE", 
         Width => 30, 
         LeadingSpaces => 5, 
         Left => True, 
         ReportControl => R);
         
         BatchIDString Invocation
            ( -0.8 , 0.34 , 0.0 , 0.2 , 0.025 
             Layer_ = 2
             Enable_ = True : InVar_ "EnableControl" ) : ReportString (
         Value => "$_BATCH_ID", 
         Width => 30, 
         LeadingSpaces => 5, 
         Left => True, 
         EnableModule => EnableControl, 
         ReportControl => R);
         
         MasterAuthor Invocation
            ( -0.08 , 0.66 , 0.0 , 0.2 , 0.025 
             Layer_ = 2
             ) : ReportString (
         Value => Recipe.Header.MasterRecipeAuthor, 
         Width => MasterRecipeWidth, 
         Left => True, 
         EnableModule => EnableMaster, 
         ReportControl => R);
         
         ControlAuthor Invocation
            ( 0.4 , 0.66 , 0.0 , 0.2 , 0.025 
             Layer_ = 2
             ) : ReportString (
         Value => Recipe.Header.ControlRecipeAuthor, 
         Width => ControlRecipeWidth, 
         Left => True, 
         EnableModule => EnableControl, 
         ReportControl => R);
         
         MasterDate Invocation
            ( -0.08 , 0.58 , 0.0 , 0.2 , 0.025 
             Layer_ = 2
             ) : ReportTime (
         Value => Recipe.Header.MasterRecipeDate, 
         Width => MasterRecipeWidth, 
         Left => True, 
         EnableModule => EnableMaster, 
         ReportControl => R);
         
         ControlDate Invocation
            ( 0.4 , 0.58 , 0.0 , 0.2 , 0.025 
             Layer_ = 2
             ) : ReportTime (
         Value => Recipe.Header.ControlRecipeDate, 
         Width => ControlRecipeWidth, 
         Left => True, 
         EnableModule => EnableControl, 
         ReportControl => R);
         
         ProductDescription Invocation
            ( -0.08 , 0.5 , 0.0 , 0.2 , 0.025 
             Layer_ = 2
             ) : ReportString (
         Value => Recipe.Header.ProductDescription, 
         Width => 40, 
         Left => True, 
         ReportControl => R);
         
         ProductCode Invocation
            ( -0.08 , 0.42 , 0.0 , 0.2 , 0.025 
             Layer_ = 2
             ) : ReportString (
         Value => Recipe.Header.ProductCode, 
         Width => 40, 
         Left => True, 
         ReportControl => R);
         
         BatchID Invocation
            ( -0.08 , 0.34 , 0.0 , 0.2 , 0.025 
             Layer_ = 2
             ) : ReportString (
         Value => Recipe.Header.BatchIdentification, 
         Width => 40, 
         Left => True, 
         EnableModule => EnableControl, 
         ReportControl => R);
         
         Colon1 Invocation
            ( -0.3 , 0.66 , 0.0 , 0.06 , 0.025 
             Layer_ = 2
             ) : ReportString (
         Value => " : ", 
         Width => 3, 
         Left => True, 
         ReportControl => R);
         
         Colon2 Invocation
            ( -0.3 , 0.58 , 0.0 , 0.06 , 0.025 
             Layer_ = 2
             ) : ReportString (
         Value => " : ", 
         Width => 3, 
         Left => True, 
         ReportControl => R);
         
         Colon3 Invocation
            ( -0.3 , 0.5 , 0.0 , 0.06 , 0.025 
             Layer_ = 2
             ) : ReportString (
         Value => " : ", 
         Width => 3, 
         Left => True, 
         ReportControl => R);
         
         Colon4 Invocation
            ( -0.3 , 0.42 , 0.0 , 0.06 , 0.025 
             Layer_ = 2
             ) : ReportString (
         Value => " : ", 
         Width => 3, 
         Left => True, 
         ReportControl => R);
         
         Colon5 Invocation
            ( -0.3 , 0.34 , 0.0 , 0.06 , 0.025 
             Layer_ = 2
             ) : ReportString (
         Value => " : ", 
         Width => 3, 
         Left => True, 
         EnableModule => EnableControl, 
         ReportControl => R);
         
         HideInOperate Invocation
            ( 0.74 , -0.94 , 0.0 , 0.22 , 0.22666 
             Layer_ = 2
             Enable_ = True : InVar_ False ) : MODULEDEFINITION DateCode_ 
         370734751 ( Frame_Module ) 
         SUBMODULES
            Pres Invocation
               ( -0.96429 , -0.25 , 0.0 , 1.99234 , 1.99234 
                ) : ReportPres (
            Name => name, 
            Filename => filename, 
            R => r, 
            Fontsize => Fontsize, 
            Execute => execute, 
            Ready => ready);
            
         
         ModuleDef
         ClippingBounds = ( -1.0 , -0.28571 ) ( 0.48 , 0.28 )
         
         ENDDEF (*HideInOperate*);
         
         Code Invocation
            ( 0.94 , -0.94 , 0.0 , 0.06 , 0.06 
             Layer_ = 2
             ) : ReportMasterCode (
         R => R, 
         FirstLine => FirstLine, 
         LastLine => LastLine, 
         HeaderFirstLine => HeaderFirstLine, 
         HeaderEndLine => HeaderEndLine, 
         FileName => FileName, 
         PageLength => PageLength, 
         PageWidth => PageWidth, 
         EnableSpreadSheet => EnableSpreadSheet, 
         LineDelimiter => LineDelimiter, 
         FieldDelimiter => FieldDelimiter, 
         StringDelimiter => StringDelimiter, 
         Append => Append, 
         TrailingFormFeed => TrailingFormFeed, 
         LeadingFormFeed => LeadingFormFeed, 
         Execute => Execute, 
         Ready => Ready, 
         ReadyOK => ReadyOK);
         
      
      ModuleDef
      ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
      Two_Layers_ LayerLimit_ = 0.95
      Zoomable
      GraphObjects :
         RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
            OutlineColour : Colour0 = -3 
         RectangleObject ( -1.0 , -1.0 ) ( 0.99998 , 0.99998 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
            FillColour : Colour0 = -2 
         TextObject ( -0.9 , 0.74 ) ( -0.8 , 0.76 ) 
            "FirstLine" 
            ConnectionNode ( -0.94 , 0.76 ) 
            LeftAligned 
            Layer_ = 2
            Enable_ = True : InVar_ False 
            OutlineColour : Colour0 = -3 
         TextObject ( -0.98 , -0.98 ) ( -0.88 , -0.96 ) 
            "LastLine" 
            ConnectionNode ( -0.94 , -0.92 ) 
            
            Layer_ = 2
            Enable_ = True : InVar_ False 
            OutlineColour : Colour0 = -3 
         LineObject ( 0.19999 , 0.98665 ) ( 0.19999 , -1.01333 ) 
            Layer_ = 2
            Enable_ = True : InVar_ False 
            OutlineColour : Colour0 = -3 ColourStyle = 75.0 
         LineObject ( -0.86667 , 0.99998 ) ( -0.86667 , -1.0 ) 
            Layer_ = 2
            Enable_ = True : InVar_ False 
            OutlineColour : Colour0 = -3 ColourStyle = 75.0 
         LineObject ( 0.89331 , 0.99998 ) ( 0.89331 , -1.0 ) 
            Layer_ = 2
            Enable_ = True : InVar_ False 
            OutlineColour : Colour0 = -3 ColourStyle = 75.0 
         PolygonObject Polyline Connection ( -0.94 , 0.58 ) 
            ( -0.94 , 0.553333 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( -0.94 , 0.5 ) 
            ( -0.94 , 0.473333 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( -0.94 , 0.42 ) 
            ( -0.94 , 0.393333 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( -0.94 , 0.26 ) 
            ( -0.94 , -0.92 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         TextObject ( -0.9 , 0.82 ) ( -0.72 , 0.8 ) 
            "HeaderEndLine" 
            ConnectionNode ( -0.94 , 0.8 ) 
            LeftAligned 
            Layer_ = 2
            Enable_ = True : InVar_ False 
            OutlineColour : Colour0 = -3 
         TextObject ( -0.9 , 0.98 ) ( -0.72 , 0.96 ) 
            "HeaderFirstLine" 
            ConnectionNode ( -0.94 , 0.98 ) 
            LeftAligned 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( -0.94 , 0.76 ) 
            ( -0.94 , 0.713333 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( -0.94 , 0.66 ) 
            ( -0.94 , 0.633333 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         TextObject ( -0.62 , 0.94 ) ( -0.1 , 1.0 ) 
            "Header" 
            Layer_ = 2
            Enable_ = True : InVar_ False 
            OutlineColour : Colour0 = -3 
         TextObject ( -0.62 , 0.74 ) ( -0.1 , 0.8 ) 
            "Page" 
            Layer_ = 2
            Enable_ = True : InVar_ False 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.2 , 0.82 ) ( 0.2 , 0.76 ) 
            "80" RightAligned 
            Layer_ = 2
            Enable_ = True : InVar_ False 
            OutlineColour : Colour0 = 31 
         TextObject ( 0.9 , 0.82 ) ( 0.9 , 0.76 ) 
            "132" RightAligned 
            Layer_ = 2
            Enable_ = True : InVar_ False 
            OutlineColour : Colour0 = 31 
         PolygonObject Polyline Connection ( -0.874 , 0.286666 ) 
            ( 0.8684 , 0.286666 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( -0.94 , 0.86 ) 
            ( -0.94 , 0.8 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
            FillColour : Colour0 = 41 
         PolygonObject Polyline Connection ( -0.874 , 0.886666 ) 
            ( 0.8684 , 0.886666 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
            FillColour : Colour0 = 41 
         LineObject ( 0.19999 , 0.79998 ) ( 0.19999 , -0.8 ) 
            Layer_ = 2
            Enable_ = True : InVar_ False 
            OutlineColour : Colour0 = 31 
         PolygonObject Polyline Connection ( -0.94 , 0.913333 ) 
            ( -0.94 , 0.98 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( -0.94 , 0.34 ) 
            ( -0.94 , 0.313333 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         TextObject ( -0.8 , 0.1 ) ( 0.7 , 0.2 ) 
            "Please do not use more than six lines for the pagetop text !" 
            LeftAligned 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( -0.874 , 0.686666 ) 
            ( -0.8 , 0.685 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( -0.4 , 0.685 ) 
            ( -0.3 , 0.685 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( -0.874 , 0.606666 ) 
            ( -0.8 , 0.605 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( -0.4 , 0.605 ) 
            ( -0.3 , 0.605 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( -0.874 , 0.526666 ) 
            ( -0.8 , 0.525 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( -0.4 , 0.525 ) 
            ( -0.3 , 0.525 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( -0.18 , 0.525 ) 
            ( -0.0799999 , 0.525 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( -0.874 , 0.446666 ) 
            ( -0.8 , 0.445 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( -0.4 , 0.445 ) 
            ( -0.3 , 0.445 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( -0.18 , 0.445 ) 
            ( -0.0799999 , 0.445 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( 0.32 , 0.525 ) 
            ( 0.8684 , 0.526666 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( 0.32 , 0.445 ) 
            ( 0.8684 , 0.446666 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( -0.18 , 0.685 ) 
            ( -0.0799999 , 0.685 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( 0.32 , 0.685 ) 
            ( 0.4 , 0.685 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( 0.8 , 0.685 ) 
            ( 0.8684 , 0.686666 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( -0.18 , 0.605 ) 
            ( -0.08 , 0.605 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( 0.32 , 0.605 ) 
            ( 0.4 , 0.605 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( 0.8 , 0.605 ) 
            ( 0.8684 , 0.606666 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( -0.4 , 0.365 ) 
            ( -0.3 , 0.365 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( -0.18 , 0.365 ) 
            ( -0.0799999 , 0.365 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( 0.32 , 0.365 ) 
            ( 0.8684 , 0.366666 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( -0.874 , 0.366666 ) 
            ( -0.8 , 0.365 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
      
      ModuleCode
      EQUATIONBLOCK WidthCalculation COORD -0.38, -0.42 OBJSIZE 0.3, 0.1
      Layer_ = 2 :
         IF Execute AND  NOT OldExecute THEN
            (* POSITIVE EDGE OF EXECUTE *);
            IF MasterRecipe THEN
               (* ENABLE THE MASTER RECIPE REPORTSTRINGS *);
               MasterRecipeWidth = 40;
               EnableMaster = True;
               ControlRecipeWidth = 0;
               EnableControl = False;
            ELSE
               (* ENABLE THE CONTROL RECIPE REPORTSTRINGS *);
               MasterRecipeWidth = 0;
               EnableMaster = False;
               ControlRecipeWidth = 40;
               EnableControl = True;
            ENDIF;
         ENDIF;
         (*  *);
         OldExecute = Execute;
      
      ENDDEF (*TopOfPageText*) (
      FileName => TopOfPageFileName, 
      Recipe => RecipeDocConn.Recipe, 
      MasterRecipe => MasterRecipe, 
      Execute => ExecuteTopOfPage, 
      Ready => TopOfPageReady, 
      ReadyOK => TopOfPageReadyOK);
      
      RecipeGDSteps Invocation
         ( 0.14 , 0.4 , 0.0 , 0.1 , 0.1 
          Layer_ = 2
          ) : RecipeGDSteps (
      Recipe => RecipeDocConn.Recipe, 
      RecipeRow => CurrentRow, 
      StatusDisplay => StatusDisplay);
      
      RecipeGDStepPar Invocation
         ( 0.42 , 0.4 , 0.0 , 0.1 , 0.1 
          Layer_ = 2
          ) : RecipeGDStepPar (
      Recipe => RecipeDocConn.Recipe, 
      ParStepNo => ParStepNo, 
      ParPageNo => ParPageNo, 
      StatusDisplay => StatusDisplay);
      
      GDLastPage Invocation
         ( 0.7 , 0.4 , 0.0 , 0.1 , 0.1 
          Layer_ = 2
          ) : GDLastPage (
      StatusDisplay => StatusDisplay);
      
   
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   Two_Layers_ LayerLimit_ = 0.95
   Zoomable
   GraphObjects :
      RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = -2 
      TextObject ( -1.0 , 0.72 ) ( 0.0 , 0.84 ) 
         "ErrorStatus:" LeftAligned 
         Layer_ = 2
         OutlineColour : Colour0 = 5 Colour1 = 12 ColourStyle = False : InVar_ 
         "Error" 
      TextObject ( 0.0 , 0.72 ) ( 1.0 , 0.84 ) 
         "ErrorStatus" VarName Width_ = 5 : InVar_ 5  ValueFraction = 2  
         Layer_ = 2
         OutlineColour : Colour0 = 5 Colour1 = 12 ColourStyle = False : InVar_ 
         "Error" 
      TextObject ( -0.72 , 0.6 ) ( -1.0 , 0.54 ) 
         "ToFirst" 
         ConnectionNode ( -0.9 , 0.4 ) 
         LeftAligned 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      TextObject ( 1.0 , 0.6 ) ( 0.74 , 0.54 ) 
         "FromLast" 
         ConnectionNode ( 0.9 , 0.4 ) 
         LeftAligned 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      TextObject ( -1.0 , 0.84 ) ( 1.0 , 1.0 ) 
         "Name" VarName Width_ = 5 : InVar_ 5  ValueFraction = 3  
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.9 , 0.4 ) 
         ( -0.8 , 0.4 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.6 , 0.4 ) 
         ( -0.52 , 0.4 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.32 , 0.4 ) 
         ( -0.24 , 0.4 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.04 , 0.4 ) 
         ( 0.04 , 0.4 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( 0.8 , 0.4 ) 
         ( 0.9 , 0.4 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( 0.24 , 0.4 ) 
         ( 0.32 , 0.4 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( 0.52 , 0.4 ) 
         ( 0.6 , 0.4 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( 0.42 , 0.3 ) 
         ( 0.42 , 0.1 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.9 , 0.4 ) 
         ( -0.9 , -0.8 ) ( 0.5 , -0.8 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( 0.9 , 0.4 ) 
         ( 0.9 , -0.8 ) ( 0.7 , -0.8 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
   
   ENDDEF (*RecipeGraphDoc*);
   
   OpRecGraphDoc
   (* §Version
      §Date
      Documentation for the master modules
      is available in the general description of the library.
      
      1. Function
      
      2. Relation to other modules
      
      3. Comments on connection list
      
      4. Operators interface
      4.1 Pop-up windows
      
      4.2 Logging of operator interaction
      
      4.3 Modules accessible through pathstring
      
      5. Execution
      This module must execute in a workstation with the ScanGroup attribute Prog or system identity.
      
      The module inherits the ScanGroup from the surrounding module.
      
      6. Opsave
      
      7. Advice for usage *)
    = MODULEDEFINITION DateCode_ 372141307
   MODULEPARAMETERS
      Name "IN Module name": String  := "OpRecGraphDoc";
      OpRecipeDocConn "IN Connect to RecipeManagerCore or UnitSupervisorServer"
      : OpRecipeDocConnType ;
      EnableInteraction "IN Enable interaction": Boolean  := True;
      PrinterSystem "IN Printer system": String  := "";
      PrinterNo "IN Printer number": Integer  := 1;
      WindowsPrinter 
      "IN If true, Windows printer is assumed, page number will be e.g. 1/10 instead of only 1"
      : Boolean  := False;
      FileExtension 
      "IN Extension to the PostScript file, should be different for master/control recipes"
      : IdentString  := ".ps";
      Error "OUT Error": Boolean  := Default;
      GraphDocControl 
      "IN Commands to control the documentation from an application program": 
      GraphDocControlType  := Default;
      GraphDocStatus "OUT Status of the documentation commands": 
      GraphDocStatusType  := Default;
   LOCALVARIABLES
      ToFirst "NODE Connect to first GraphDoc module", FromLast 
      "NODE Connect to last GraphDoc module": GDConnectionType ;
      ErrorStatus "Error status", ParStepNo "No of generated parameter steps", 
      ParPageNo "No of generated parameter pages for one step", CurrentRow 
      "No of generated rows in the oprecipe", StatusDisplay 
      "Conrols which text that should be presented in the popup window": 
      Integer ;
      TopOfPageFileName 
      "Filename of the text that will be included at the top of every page": 
      String  := "OpTopOfPage.txt";
      ExecuteTopOfPage "Start generation of the text at the top of every page", 
      TopOfPageReady "The text at the top of every page ready", 
      TopOfPageReadyOK "The text at the top of every page ready and OK", 
      MasterRecipe 
      "True if operation recipe is a master recipe (not a control recipe)": 
      Boolean ;
   SUBMODULES
      RecipeGraphIcon Invocation
         ( -1.0 , -1.0 , 0.0 , 2.0 , 2.0 
          Layer_ = 1
          ) : RecipeGraphIcon (
      Error => Error);
      
      GDControl Invocation
         ( 0.6 , -0.8 , 0.0 , 0.1 , 0.1 
          Layer_ = 2
          ) : GDControl (
      EnableInteraction => EnableInteraction, 
      Error => Error, 
      ErrorStatus => ErrorStatus, 
      PrinterNo => PrinterNo, 
      PrinterSystem => PrinterSystem, 
      RecipeIsRecipe => False, 
      MasterRecipe => MasterRecipe, 
      MasterRecipeName => OpRecipeDocConn.OperationRecipe.Header.
      MasterRecipeName, 
      ControlRecipeName => OpRecipeDocConn.OperationRecipe.Header.
      ControlRecipeName, 
      FileExtension => FileExtension, 
      DocumenterPresent => OpRecipeDocConn.DocumenterPresent, 
      ExecuteDocument => OpRecipeDocConn.ExecuteDocument, 
      DocumentReady => OpRecipeDocConn.DocumentReady, 
      DocumentReadyOk => OpRecipeDocConn.DocumentReadyOk, 
      DisplayWindows => OpRecipeDocConn.DisplayWindows, 
      ParStepNo => ParStepNo, 
      ParPageNo => ParPageNo, 
      CurrentRow => CurrentRow, 
      StatusDisplay => StatusDisplay, 
      TopOfPageFileName => TopOfPageFileName, 
      ExecuteTopOfPage => ExecuteTopOfPage, 
      TopOfPageReady => TopOfPageReady, 
      TopOfPageReadyOK => TopOfPageReadyOK, 
      GraphDocControl => GraphDocControl, 
      GraphDocStatus => GraphDocStatus, 
      WindowsPrinter => WindowsPrinter);
      
      OpRecipeGDHeader Invocation
         ( -0.72 , 0.4 , 0.0 , 0.1 , 0.1 
          Layer_ = 2
          ) : OpRecipeGDHeader (
      StatusDisplay => StatusDisplay, 
      OperationRecipe => OpRecipeDocConn.OperationRecipe, 
      MasterRecipe => MasterRecipe);
      
      OpRecipeGDSteps Invocation
         ( 0.16 , 0.4 , 0.0 , 0.1 , 0.1 
          Layer_ = 2
          ) : OpRecipeGDSteps (
      OperationRecipe => OpRecipeDocConn.OperationRecipe, 
      OpRecipeRow => CurrentRow, 
      StatusDisplay => StatusDisplay);
      
      OpRecipeGDStepPar Invocation
         ( 0.44 , 0.4 , 0.0 , 0.1 , 0.1 
          Layer_ = 2
          ) : OpRecipeGDStepPar (
      OperationRecipe => OpRecipeDocConn.OperationRecipe, 
      ParStepNo => ParStepNo, 
      ParPageNo => ParPageNo, 
      StatusDisplay => StatusDisplay);
      
      GDLastPage Invocation
         ( 0.72 , 0.4 , 0.0 , 0.1 , 0.1 
          Layer_ = 2
          ) : GDLastPage (
      StatusDisplay => StatusDisplay);
      
      D Invocation
         ( 0.44 , 0.0 , 0.0 , 0.1 , 0.1 
          Layer_ = 2
          ) : MODULEDEFINITION DateCode_ 144432785
      MODULEPARAMETERS
         Name "IN Module name": String  := "D";
         OperationRecipe "IN Operation recipe": OperationRecipeType ;
         Formula1 "IN NODE Formula1 values from the current step": 
         Formula1DisplayType ;
         Formula2 "IN NODE Formula2 values from the current step": 
         Formula2DisplayType ;
         Formula3 "IN NODE Formula3 values from the current step": 
         Formula3DisplayType ;
      LOCALVARIABLES
         DisplayDummy "Dummy variable. Connect to HeaderExt": 
         HeaderExtDisplayType ;
      SUBMODULES
         Icon Invocation
            ( -1.0 , -1.0 , 0.0 , 2.0 , 2.0 
             Layer_ = 1
             ) : MODULEDEFINITION DateCode_ 370817521
         
         
         ModuleDef
         ClippingBounds = ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
         ZoomLimits = 0.28468 0.01
         GraphObjects :
            RectangleObject ( 0.0 , 0.0 ) ( 1.0 , 1.0 ) 
               OutlineColour : Colour0 = -3 
               FillColour : Colour0 = -2 
            TextObject ( 0.0 , 0.3 ) ( 1.0 , 0.7 ) 
               "Displays" 
               OutlineColour : Colour0 = -3 
         
         ENDDEF (*Icon*);
         
         Agitation1_D Invocation
            ( -0.3 , 0.3 , 0.0 , 0.1 , 0.1 
             Layer_ = 2
             ) : Agitation1Display (
         FormulaDisplay => Formula1);
         
         Heating_D Invocation
            ( 0.0 , 0.3 , 0.0 , 0.1 , 0.1 
             Layer_ = 2
             ) : HeaterDisplay (
         FormulaDisplay => Formula1);
         
         Ramping_D Invocation
            ( 0.0 , 0.0 , 0.0 , 0.1 , 0.1 
             Layer_ = 2
             ) : RampingDisplay (
         FormulaDisplay => Formula2);
         
         Agitation2_D Invocation
            ( -0.3 , 0.0 , 0.0 , 0.1 , 0.1 
             Layer_ = 2
             ) : Agitation2Display (
         FormulaDisplay => Formula2);
         
         Filling_D Invocation
            ( -0.3 , -0.3 , 0.0 , 0.1 , 0.1 
             Layer_ = 2
             ) : FillingDisplay (
         FormulaDisplay => Formula3);
         
         HeadExt Invocation
            ( -0.1 , -0.8 , 0.0 , 0.1 , 0.1 
             Layer_ = 2
             ) : OpRecHeaderExt (
         OperationRecipe => OperationRecipe, 
         HeaderExtDisplay => DisplayDummy);
         
         Dummy_D Invocation
            ( 0.76 , -0.14 , 0.0 , 0.1 , 0.1 
             Layer_ = 2
             ) : MODULEDEFINITION DateCode_ 371997216
         MODULEPARAMETERS
            Name "IN Module name": string  := "Empty dummy";
         SUBMODULES
            Icon Invocation
               ( -1.0 , -1.0 , 0.0 , 2.0 , 2.0 
                Layer_ = 1
                ) : MODULEDEFINITION DateCode_ 371997216
            
            
            ModuleDef
            ClippingBounds = ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
            GraphObjects :
               RectangleObject ( 0.0 , 0.0 ) ( 1.0 , 1.0 ) 
                  OutlineColour : Colour0 = -3 
                  FillColour : Colour0 = -2 
               TextObject ( 0.0 , 0.3 ) ( 1.0 , 0.7 ) 
                  "Dummy" 
                  OutlineColour : Colour0 = -3 
            
            ENDDEF (*Icon*);
            
            Page1 Invocation
               ( -0.8 , -0.6 , 0.0 , 1.2 , 1.2 
                Layer_ = 2
                ) : MODULEDEFINITION DateCode_ 371997216 ( Frame_Module ) 
            
            
            ModuleDef
            ClippingBounds = ( -2.98023E-08 , 0.0 ) 
            ( 1.0 , 1.1 )
            GraphObjects :
               TextObject ( 0.1 , 1.0 ) ( 0.9 , 0.92 ) 
                  "Dummy step" LeftAligned 
                  OutlineColour : Colour0 = -3 
            
            ENDDEF (*Page1*);
            
         
         ModuleDef
         ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
         Two_Layers_ LayerLimit_ = 0.95
         Zoomable
         GraphObjects :
            RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
               Layer_ = 2
               OutlineColour : Colour0 = -3 
               FillColour : Colour0 = -2 
            TextObject ( -1.0 , 0.8 ) ( 1.0 , 0.96 ) 
               "Name" VarName Width_ = 5 : InVar_ 5  ValueFraction = 3  
               Layer_ = 2
               OutlineColour : Colour0 = -3 
         InteractObjects :
            ProcedureInteract ( -0.8 , -0.8 ) ( 0.8 , 0.8 ) 
               ToggleWindow
               "" : InVar_ LitString "+Info" "" : InVar_ "Name" False : InVar_ 
               True 0.0 : InVar_ 0.1 0.0 : InVar_ -0.1 0.0 : InVar_ 0.24 0.0 
               False 0 0 False 0 
               Layer_ = 1
               Variable = 0.0 
         
         ENDDEF (*Dummy_D*);
         
      
      ModuleDef
      ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
      Two_Layers_ LayerLimit_ = 0.95
      Zoomable
      GraphObjects :
         RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
            OutlineColour : Colour0 = -3 
         TextObject ( -0.3 , 0.8 ) ( 0.3 , 0.96 ) 
            "Formula2" 
            ConnectionNode ( 0.0 , 1.0 ) 
            
            OutlineColour : Colour0 = -3 
         TextObject ( 0.4 , 0.8 ) ( 1.0 , 0.96 ) 
            "Formula3" 
            ConnectionNode ( 0.5 , 1.0 ) 
            
            OutlineColour : Colour0 = -3 
         TextObject ( -1.0 , 0.8 ) ( -0.4 , 0.96 ) 
            "Formula1" 
            ConnectionNode ( -0.5 , 1.0 ) 
            
            OutlineColour : Colour0 = -3 
         TextObject ( -1.0 , 0.32 ) ( 1.0 , 0.56 ) 
            "Name" VarName Width_ = 5 : InVar_ 5  ValueFraction = 3  
            Layer_ = 1
            OutlineColour : Colour0 = -3 
         RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
            FillColour : Colour0 = -2 
         TextObject ( -1.0 , 0.8 ) ( 1.0 , 0.96 ) 
            "Name" VarName Width_ = 5 : InVar_ 5  ValueFraction = 3  
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         TextObject ( -0.9 , -0.5 ) ( -0.9 , -0.58 ) 
            "Please put an instance of the OpRecHeaderExt module here. " 
            LeftAligned 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         TextObject ( -0.9 , 0.78 ) ( -0.9 , 0.7 ) 
            "Please put an instance of every phase display module here. " 
            LeftAligned 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         TextObject ( -0.9 , 0.7 ) ( -0.9 , 0.62 ) 
            "Name the modules <phasename>_D (for example Heat_D). " LeftAligned 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         TextObject ( -0.9 , -0.58 ) ( -0.9 , -0.66 ) 
            
            "Name it ""HeadExt"" and connect ""OperationRecipe"" and ""DisplayDummy""." 
            LeftAligned 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         TextObject ( -0.9 , 0.62 ) ( -0.9 , 0.54 ) 
            "Connect formula values  to the PhaseDisplay modules." LeftAligned 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         TextObject ( -0.9 , 0.26 ) ( -0.5 , 0.36 ) 
            "Formula1:" LeftAligned 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         TextObject ( -0.9 , -0.04 ) ( -0.5 , 0.06 ) 
            "Formula2:" LeftAligned 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         TextObject ( -0.9 , -0.34 ) ( -0.5 , -0.24 ) 
            "Formula3:" LeftAligned 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         TextObject ( -0.44 , 0.14 ) ( -0.16 , 0.2 ) 
            "Agitation1_D" LeftAligned 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         TextObject ( -0.14 , 0.14 ) ( 0.14 , 0.2 ) 
            "Heating_D" LeftAligned 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         TextObject ( 0.6 , -0.3 ) ( 0.88 , -0.24 ) 
            "Dummy_D" LeftAligned 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         TextObject ( -0.14 , -0.16 ) ( 0.14 , -0.1 ) 
            "Ramping_D" LeftAligned 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         TextObject ( -0.44 , -0.16 ) ( -0.16 , -0.1 ) 
            "Agitation2_D" LeftAligned 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         TextObject ( -0.44 , -0.46 ) ( -0.16 , -0.4 ) 
            "Filling_D" LeftAligned 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
      
      ENDDEF (*D*) (
      OperationRecipe => OpRecipeDocConn.OperationRecipe);
      
      GDTextFile Invocation
         ( -0.14 , 0.4 , 0.0 , 0.1 , 0.1 
          Layer_ = 2
          ) : GDTextFile (
      TextFile => "TextFile1.txt", 
      StatusDisplay => StatusDisplay);
      
      GDHeaderExtension Invocation
         ( -0.44 , 0.4 , 0.0 , 0.1 , 0.1 
          Layer_ = 2
          ) : GDHeaderExtension (
      StatusDisplay => StatusDisplay);
      
      OpTopOfPageText Invocation
         ( -0.1 , 3.72529E-09 , 0.0 , 0.1 , 0.1 
          Layer_ = 2
          ) : MODULEDEFINITION DateCode_ 370817521 ( GroupConn = ScanGroup ) 
      MODULEPARAMETERS
         Name "IN Module name (= name of report)": String  := "OpTopOfPageText"
         ;
         FileName "IN Name of the local file containing the report": String  := 
         "OpTopOfPage.txt";
         OpRecipe "IN Operation recipe": OperationRecipeType  := Default;
         MasterRecipe "IN Should be true if the OpRecipe is a master recipe": 
         Boolean  := Default;
         Execute "IN Generate a report": Boolean  := Default;
         Ready "OUT Generation ready": Boolean  := Default;
         ReadyOK "OUT Report succesfully generated": Boolean  := Default;
         ScanGroup "IN Scan group for this module": GroupData  := Default;
      LOCALVARIABLES
         R "Common data for line and field modules.": ReportCommon ;
         FirstLine "Used by library modules.", LastLine 
         "Used by library modules.", HeaderFirstLine "Used by library modules."
         , HeaderEndLine "Used by library modules.": LineConnection ;
         ExecuteState "Used by library modules.": Boolean State;
         PageLength "No. of lines per page": Integer  := 64;
         PageWidth "No. of characters per line.": Integer  := 80;
         EnableSpreadSheet "If true, use line and field delimiters": boolean  
         := False;
         LineDelimiter "Line delimiter for spreadsheet files", FieldDelimiter 
         "Field delimiter for spreadsheet files", StringDelimiter 
         "Inserted before and after strings in spreadsheets": Identstring  := 
         "";
         Append "Append to existing file", TrailingFormFeed 
         "If true then a formfeed is added after the report text", 
         LeadingFormFeed 
         "If true then a formfeed is inserted before  the report text": Boolean  
         := False;
         Fontsize "Fontsize in window when inspecting files": Integer  := 15;
         ControlRecipeWidth "Width of string if the recipe is a control recipe"
         , MasterRecipeWidth "Width of string if the recipe is a master recipe"
         : Integer  := 30;
         OldExecute "Used for edge detection", EnableMaster 
         "Enables master recipe reportstrings", EnableControl 
         "Enables control recipe reportstrings": Boolean ;
      SUBMODULES
         ReportMasterIcon Invocation
            ( -1.0 , -1.0 , 0.0 , 2.0 , 2.0 
             Layer_ = 1
             ZoomLimits = 0.42568 0.01 ) : ReportMasterIcon (
         Error => R.error);
         
         Line2 Invocation
            ( -0.94 , 0.58 , 0.0 , 0.66 , 0.66666 
             Layer_ = 2
             ) : ReportLine (
         ReportControl => R);
         
         Line1 Invocation
            ( -0.94 , 0.66 , 0.0 , 0.66 , 0.66666 
             Layer_ = 2
             ) : ReportLine (
         ReportControl => R);
         
         Line3 Invocation
            ( -0.94 , 0.5 , 0.0 , 0.66 , 0.66666 
             Layer_ = 2
             ) : ReportLine (
         ReportControl => R);
         
         Line4 Invocation
            ( -0.94 , 0.42 , 0.0 , 0.66 , 0.66666 
             Layer_ = 2
             ) : ReportLine (
         ReportControl => R);
         
         Line5 Invocation
            ( -0.94 , 0.34 , 0.0 , 0.66 , 0.66666 
             Layer_ = 2
             ) : ReportLine (
         ReportControl => R);
         
         Line6 Invocation
            ( -0.94 , 0.26 , 0.0 , 0.66 , 0.66666 
             Layer_ = 2
             ) : ReportLine (
         ReportControl => R);
         
         Line0 Invocation
            ( -0.94 , 0.86 , 0.0 , 0.66 , 0.66666 
             Layer_ = 2
             ) : ReportLine (
         ReportControl => R);
         
         AuthorString Invocation
            ( -0.8 , 0.66 , 0.0 , 0.2 , 0.025 
             Layer_ = 2
             ) : ReportString (
         Value => "$_AUTHOR", 
         Width => 30, 
         LeadingSpaces => 5, 
         Left => True, 
         ReportControl => R);
         
         DateString Invocation
            ( -0.8 , 0.58 , 0.0 , 0.2 , 0.025 
             Layer_ = 2
             ) : ReportString (
         Value => "$_OPRECIPE_DATE", 
         Width => 30, 
         LeadingSpaces => 5, 
         Left => True, 
         ReportControl => R);
         
         ProdDescrString Invocation
            ( -0.8 , 0.5 , 0.0 , 0.2 , 0.025 
             Layer_ = 2
             ) : ReportString (
         Value => "$_PRODUCT_DESCRIPTION", 
         Width => 30, 
         LeadingSpaces => 5, 
         Left => True, 
         ReportControl => R);
         
         ProductCodeString Invocation
            ( -0.8 , 0.42 , 0.0 , 0.2 , 0.025 
             Layer_ = 2
             ) : ReportString (
         Value => "$_PRODUCT_CODE", 
         Width => 30, 
         LeadingSpaces => 5, 
         Left => True, 
         ReportControl => R);
         
         MasterAuthor Invocation
            ( -0.08 , 0.66 , 0.0 , 0.2 , 0.025 
             Layer_ = 2
             ) : ReportString (
         Value => OpRecipe.Header.MasterRecipeAuthor, 
         Width => MasterRecipeWidth, 
         Left => True, 
         EnableModule => EnableMaster, 
         ReportControl => R);
         
         ControlAuthor Invocation
            ( 0.4 , 0.66 , 0.0 , 0.2 , 0.025 
             Layer_ = 2
             ) : ReportString (
         Value => OpRecipe.Header.ControlRecipeAuthor, 
         Width => ControlRecipeWidth, 
         Left => True, 
         EnableModule => EnableControl, 
         ReportControl => R);
         
         MasterDate Invocation
            ( -0.08 , 0.58 , 0.0 , 0.2 , 0.025 
             Layer_ = 2
             ) : ReportTime (
         Value => OpRecipe.Header.MasterRecipeDate, 
         Width => MasterRecipeWidth, 
         Left => True, 
         EnableModule => EnableMaster, 
         ReportControl => R);
         
         ControlDate Invocation
            ( 0.4 , 0.58 , 0.0 , 0.2 , 0.025 
             Layer_ = 2
             ) : ReportTime (
         Value => OpRecipe.Header.ControlRecipeDate, 
         Width => ControlRecipeWidth, 
         Left => True, 
         EnableModule => EnableControl, 
         ReportControl => R);
         
         ProductDescription Invocation
            ( -0.08 , 0.5 , 0.0 , 0.2 , 0.025 
             Layer_ = 2
             ) : ReportString (
         Value => OpRecipe.Header.ProductDescription, 
         Width => 40, 
         Left => True, 
         ReportControl => R);
         
         ProductCode Invocation
            ( -0.08 , 0.42 , 0.0 , 0.2 , 0.025 
             Layer_ = 2
             ) : ReportString (
         Value => OpRecipe.Header.ProductCode, 
         Width => 40, 
         Left => True, 
         ReportControl => R);
         
         Colon1 Invocation
            ( -0.3 , 0.66 , 0.0 , 0.06 , 0.025 
             Layer_ = 2
             ) : ReportString (
         Value => " : ", 
         Width => 3, 
         Left => True, 
         ReportControl => R);
         
         Colon2 Invocation
            ( -0.3 , 0.58 , 0.0 , 0.06 , 0.025 
             Layer_ = 2
             ) : ReportString (
         Value => " : ", 
         Width => 3, 
         Left => True, 
         ReportControl => R);
         
         Colon3 Invocation
            ( -0.3 , 0.5 , 0.0 , 0.06 , 0.025 
             Layer_ = 2
             ) : ReportString (
         Value => " : ", 
         Width => 3, 
         Left => True, 
         ReportControl => R);
         
         Colon4 Invocation
            ( -0.3 , 0.42 , 0.0 , 0.06 , 0.025 
             Layer_ = 2
             ) : ReportString (
         Value => " : ", 
         Width => 3, 
         Left => True, 
         ReportControl => R);
         
         HideInOperate Invocation
            ( 0.74 , -0.94 , 0.0 , 0.22 , 0.22666 
             Layer_ = 2
             Enable_ = True : InVar_ False ) : MODULEDEFINITION DateCode_ 
         370817877 ( Frame_Module ) 
         SUBMODULES
            Pres Invocation
               ( -0.96429 , -0.25 , 0.0 , 1.99234 , 1.99234 
                ) : ReportPres (
            Name => name, 
            Filename => filename, 
            R => r, 
            Fontsize => Fontsize, 
            Execute => execute, 
            Ready => ready);
            
         
         ModuleDef
         ClippingBounds = ( -1.0 , -0.28571 ) ( 0.48 , 0.28 )
         
         ENDDEF (*HideInOperate*);
         
         Code Invocation
            ( 0.94 , -0.94 , 0.0 , 0.06 , 0.06 
             Layer_ = 2
             ) : ReportMasterCode (
         R => R, 
         FirstLine => FirstLine, 
         LastLine => LastLine, 
         HeaderFirstLine => HeaderFirstLine, 
         HeaderEndLine => HeaderEndLine, 
         FileName => FileName, 
         PageLength => PageLength, 
         PageWidth => PageWidth, 
         EnableSpreadSheet => EnableSpreadSheet, 
         LineDelimiter => LineDelimiter, 
         FieldDelimiter => FieldDelimiter, 
         StringDelimiter => StringDelimiter, 
         Append => Append, 
         TrailingFormFeed => TrailingFormFeed, 
         LeadingFormFeed => LeadingFormFeed, 
         Execute => Execute, 
         Ready => Ready, 
         ReadyOK => ReadyOK);
         
      
      ModuleDef
      ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
      Two_Layers_ LayerLimit_ = 0.95
      Zoomable
      GraphObjects :
         RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
            OutlineColour : Colour0 = -3 
         RectangleObject ( -1.0 , -1.0 ) ( 0.99998 , 0.99998 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
            FillColour : Colour0 = -2 
         TextObject ( -0.9 , 0.74 ) ( -0.8 , 0.76 ) 
            "FirstLine" 
            ConnectionNode ( -0.94 , 0.76 ) 
            LeftAligned 
            Layer_ = 2
            Enable_ = True : InVar_ False 
            OutlineColour : Colour0 = -3 
         TextObject ( -0.98 , -0.98 ) ( -0.88 , -0.96 ) 
            "LastLine" 
            ConnectionNode ( -0.94 , -0.92 ) 
            
            Layer_ = 2
            Enable_ = True : InVar_ False 
            OutlineColour : Colour0 = -3 
         LineObject ( 0.19999 , 0.98665 ) ( 0.19999 , -1.01333 ) 
            Layer_ = 2
            Enable_ = True : InVar_ False 
            OutlineColour : Colour0 = -3 ColourStyle = 75.0 
         LineObject ( -0.86667 , 0.99998 ) ( -0.86667 , -1.0 ) 
            Layer_ = 2
            Enable_ = True : InVar_ False 
            OutlineColour : Colour0 = -3 ColourStyle = 75.0 
         LineObject ( 0.89331 , 0.99998 ) ( 0.89331 , -1.0 ) 
            Layer_ = 2
            Enable_ = True : InVar_ False 
            OutlineColour : Colour0 = -3 ColourStyle = 75.0 
         PolygonObject Polyline Connection ( -0.94 , 0.58 ) 
            ( -0.94 , 0.553333 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( -0.94 , 0.5 ) 
            ( -0.94 , 0.473333 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( -0.94 , 0.42 ) 
            ( -0.94 , 0.393333 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( -0.94 , 0.26 ) 
            ( -0.94 , -0.92 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         TextObject ( -0.9 , 0.82 ) ( -0.72 , 0.8 ) 
            "HeaderEndLine" 
            ConnectionNode ( -0.94 , 0.8 ) 
            LeftAligned 
            Layer_ = 2
            Enable_ = True : InVar_ False 
            OutlineColour : Colour0 = -3 
         TextObject ( -0.9 , 0.98 ) ( -0.72 , 0.96 ) 
            "HeaderFirstLine" 
            ConnectionNode ( -0.94 , 0.98 ) 
            LeftAligned 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( -0.94 , 0.76 ) 
            ( -0.94 , 0.713333 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( -0.94 , 0.66 ) 
            ( -0.94 , 0.633333 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         TextObject ( -0.62 , 0.94 ) ( -0.1 , 1.0 ) 
            "Header" 
            Layer_ = 2
            Enable_ = True : InVar_ False 
            OutlineColour : Colour0 = -3 
         TextObject ( -0.62 , 0.74 ) ( -0.1 , 0.8 ) 
            "Page" 
            Layer_ = 2
            Enable_ = True : InVar_ False 
            OutlineColour : Colour0 = -3 
         TextObject ( 0.2 , 0.82 ) ( 0.2 , 0.76 ) 
            "80" RightAligned 
            Layer_ = 2
            Enable_ = True : InVar_ False 
            OutlineColour : Colour0 = 31 
         TextObject ( 0.9 , 0.82 ) ( 0.9 , 0.76 ) 
            "132" RightAligned 
            Layer_ = 2
            Enable_ = True : InVar_ False 
            OutlineColour : Colour0 = 31 
         PolygonObject Polyline Connection ( -0.874 , 0.286666 ) 
            ( 0.8684 , 0.286666 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( -0.94 , 0.86 ) 
            ( -0.94 , 0.8 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
            FillColour : Colour0 = 41 
         PolygonObject Polyline Connection ( -0.874 , 0.886666 ) 
            ( 0.8684 , 0.886666 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
            FillColour : Colour0 = 41 
         LineObject ( 0.19999 , 0.79998 ) ( 0.19999 , -0.8 ) 
            Layer_ = 2
            Enable_ = True : InVar_ False 
            OutlineColour : Colour0 = 31 
         PolygonObject Polyline Connection ( -0.874 , 0.366666 ) 
            ( 0.8684 , 0.366666 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
            FillColour : Colour0 = 12 
         PolygonObject Polyline Connection ( -0.94 , 0.913333 ) 
            ( -0.94 , 0.98 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( -0.94 , 0.34 ) 
            ( -0.94 , 0.313333 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         TextObject ( -0.8 , 0.1 ) ( 0.7 , 0.2 ) 
            "Please do not use more than six lines for the pagetop text !" 
            LeftAligned 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( -0.874 , 0.686666 ) 
            ( -0.8 , 0.685 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( -0.4 , 0.685 ) 
            ( -0.3 , 0.685 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( -0.874 , 0.606666 ) 
            ( -0.8 , 0.605 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( -0.4 , 0.605 ) 
            ( -0.3 , 0.605 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( -0.874 , 0.526666 ) 
            ( -0.8 , 0.525 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( -0.4 , 0.525 ) 
            ( -0.3 , 0.525 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( -0.18 , 0.525 ) 
            ( -0.0799999 , 0.525 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( -0.874 , 0.446666 ) 
            ( -0.8 , 0.445 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( -0.4 , 0.445 ) 
            ( -0.3 , 0.445 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( -0.18 , 0.445 ) 
            ( -0.0799999 , 0.445 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( 0.32 , 0.525 ) 
            ( 0.8684 , 0.526666 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( 0.32 , 0.445 ) 
            ( 0.8684 , 0.446666 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( -0.18 , 0.685 ) 
            ( -0.0799999 , 0.685 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( 0.32 , 0.685 ) 
            ( 0.4 , 0.685 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( 0.8 , 0.685 ) 
            ( 0.8684 , 0.686666 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( -0.18 , 0.605 ) 
            ( -0.08 , 0.605 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( 0.32 , 0.605 ) 
            ( 0.4 , 0.605 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
         PolygonObject Polyline Connection ( 0.8 , 0.605 ) 
            ( 0.8684 , 0.606666 ) 
            Layer_ = 2
            OutlineColour : Colour0 = -3 
      
      ModuleCode
      EQUATIONBLOCK WidthCalculation COORD -0.38, -0.42 OBJSIZE 0.3, 0.1
      Layer_ = 2 :
         IF Execute AND  NOT OldExecute THEN
            (* POSITIVE EDGE OF EXECUTE *);
            IF MasterRecipe THEN
               (* ENABLE THE MASTER RECIPE REPORTSTRINGS *);
               MasterRecipeWidth = 40;
               EnableMaster = True;
               ControlRecipeWidth = 0;
               EnableControl = False;
            ELSE
               (* ENABLE THE CONTROL RECIPE REPORTSTRINGS *);
               MasterRecipeWidth = 0;
               EnableMaster = False;
               ControlRecipeWidth = 40;
               EnableControl = True;
            ENDIF;
         ENDIF;
         (*  *);
         OldExecute = Execute;
      
      ENDDEF (*OpTopOfPageText*) (
      FileName => TopOfPageFileName, 
      OpRecipe => OpRecipeDocConn.OperationRecipe, 
      MasterRecipe => MasterRecipe, 
      Execute => ExecuteTopOfPage, 
      Ready => TopOfPageReady, 
      ReadyOK => TopOfPageReadyOK);
      
      GraphObj Invocation
         ( -0.6 , -0.48 , 0.0 , 0.36 , 0.36 
          Layer_ = 1
          ) : MODULEDEFINITION DateCode_ 370817877 ( Frame_Module ) 
      
      
      ModuleDef
      ClippingBounds = ( -1.0 , -0.72222 ) ( 1.0 , 0.72222 )
      GraphObjects :
         TextObject ( -1.0 , -0.72222 ) ( 0.88889 , 0.66667 ) 
            "OP" LeftAligned 
            Layer_ = 1
            OutlineColour : Colour0 = -3 
      
      ENDDEF (*GraphObj*);
      
   
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   Two_Layers_ LayerLimit_ = 0.95
   Zoomable
   GraphObjects :
      RectangleObject ( -1.0 , -1.0 ) ( 1.0 , 1.0 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
         FillColour : Colour0 = -2 
      TextObject ( -1.0 , 0.72 ) ( 0.0 , 0.84 ) 
         "ErrorStatus:" LeftAligned 
         Layer_ = 2
         OutlineColour : Colour0 = 5 Colour1 = 12 ColourStyle = False : InVar_ 
         "Error" 
      TextObject ( 0.0 , 0.72 ) ( 1.0 , 0.84 ) 
         "ErrorStatus" VarName Width_ = 5 : InVar_ 5  ValueFraction = 2  
         Layer_ = 2
         OutlineColour : Colour0 = 5 Colour1 = 12 ColourStyle = False : InVar_ 
         "Error" 
      TextObject ( -0.72 , 0.6 ) ( -1.0 , 0.54 ) 
         "ToFirst" 
         ConnectionNode ( -0.9 , 0.4 ) 
         LeftAligned 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      TextObject ( 1.0 , 0.6 ) ( 0.74 , 0.54 ) 
         "FromLast" 
         ConnectionNode ( 0.9 , 0.4 ) 
         LeftAligned 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      TextObject ( -1.0 , 0.84 ) ( 1.0 , 1.0 ) 
         "Name" VarName Width_ = 5 : InVar_ 5  ValueFraction = 3  
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.9 , 0.4 ) 
         ( -0.82 , 0.4 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( 0.26 , 0.4 ) 
         ( 0.34 , 0.4 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( 0.54 , 0.4 ) 
         ( 0.62 , 0.4 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.04 , 0.4 ) 
         ( 0.06 , 0.4 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.34 , 0.4 ) 
         ( -0.24 , 0.4 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.62 , 0.4 ) 
         ( -0.54 , 0.4 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( 0.82 , 0.4 ) 
         ( 0.9 , 0.4 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( 0.39 , 0.3 ) 
         ( 0.39 , 0.1 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( 0.44 , 0.3 ) 
         ( 0.44 , 0.1 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( 0.49 , 0.3 ) 
         ( 0.49 , 0.1 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( -0.9 , 0.4 ) 
         ( -0.9 , -0.8 ) ( 0.5 , -0.8 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
      PolygonObject Polyline Connection ( 0.7 , -0.8 ) 
         ( 0.9 , -0.8 ) ( 0.9 , 0.4 ) 
         Layer_ = 2
         OutlineColour : Colour0 = -3 
   
   ENDDEF (*OpRecGraphDoc*);
   
LOCALVARIABLES
   RecipeRevServer 
   "The name of the file revision server.  The revision handling is activated when this name is defined"
   : string  := "";
   RevisionDelimiter "Configurable delimiter. Must be unique in a file name": 
   identstring Const := "_v";
   SysList: SystListType ;
   OpScanGroup, Slc1ScanGroup, Slc2ScanGroup: GroupData ;
   ProgStationData: ProgStationData ;
   EnableInteraction, EnableEdit, EnableEditRestricted, EnableControl, 
   EnableStart: boolean  := True;
   UnitList: UnitSystemType ;
   RecipeSystem, RecipeDirectory, JournalSystem1, JournalSystem2, PrinterSystem
   : string OpSave;
   PrinterNo: integer OpSave := 1;
   Status: integer ;
SUBMODULES
   batchdemo
   (*  *)
    Invocation
      ( -0.5 , -0.2 , 0.0 , 1.0 , 1.0 
       IgnoreMaxModule ) : MODULEDEFINITION DateCode_ 681872061 ( Frame_Module 
   ) 
   SUBMODULES
      ProgStationControl Invocation
         ( 0.06 , 0.06 , 0.0 , 0.06 , 0.06 
          ) : ProgStationControl;
      
      VariableSecure Invocation
         ( 0.06 , 0.18 , 0.0 , 0.06 , 0.06 
          ) : VariableSecure;
      
      OpStation Invocation
         ( 0.46 , 0.65 , 0.0 , 0.72 , 0.72 
          ) : OpStationBatch (
      ScanGroup => OpScanGroup, 
      ProcessManagerNumber => 1, 
      JournalSystem1 => JournalSystem1, 
      JournalSystem2 => JournalSystem2, 
      RecipeSystem => RecipeSystem, 
      RecipeDirectory => RecipeDirectory, 
      PrinterSystem => PrinterSystem, 
      PrinterNo => PrinterNo, 
      RecipeRevServer => RecipeRevServer, 
      RevisionDelimiter => RevisionDelimiter, 
      OpName => SysList.OpName, 
      EnableInteraction => EnableInteraction, 
      EnableEdit => EnableEdit, 
      EnableEditRestricted => EnableEditRestricted, 
      EnableControl => EnableControl, 
      EnableStart => EnableStart);
      
      OpScanGroup Invocation
         ( 0.18 , 0.06 , 0.0 , 0.06 , 0.06 
          ) : ScanGroupControl (
      Name => "OpScanGroup", 
      Group => OpScanGroup, 
      System => SysList.OpName, 
      ReqCycleTimeInit => 500);
      
      Slc1ScanGroup Invocation
         ( 0.3 , 0.06 , 0.0 , 0.06 , 0.06 
          ) : ScanGroupControl (
      Name => "Slc1ScanGroup", 
      Group => Slc1ScanGroup, 
      System => SysList.Slc1Name, 
      ReqCycleTimeInit => 500);
      
      Slc2ScanGroup Invocation
         ( 0.42 , 0.06 , 0.0 , 0.06 , 0.06 
          ) : ScanGroupControl (
      Name => "Slc2ScanGroup", 
      Group => Slc2ScanGroup, 
      System => SysList.Slc2Name, 
      ReqCycleTimeInit => 500);
      
      SLC1 Invocation
         ( 0.28 , 0.12 , 0.0 , 0.72 , 0.72 
          ) : SLC (
      Unit1Name => UnitList.Unit1, 
      Unit2Name => UnitList.Unit2, 
      Unit3Name => UnitList.Unit3, 
      SlcName => SysList.Slc1Name, 
      JournalSystem => SysList.OpName, 
      ProcessManagerNumber => 1, 
      ScanGroup => Slc1ScanGroup, 
      EnableInteraction => EnableInteraction, 
      EnableEdit => EnableEdit, 
      EnableEditRestricted => EnableEditRestricted, 
      EnableControl => EnableControl);
      
      SLC2 Invocation
         ( 1.12 , 0.12 , 0.0 , 0.72 , 0.72 
          ) : Slc (
      Unit1Name => UnitList.Unit4, 
      Unit2Name => UnitList.Unit5, 
      Unit3Name => UnitList.Unit6, 
      SlcName => SysList.Slc2Name, 
      JournalSystem => SysList.OpName, 
      ProcessManagerNumber => 1, 
      ScanGroup => Slc2ScanGroup, 
      EnableInteraction => EnableInteraction, 
      EnableEdit => EnableEdit, 
      EnableEditRestricted => EnableEditRestricted, 
      EnableControl => EnableControl);
      
      MmsDiagnostics Invocation
         ( 0.54 , 0.06 , 0.0 , 0.06 , 0.06 
          ) : MmsDiagnostics (
      RemSys => SysList.Slc1Name, 
      ExportCycleTime => 2000, 
      PictCycleTime => 2000, 
      PictBGCycleTime => 2000);
      
      RecipeManager1 Invocation
         ( 0.24 , 0.99 , 0.0 , 0.18 , 0.18 
          ) : RecipeManager1 (
      RecipeSystem => RecipeSystem, 
      RecipeDirectory => RecipeDirectory, 
      RecipeRevServer => RecipeRevServer, 
      RevisionDelimiter => RevisionDelimiter, 
      EnableEdit => EnableEdit, 
      EnableEditRestricted => EnableEditRestricted, 
      EnableControl => False, 
      PrinterSystem => PrinterSystem, 
      PrinterNo => PrinterNo, 
      EnableInteraction => EnableInteraction);
      
      BatchDemoVersion Invocation
         ( 1.86 , 1.3 , 0.0 , 0.12 , 0.12 
          ) : BatchDemoVersion;
      
      FileRevisionServer1 Invocation
         ( 0.21 , 0.59 , 0.0 , 0.07 , 0.07 
          ) : FileRevisionServer (
      Name => RecipeRevServer);
      
   
   ModuleDef
   ClippingBounds = ( 0.0 , 0.0 ) ( 2.0 , 1.4 )
   Zoomable
   Grid = 0.01
   GraphObjects :
      TextObject ( 0.0 , 1.32 ) ( 0.4 , 1.4 ) 
         "BatchDemo" LeftAligned 
         OutlineColour : Colour0 = -3 
      TextObject ( 0.6 , 0.08 ) ( 0.86 , 0.12 ) 
         "EnableEdit" RightAligned 
         OutlineColour : Colour0 = -3 
      TextObject ( 0.9 , 0.04 ) ( 1.16 , 0.08 ) 
         "EnableStart" RightAligned 
         OutlineColour : Colour0 = -3 
      TextObject ( 0.9 , 3.72529E-09 ) ( 1.16 , 0.04 ) 
         "EnableInteraction" RightAligned 
         OutlineColour : Colour0 = -3 
      TextObject ( 0.6 , 7.45058E-09 ) ( 0.86 , 0.04 ) 
         "EnableControl" RightAligned 
         OutlineColour : Colour0 = -3 
      TextObject ( 0.6 , 0.04 ) ( 0.86 , 0.08 ) 
         "EnableEditRestricted" RightAligned 
         OutlineColour : Colour0 = -3 
      TextObject ( 0.05 , 1.2 ) ( 0.45 , 1.29 ) 
         "RecipeManager" LeftAligned 
         OutlineColour : Colour0 = -3 
      TextObject ( 1.5 , 1.05 ) ( 1.75 , 1.1 ) 
         "RecipeDirectory" 
      TextObject ( 1.5 , 1.15 ) ( 1.75 , 1.2 ) 
         "RecipeSystem" 
      TextObject ( 1.5 , 0.95 ) ( 1.75 , 1.0 ) 
         "JournalSystem1" 
      TextObject ( 1.5 , 0.85 ) ( 1.75 , 0.9 ) 
         "JournalSystem2" 
      TextObject ( 1.5 , 0.75 ) ( 1.75 , 0.8 ) 
         "PrinterSystem" 
      TextObject ( 1.5 , 0.65 ) ( 1.75 , 0.7 ) 
         "PrinterNo" 
      TextObject ( 0.04 , 0.66 ) ( 0.45 , 0.75 ) 
         "FileRevisionServer" LeftAligned 
         OutlineColour : Colour0 = -3 
   InteractObjects :
      TextBox_ ( 1.75 , 0.75 ) ( 1.99 , 0.8 ) 
         String_Value
         Variable = "" : OutVar_ "PrinterSystem" CenterAligned Abs_ Digits_
         
         FillColour : Colour0 = 9 Colour1 = -1 
      TextBox_ ( 1.75 , 0.65 ) ( 1.99 , 0.7 ) 
         Int_Value
         Variable = 0 : OutVar_ "PrinterNo" CenterAligned Abs_ Digits_
         
         FillColour : Colour0 = 9 Colour1 = -1 
      ComBut_ ( 0.86 , 0.08 ) ( 0.9 , 0.12 ) 
         Bool_Value
         Variable = False : OutVar_ "EnableEdit" ToggleAction
         Abs_ SetApp_
         
      ComBut_ ( 1.16 , 0.0 ) ( 1.2 , 0.04 ) 
         Bool_Value
         Variable = False : OutVar_ "EnableInteraction" ToggleAction
         Abs_ SetApp_
         
      ComBut_ ( 1.16 , 0.04 ) ( 1.2 , 0.08 ) 
         Bool_Value
         Variable = False : OutVar_ "EnableStart" ToggleAction
         Abs_ SetApp_
         
      ComBut_ ( 0.86 , 0.0 ) ( 0.9 , 0.04 ) 
         Bool_Value
         Variable = False : OutVar_ "EnableControl" ToggleAction
         Abs_ SetApp_
         
      ComBut_ ( 0.86 , 0.04 ) ( 0.9 , 0.08 ) 
         Bool_Value
         Variable = False : OutVar_ "EnableEditRestricted" ToggleAction
         Abs_ SetApp_
         
      TextBox_ ( 1.75 , 1.15 ) ( 1.99 , 1.2 ) 
         String_Value
         Variable = "" : OutVar_ "RecipeSystem" CenterAligned Abs_ Digits_
         
         FillColour : Colour0 = 9 Colour1 = -1 
      TextBox_ ( 1.75 , 1.05 ) ( 1.99 , 1.1 ) 
         String_Value
         Variable = "" : OutVar_ "RecipeDirectory" CenterAligned Abs_ Digits_
         
         FillColour : Colour0 = 9 Colour1 = -1 
      TextBox_ ( 1.75 , 0.95 ) ( 1.99 , 1.0 ) 
         String_Value
         Variable = "" : OutVar_ "JournalSystem1" CenterAligned Abs_ Digits_
         
         FillColour : Colour0 = 9 Colour1 = -1 
      TextBox_ ( 1.75 , 0.85 ) ( 1.99 , 0.9 ) 
         String_Value
         Variable = "" : OutVar_ "JournalSystem2" CenterAligned Abs_ Digits_
         
         FillColour : Colour0 = 9 Colour1 = -1 
   
   ENDDEF (*batchdemo*);
   

ModuleDef
ClippingBounds = ( -10.0 , -10.0 ) ( 10.0 , 10.0 )
ZoomLimits = 1.42857E+10 0.01

ENDDEF (*BasePicture*);

