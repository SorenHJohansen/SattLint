# SattLine Data Acquisition and Storage Reference

## Journal Concepts

### Journal Structure
A journal is a timestamped data file:
```
Timestamp | Tag | Data
12:01     | TT1 | 23.45
12:03     | TT1 | 3.66
12:40     | REPORT | "Choco, 345.6, Juice, 234.6"
```

### Journal Attributes
| Attribute | Description | Default |
|-----------|-------------|---------|
| Deletable | Can be deleted by code | True |
| AutoNewEntry | Add 1ms if duplicate timestamp | True |
| Overwrite | Replace existing entry | False |

**Priority:** Overwrite > AutoNewEntry

### Data Types Supported
- Integer
- Real
- Boolean
- String
- Structured types (records)
- Arrays

---

## Journal Operations

### Creating Journals

**JouCreate (local):**
```
JouCreate(JournalName, Attributes, Status)
```

**JouLocalCreate:**
- Creates on local node
- Full attribute control

### Writing to Journals

**JouWriteEntry:**
```
JouWriteEntry(Journal, Tag, Data, Timestamp, Status)
```
- Timestamp added automatically if not specified
- Synchronous or asynchronous operation

### Reading from Journals

**JouReadEntry:**
```
JouReadEntry(Journal, Tag, TimeFrom, TimeTo, Entry, Status)
```
- Returns one entry per call
- Sequential access pattern

**JouReadEntryKey:**
- Search by key/tag
- Random access

**JouReadTag:**
- Read specific tag
- Time range filtering

### Journal Maintenance

**JouPurgeEntries:**
- Remove old entries
- By time or count
- Tag-specific or all

**JouLocalErase:**
- Erase time interval
- Tag-specific

**JouDelete:**
- Delete entire journal
- Must be deletable

**JouLocalCopy:**
- Backup journal
- Can copy while in use

**JouLocalRename:**
- Rename journal

---

## History Logging

### HistoryControlMaster
- Central history management
- Multiple history groups
- Synchronized logging
- Buffer management

### HistoryGroup
- Groups related variables
- Common sampling time
- Buffer configuration

### HistoryLogger Modules

**HistoryLogger1 to HistoryLogger5:**
- Log up to 5 variables
- Configurable sampling
- Local buffering
- Automatic journal write

**HistoryLogger1RealS to HistoryLogger5RealS:**
- For RealSignal types
- Quality logging

**Parameters:**
```
HistoryLogger1Par:
  Tag: String
  SampleTime: Duration
  BufferSize: Integer
  Journal: String
```

### Basic Logging

**BasicLogger / BasicLoggerRealS:**
- Simple logging
- Single variable
- Event-triggered or cyclic

**HistoryBasicControl:**
- On/off control
- Single point logging

---

## History Presentation

### CurveDataBase
- Manages history data
- Time range handling
- Data retrieval

**Parameters:**
```
CurveDataBasePar:
  Journal: String
  Tag: String
  TimeSpan: Duration
```

### Curve4Display
- Displays history curves
- Up to 4 trends
- Zoom and scroll
- Real-time update

**Interaction:**
- Pan along time axis
- Zoom in/out
- Cursor for values
- Update/stopped mode

### Statistical Analysis

**JouStatistics:**
- Min, max, average
- Standard deviation
- Time range

**JouStatisticsBar:**
- Bar chart display
- Statistical summaries

---

## Journal Lists

### JouListServer
- Server-side list generation
- Format control
- Multiple tags

### JouList
- ASCII text output
- Spreadsheet compatible
- Delimiter selection
- Time range

### JouListEventLog
- Specialized for events
- Alarm/event formatting
- Severity filtering

---

## Report Generation (ReportLib)

### ReportMaster
- Central report control
- Trigger conditions
- Output formatting

### Report Modules

**ReportInteger / ReportReal / ReportString / ReportBoolean / ReportTime / ReportDuration:**
- Field reporting
- Format specification
- Width and decimals

**ReportLine:**
- Text line output
- Separators

**ReportJournalTable / ReportJourTableKey:**
- Table from journal
- Multiple columns
- Key-based selection

**ReportArrayTable / ReportRecordTable:**
- Array data reporting
- Record structure output

**ReportFormFeed:**
- Page breaks

**ReportStatisticsCalc:**
- Statistical calculations
- Min/max/average

### PostScript Reports

**PSReportInit:**
- Initialize PostScript output
- Page setup

**PSReportText:**
- Text in PostScript
- Font control

**PSReportPicture:**
- Include graphics
- Image embedding

**PSReportWait:**
- Page control
- Delay/continue

### Report Configuration
- Text file output
- PostScript for printing
- Conditional execution
- Loop control (ReportControlDivert / ReportControlAccept)

---

## SQL Integration (SQLLib)

### SQLCommand
- Execute SQL statements
- INSERT, UPDATE, DELETE
- Asynchronous execution

### SQLSelect / SQLSingleSelect
- Query databases
- Return results
- Row-by-row or single value

### Session Management

**SQLBeginSession:**
- Connect to database
- Authentication

**SQLSessionCommand / SQLSessionSelect:**
- Commands within session
- Transaction context

**SQLSessionCommit / SQLSessionRollBack:**
- Transaction control

**SQLEndSession:**
- Close connection

### Data Types
```
SQLConnectType: Connection parameters
SessionConnectType: Session configuration
SessionType: Active session
BeginSessionType: Session start parameters
```

### Supported Databases
- ODBC compliant
- Oracle
- SQL Server
- Access
- Other ODBC drivers

---

## Enterprise Integration

### ODBC MMS Gateway
- SQL access to SattLine data
- Read/write variables
- Journal access
- ODBC driver

### OLE MMS Gateway
- COM/DCOM interface
- Windows applications
- Excel, VB, etc.

### System Command
- Execute external programs
- File operations
- Trigger integrations

---

## Best Practices

### Journal Design
- Use descriptive tags
- Include program/unit prefix
- Consistent naming
- Plan for growth

### History Logging
- Match sample time to process
- Fast processes: 1-10 seconds
- Slow processes: 1-60 minutes
- Buffer appropriately

### Data Retention
- Purge old data regularly
- Archive before purge
- Consider regulatory requirements
- Monitor disk space

### Performance
- Buffer before network write
- Group related variables
- Use appropriate scan groups
- Avoid excessive logging

### Security
- Limit journal deletion
- Secure SQL connections
- Audit sensitive data access
- Backup critical journals

---

## Common Configurations

### Operator Logging
```
- Operator actions
- Setpoint changes
- Mode switches
- Alarm acknowledgments
```

### Production Logging
```
- Batch records
- Material usage
- Product quality
- Equipment runtime
```

### Maintenance Logging
```
- Equipment status
- Operating hours
- Calibration data
- Maintenance events
```

### Environmental Logging
```
- Temperature
- Pressure
- Flow totals
- Emissions data
```
