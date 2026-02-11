# SattLine Program Execution Reference

## Scan Groups

### Concept
Programs execute in scan groups — periodic execution cycles:
- Variables sorted by dependency
- Equations executed once per scan
- Sequences evaluated once per scan

### Standard Scan Groups

| Scan Group | Cycle Time | Use Case |
|------------|-----------|----------|
| Fast | 10-50 ms | High-speed control |
| Normal | 100-500 ms | Standard control |
| Slow | 1-10 s | Monitoring, logging |
| Manual | Triggered | Diagnostics, special |

### Scan Group Assignment
- Modules assigned to scan groups
- Variables inherit from containing module
- Can be changed dynamically
- Default: Normal

---

## Execution Parameters

### Cycle Time
- Determines scan frequency
- Affects controller performance
- Trade-off: speed vs. CPU load

### Priority
- Within same cycle time
- Higher priority = earlier execution
- Range: 0-255
- Default: 128

### Phase
- For precise timing
- 0-99% of cycle time
- Delays execution start
- Used for load distribution

### Non-Cyclic Execution
- Execute on event
- Manual trigger
- Time-based trigger
- Conditional execution

---

## Scan Group Control

### ScanGroupControl Module
- Enable/disable scan groups
- Monitor execution
- Control membership

**Parameters:**
```
ScanGroup: Integer  -- Target scan group
Enable: Boolean     -- Enable/disable
Member: Boolean     -- Module membership
```

### ScanGroupExtension Module
- Extended control options
- Operator interface
- Status monitoring

**Parameters:**
```
CycleTime: Duration    -- Current cycle time
MaxCycleTime: Duration -- Maximum observed
ExecuteCount: Integer  -- Number of executions
```

### Synchronized Scan Groups
- Multiple scan groups synchronized
- Same cycle start
- Used for coordinated control
- Phase relationship maintained

---

## Execution Order

### Sorting
- Variables sorted by dependencies
- Equations execute after inputs ready
- Ensures consistent values
- Handles feedforward correctly

### Program Loops

**Detection:**
- Cross-block loops detected
- Within-block loops not detected
- Loops cause warnings

**Indirect Dependencies:**
```
// Detected as loop
A = B + 1;
B = A * 2;  // Indirect: B depends on A
```

**Direct Dependencies:**
```
// May not be detected
A = B + 1;
B = C;
C = A;  // Hidden loop via C
```

**Handling Loops:**
- Execution continues with warning
- Values may oscillate
- Review and redesign
- Use state variables carefully

---

## Program States

### Edit Mode
- Development and testing
- Full editing capabilities
- Simulation available
- No real I/O

### Simulate Mode
- Test with real program
- Simulated I/O
- Time can be compressed
- Debugging tools active

### Operate Mode
- Production operation
- Real I/O active
- Operator interaction enabled
- Debugging limited

### Run Mode
- Standalone execution
- No operator interface
- Headless operation
- Maximum performance

---

## Run Analysis

### Program Version
- Version tracking
- Incremental numbers
- Timestamp
- Owner information

### Common Program Version
- Shared library versions
- Consistency check
- All systems must match

### Compilation
- Syntax checking
- Sorting equations
- Generating code
- Download to controller

### Version Inconsistencies
- Detected at startup
- Options: ignore, warn, stop
- Force recompile
- Update all systems

---

## Performance Monitoring

### Execution Load
- CPU utilization
- Scan time compliance
- Execution count
- Performance metrics

### SystemExecutionInfo Module
- Real-time statistics
- Load monitoring
- Performance trends
- Diagnostic information

### SystemExecutionLog Module
- Historical data
- Event logging
- Audit trail
- Troubleshooting

---

## Source Code Distribution

### Program Unit Owner
- Single owner per unit
- Edit rights
- Version control
- Change tracking

### Reserve/Release
- Check-out for editing
- Prevents conflicts
- Locks unit
- Reserved indicator

### Save Official Version
- Committed version
- Backup created
- Version incremented
- Change documented

### Installation
- Download to controller
- Compile and link
- Verify checksum
- Activate program

---

## Distributed Execution

### Variable Distribution
- Export from source system
- Import to destination
- MMS communication
- Automatic synchronization

### System Identity
- Unique system identifier
- Network address
- System type (WS/CS)
- Routing information

### Configuration
- Distribution setup
- Communication paths
- Scan group mapping
- Priority settings

---

## Best Practices

### Scan Group Selection
- Fast for critical loops
- Normal for standard control
- Slow for monitoring
- Match process dynamics

### Cycle Time Guidelines
| Process Type | Typical Cycle |
|--------------|---------------|
| Flow control | 100-500 ms |
| Pressure control | 200-1000 ms |
| Level control | 500-2000 ms |
| Temperature | 1-10 s |
| Batch phases | 100-500 ms |

### Priority Guidelines
- Critical safety: 0-50
- Fast control: 51-100
- Standard control: 101-150
- Monitoring: 151-200
- Background: 201-255

### Avoiding Loops
- Design feedforward carefully
- Check indirect dependencies
- Use state variables sparingly
- Document intended loops

### Performance Optimization
- Minimize cross-system variables
- Group related logic
- Avoid unnecessary sorting
- Use appropriate data types

### Testing
- Test in simulate mode first
- Verify scan times
- Check for loops
- Validate distributed execution

---

## Troubleshooting

### Slow Scan Times
**Causes:**
- Too much logic
- Heavy calculations
- Slow I/O
- Network delays

**Solutions:**
- Move to faster scan group
- Optimize equations
- Distribute load
- Reduce communication

### Cycle Time Violations
- Increase cycle time
- Split into multiple scans
- Reduce priority
- Optimize code

### Inconsistent Values
- Check scan group assignment
- Verify sorting order
- Look for loops
- Check state variables

### Distributed Execution Issues
- Verify system identities
- Check network connectivity
- Validate distribution config
- Monitor communication status
