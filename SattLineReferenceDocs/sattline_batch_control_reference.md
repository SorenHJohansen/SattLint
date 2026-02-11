# SattLine Batch Control Reference

## S88.01 Terminology

### Physical Hierarchy
```
Process Cell
    └── Unit (reactor, mixer, tank)
        ├── Equipment Module (heater, pump)
        └── Control Module (valve, sensor)
```

**Unit:** Contains equipment, executes recipes, works on one batch at a time
**Equipment Module:** Performs minor activities, no step sequences
**Control Module:** Basic equipment (valves, pumps)

### Recipe Hierarchy
```
General Recipe (enterprise level)
    └── Site Recipe
        └── Master Recipe (plant level)
            └── Control Recipe (control system)
                └── Operation Recipe (unit level)
```

**Procedure:** Strategy for making a batch
**Unit Procedure:** Part of procedure executed in one unit
**Operation:** Major processing activity
**Phase:** Smallest recipe element

---

## BatchLib Structure

### Core Modules

**RecipeManagerMaster**
- Central recipe management
- Recipe editing
- Version control
- Validation

**ProcessManagerMaster**
- Batch scheduling
- Unit allocation
- Recipe distribution
- Batch tracking

**Unit Supervisor Modules**
- Equipment phase execution
- Recipe step interpretation
- Arbitration
- Status reporting

### Equipment Phase Modules
- Execute specific process actions
- Parameter-driven
- Return result codes
- Examples: Fill, Heat, Mix, Cool, Transfer

---

## Data Types

### Recipe Parameters
```
RecipePar: General recipe parameters
OperationPar: Operation-level parameters
PhasePar: Phase parameters
FormulaPar: Formula values
```

### Unit Configuration
```
UnitPar: Unit properties
UnitStatus: Unit state
AllocationStatus: Allocation state
```

### Batch Tracking
```
BatchId: Unique batch identifier
LotId: Lot identification
ProductCode: Product type
BatchStatus: Current state
```

---

## Single-Unit Batch

### Basic Configuration

1. **RecipeManagerMaster**
   - Operation recipe editor
   - Recipe storage/retrieval
   - Version handling

2. **ProcessManagerMaster**
   - Batch start/stop
   - Recipe selection
   - Unit assignment

3. **UnitSupervisor**
   - Phase execution control
   - Recipe interpretation
   - Equipment coordination

### Operation Recipe Structure
```
Header:
  - Recipe name
  - Version
  - Product code
  - Batch size

Steps:
  - Phase name
  - Parameters (formula)
  - Conditions (pre/post)
  - Result handling
```

### Phase Execution Flow
1. Check pre-conditions
2. Allocate equipment
3. Execute phase logic
4. Monitor completion
5. Return result
6. Release equipment

---

## Multi-Unit Batch

### Configuration Extensions

**MatrixEditor Concept:**
- Horizontal: Units
- Vertical: Recipe steps
- Visual allocation display
- Drag-and-drop editing

### Synchronization

**Transfer Operations:**
- Source unit completes
- Destination unit ready
- Transfer phase executes
- Handshaking between units

**Allocation Arbitration:**
- Shared equipment modules
- First-request basis
- Priority override
- Timeout handling

### Batch State Tracking
- Batch identity maintained across units
- Transfer timestamps
- Current location
- Completion status

---

## Recipe Editing

### RecipeManager Editor
- Graphical step sequence
- Parameter tables
- Formula entry
- Validation rules

### Unit-Level Editing
- Local recipe modifications
- Operator recipe variants
- Parameter overrides
- Online changes

### Validation
- Syntax checking
- Equipment phase existence
- Parameter compatibility
- Step logic verification

### Version Handling
- Automatic versioning
- Change tracking
- Rollback capability
- Approval workflow

---

## Logging and Reporting

### BatchLoggerMaster
- Batch event logging
- Phase execution records
- Parameter values
- Operator actions

### BatchJournalSampler
- Automatic data collection
- Tag-based sampling
- Batch correlation
- Historical storage

### Report Generation
- Batch reports
- Production summaries
- Quality records
- Regulatory compliance

### Logged Data
- Batch start/end times
- Phase start/end
- Parameter setpoints/actuals
- Alarms during batch
- Operator interactions
- Equipment used
- Results

---

## Error Handling

### Recipe Errors
- Invalid phase names
- Missing parameters
- Array size exceeded
- Circular references

### Execution Errors
- Allocation failure
- Phase timeout
- Equipment failure
- Invalid result

### Recovery Actions
- Pause batch
- Hold equipment
- Abort batch
- Manual intervention
- Automatic retry

---

## Equipment Phases

### Phase Structure
```
Parameters:
  - Enable
  - PhaseState (input)
  - Result (output)
  - Formula parameters
  - Report parameters

Execution:
  - Idle
  - Starting
  - Running
  - Completing
  - Complete
  - Holding
  - Held
  - Aborting
  - Aborted
  - Stopping
  - Stopped
```

### Phase Results
- `0` — Normal completion
- `1-99` — User-defined success codes
- `100+` — Error codes
- `-1` — Aborted

### Standard Phases

**Material Transfer:**
- Fill (from source)
- Empty (to destination)
- Transfer (unit to unit)

**Processing:**
- Heat
- Cool
- Mix
- React
- Wait

**Utility:**
- Sample
- Weigh
- Check

---

## Operation Recipes Without Procedure

### Parameter-Only Recipes
- No step sequence
- Direct equipment operation
- Quick changeover
- Simple products

### Equipment Operations
- Direct equipment control
- Manual intervention points
- Simple state machines
- Parameter-driven

---

## Best Practices

### Recipe Design
- Keep phases simple and reusable
- Use standard phase libraries
- Document result codes
- Include timeout handling

### Unit Structure
- Design for single-batch focus
- Minimize shared equipment
- Clear allocation boundaries
- Standard interfaces

### Error Handling
- Always define timeout actions
- Include hold states
- Provide manual recovery
- Log all exceptions

### Validation
- Validate at save time
- Check equipment compatibility
- Verify parameter ranges
- Test recipe thoroughly

### Documentation
- Document recipe purpose
- Define phase behaviors
- List parameters
- Specify results

---

## Integration

### With EventLib
- Batch-related events
- Phase state changes
- Allocation events
- Alarm correlation

### With JournalLib
- Batch history
- Production records
- Quality data
- Regulatory logs

### With ControlLib
- Analog setpoints from recipe
- Controller modes
- Alarm limits from parameters
- Equipment control

### With External Systems
- MES integration
- ERP connectivity
- Laboratory systems
- Historians

---

## Performance Considerations

### Scan Group Assignment
- Recipe logic in appropriate scan group
- Fast phases in fast scan
- Slow phases can be slower

### Communication
- Minimize cross-system recipe data
- Local equipment control
- Centralized batch tracking

### Memory
- Recipe array sizes
- Phase instance limits
- Journal buffer sizing
