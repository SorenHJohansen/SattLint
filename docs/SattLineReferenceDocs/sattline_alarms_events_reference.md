# SattLine Alarms and Events Reference

## Event Detection

### Event Types
| Type | Description |
|------|-------------|
| Alarm | Abnormal condition requiring operator attention |
| Event | General state change or occurrence |
| Operator Interaction | Operator action logged |
| Process Event | Automatic process action |

### Event Detection Parameters
- **Tag** — Unique identifier (max 22 chars, format: `Program.Unit.Signal`)
- **Event Text** — Description message
- **Severity** — 1 (highest) to 8 (lowest)
- **Class** — 1-16 for grouping/operator assignment
- **Type** — Alarm type classification

### Time Filtering
Prevents nuisance alarms:
- Minimum time in state before alarm
- Maximum time for state acknowledgment
- Configurable per detector

---

## EventLib Modules

### Event Detection

**EventDetector1 / EventDetector2**
- Monitors boolean signal for state changes
- Parameters: Tag, Severity, Class, EventType, TimeFilter
- Outputs: Alarm state, acknowledgment status

**EventLostDetector**
- Detects missed events due to system issues
- Queues events that couldn't be delivered

### Event Presentation

**Event1 / Event2 / Event1Advanced / Event2Advanced**
- Single event display
- Shows: Tag, text, time, severity, state
- Operator acknowledgment
- Blinking for unacknowledged alarms

**EventList / EventInhibitList**
- Lists multiple events
- Filtering by severity/class
- Sorting by time/priority
- Acknowledge all/individual

**EventLine / EventLineSelect**
- Compact event line display
- Scrolling through active events
- Configurable priority display

### Event Interaction

**EventInteractor / EventAllInteractor**
- Operator interaction with events
- Acknowledge, block, inhibit functions
- Privilege checking

### Event Logging

**EventLogger / EventLoggerMaster**
- Logs events to journal
- Parameters: JournalName, Tag prefix
- Automatic timestamp
- Batch/lot correlation

**EventPrinter**
- Prints events to printer
- Format templates
- Real-time or buffered output

**EventAnnunciator**
- Audio/visual alarm activation
- Configurable sounds per severity
- Acknowledgment required

### COMLI Alarms

**EventComli1**
- Interface to external COMLI alarm systems
- Sends/receives alarm telegrams
- Protocol conversion

---

## Data Types

### EventSubscriberPar
```
Tag: String
Severity: Integer (1-8)
Class: Integer (1-16)
EventType: Integer
Enable: Boolean
```

### EventListPar
```
MinSeverity: Integer
MaxSeverity: Integer
FilterClass: Integer
TimeSpan: Duration
```

### EventFormatType
Controls presentation format:
- Tag display
- Time format
- Severity/class icons
- Text layout

### FilterConnectionType
```
FilterTag: String
FilterClass: Integer
FilterSeverity: Integer
```

---

## Presentation Formats

### Event Display Elements
1. **Icon** — Severity-based graphic
2. **Tag** — Event identifier
3. **Text** — Event description
4. **Time** — Timestamp (absolute/relative)
5. **State** — Active/inactive/acknowledged
6. **Severity/Class** — Color coding

### Severity Colors
| Severity | Color | Blink |
|----------|-------|-------|
| 1 | Red | Yes |
| 2 | Red | No |
| 3 | Yellow | Yes |
| 4 | Yellow | No |
| 5-8 | Blue/White | No |

### Status Texts
Alternative text for boolean states:
- `StatusTextGroup` — Defines state descriptions
- Example: "Open"/"Closed" instead of "True"/"False"

---

## Operator Interaction

### Actions
- **Acknowledge** — Mark as seen (stops blinking/audio)
- **Block** — Temporarily suppress alarm
- **Inhibit** — Disable detection entirely
- **Comment** — Add operator note

### Privileges
Different privileges for:
- Alarm acknowledgment
- Alarm blocking/inhibiting
- Configuration changes

---

## Distributed Events

### Multi-System Configuration
- Events propagate across network
- Centralized or distributed presentation
- Single-event or list-based display

### Event Queues
1. **Notification queue** — Pending operator notifications
2. **Active queue** — Currently active events
3. **State queue** — All state changes (for history)

### Parallel Printing/Logging
Multiple destinations supported:
- Local printer
- Remote printer
- Journal (workstation)
- Journal (control system)

---

## PLC Functions (PLCLib)

### ACOF (Automatic Check Of Feedback)
Valve and actuator supervision:

**Type1Acof** — Full feedback (open/close + opened/closed)
- `OutputOpen`, `OutputClose` — Command signals
- `InputOpened`, `InputClosed` — Feedback signals
- `Time` — Max response time

**Type2Acof** — Single feedback (open + opened/closed)

**Type3Acof** — Open only (open + opened)

**Type5Acof** — Close only (close + closed)

**Type8Acof** — Open/close + opened only

**Type9Acof** — Open/close + closed only

### RUTI (Run Time Supervision)
Equipment runtime monitoring:
- `RutiModule` — Monitors boolean signal runtime
- Tracks operating hours
- Maintenance interval warnings
- `RutiPresList` — Presentation of runtime data

### BCD/BIN Conversion
- `BinToInt` — Binary to integer
- `IntToBin` — Integer to binary
- `BcdToInt` — BCD to integer
- `IntToBcd` — Integer to BCD

---

## Time Channel Control (TCCLib)

Time-based control functions:

**TccMaster** — Central coordinator
**TccObjectListMaster** — Manages controlled objects
**TccYear / TccWeek / TccDay / TccHour / TccMinute** — Time level controllers
**TccInterval** — Cyclic on/off control
**TccForcedDays** — Exception day handling

### TCC Data Types
```
TccWeekPar: Weekly schedule
TccIntervalPar: On/off times
TccModulePar: Module configuration
TccForcedDaysPar: Exception dates
```

---

## Configuration

### Event Settings
- Time format (absolute/relative)
- Presentation formats
- Status text groups
- Keyboard shortcuts
- Event queue sizes

### Tag Filtering
- Wildcard support (`*`, `?`)
- Program/unit/signal levels
- Regular expressions (limited)

### Colors
Configurable colors for:
- Each severity level
- Acknowledged/unacknowledged
- Blocked/inhibited states

---

## Best Practices

### Alarm Design
- Use severity 1-2 for critical safety alarms
- Severity 3-4 for operational warnings
- Severity 5+ for informational events
- Keep event text concise (< 80 chars)
- Include unit/location in tag

### Time Filtering
- Set based on process dynamics
- Too short = nuisance alarms
- Too long = delayed notification

### Operator Load
- Limit active alarms per operator
- Use classes to partition responsibility
- Implement alarm shelving for maintenance

### Logging
- Log all severity 1-4 events
- Consider rotating event journals
- Correlate with batch/lot IDs

---

## Integration Points

### With BatchLib
- Batch phase events
- Recipe parameter changes
- Equipment allocation events

### With JournalLib
- Event history storage
- Event-based reporting
- Statistical analysis

### With ControlLib
- Analog alarm limits
- Controller deviation alarms
- Equipment status changes
