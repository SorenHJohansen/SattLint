# SattLine System Procedures Reference

## String Handling

### String Operations

**ClearString(Str)** — Clear string content

**StringLength(Str)** — Returns current length

**MaxStringLength(Str)** — Returns maximum length

**GetStringPos(Str)** — Get current position

**SetStringPos(Str, Pos, Status)** — Set current position

**PutBlanks(String, NumberOfSpaces, Status)** — Insert blanks

**CutString(String, Length, Status)** — Truncate to length

**InsertString(String, String2, Length, Status)** — Insert String2 into String

**ExtractString(String, String2, Length, Status)** — Extract substring

**Concatenate(Str1, Str2, Result, Status)** — Concatenate strings

**StringMatch(Pattern, Searchstring, CaseSensitive, Status)** — Pattern matching with wildcards (`*`, `?`)

### Case Conversion

**NationalUpperCase(Source, Dest, NationCode, Status)** — To uppercase

**NationalLowerCase(Source, Dest, NationCode, Status)** — To lowercase

---

## Timer Functions

### Timer Control

**StartTimer(TimerName)** — Start timer

**StopTimer(TimerName)** — Stop timer

**HoldTimer(TimerName)** — Pause timer

### Timer Status

**TimerExpired(TimerName)** — True when timer elapsed

**TimerRunning(TimerName)** — True if running

**TimerValue(TimerName)** — Returns elapsed time

---

## ACOF (Automatic Check of Feedback)

Valve and actuator supervision:

**Acof1(AcofVar, OutOpen, OutClose, InOpened, InClosed, Time)** — Full feedback

**Acof2(AcofVar, OutOpen, InOpened, InClosed, Time)** — Open only + position

**Acof3(AcofVar, OutOpen, InOpened, Time)** — Open command + opened feedback

**Acof4(AcofVar, OutOpen, OutHalf, InOpened, InClosed, Time)** — Three-position

**Acof5(AcofVar, OutOpen, InClosed, Time)** — Open only + closed feedback

**Acof8(AcofVar, OutOpen, OutClose, InOpened, Time)** — Open/close + opened

**Acof9(AcofVar, OutOpen, OutClose, InClosed, Time)** — Open/close + closed

---

## Limiters

**MinLim(Input, OnLim, Hysteresis, Output)** — Minimum limiter

**MaxLim(Input, OnLim, Hysteresis, Output)** — Maximum limiter

---

## Variable Operations

**CopyVariable(Source, Destination, Status)** — Copy variable

**CopyVarNoSort(Source, Destination, Status)** — Copy without sort dependency

**InitVariable(UserRec, InitRec, Status)** — Initialize with defaults

**EqualVariables(Var1, Var2, Status)** — Compare variables

**Equal(Var1, Var2)** — Simple equality check

**EqualString(Str1, Str2, CaseSensitive)** — String equality

### Variable Persistence

**SaveVariable(Variable, TextFile, Status)** — Save to file

**RestoreVariable(Variable, TextFile, Status)** — Restore from file

**RestoreVariableMatch(Variable, TextFile, Status)** — Restore with matching

### Distributed Variables

**WriteVar(RemoteVar, LocalVar, AsyncOp, DebugStatus)** — Write to remote

**WriteLongVar(RemoteVar, LocalVar, AsyncOp, DebugStatus)** — Write large data

**ReadVar(RemoteVar, LocalVar, AsyncOp, DebugStatus)** — Read from remote

---

## Record Component Access

**PutRecordComponent(ExRecord, Index, InputRecord, Status)** — Set component

**GetRecordComponent(ExRecord, Index, ResultRecord, Status)** — Get component

**SearchRecComponent(ExRecord, Index, Count, SearchRec, SearchComp, FoundRec, Status)** — Search

---

## Arrays

**CreateArray(Name, FirstIndex, LastIndex, Element, Status)** — Create dynamic array

**DeleteArray(Name, Status)** — Delete array

**GetArray(Name, Index, Element, Status)** — Read element

**PutArray(Name, Index, Element, Status)** — Write element

**InsertArray(Name, Index, Element, Status)** — Insert element

**SearchArray(Name, SearchIndex, Count, SearchElement, SearchComp, FoundElement, Status)** — Search

---

## Queues

**CreateQueue(Name, Size, Element, Status)** — Create FIFO queue

**DeleteQueue(Name, Status)** — Delete queue

**ClearQueue(Name, Status)** — Empty queue

**PutFirstQueue(Name, Element, Status)** — Insert at front

**PutLastQueue(Name, Element, Status)** — Insert at back

**GetFirstQueue(Name, Element, Status)** — Remove from front

**GetLastQueue(Name, Element, Status)** — Remove from back

**ReadQueue(Name, Number, Element, Status)** — Read without remove

**CurrentQueueSize(Name, Status)** — Returns element count

---

## Time and Duration

### System Time

**SetTime(ActTime, Status)** — Set system clock

**GetTime(ActTime, Status)** — Read system clock

### Time Comparison

**TimeBefore(TR1, TR2, Status)** — True if TR1 < TR2

**TimeRecordBefore(TR1, TR2, Status)** — Compare TimeRecords

**DurationGreaterThan(Dur1, Dur2, Status)** — Compare durations

### Time Arithmetic

**SubTimes(Ti1, Ti2, Dur, Status)** — Time difference

**SubTimeRecords(TR1, TR2, D, Status)** — TimeRecord difference

**SubDurations(Dur1, Dur2, DurOut, Status)** — Duration subtraction

**AddDurations(Dur1, Dur2, DurOut, Status)** — Duration addition

**AddTimeAndDuration(TiIn, Dur, TiOut, Status)** — Add duration to time

**SubDurationFromTime(TiIn, Dur, TiOut, Status)** — Subtract duration

---

## Type Conversions

### Boolean to Integer

**Boolean16ToInteger(BoolRec, Int, Status)** — 16 booleans to int

**Boolean32ToInteger(BoolRec, Int, Status)** — 32 booleans to int

### Integer to Boolean

**IntegerToBoolean16(Int, BoolRec, Status)** — Int to 16 booleans

**IntegerToBoolean32(Int, BoolRec, Status)** — Int to 32 booleans

### Integer Conversions

**IntegerToString(Str, Val, Width, Status)** — Int to string

**IntegerToOctalString(Str, Val, Width, Status)** — Int to octal string

**IntegerToBCD(Int, BCD, Status)** — Int to BCD

**BCDToInteger(BCD, Int, Status)** — BCD to int

### Real Conversions

**RealToString(Str, Val, Width, Fraction, Status)** — Real to string

**StringToReal(Str, Status)** — String to real

**StringToInteger(Str, Status)** — String to integer

### Time Conversions

**StringToTime(Str, TimeFormat, ActTime, Status)** — String to time

**StringToTimeRecord(Str, TimeFormat, TR, Status)** — String to TimeRecord

**StringToDuration(Str, Dur, Status)** — String to duration

**TimeToString(ActTime, TimeFormat, Str, Status)** — Time to string

**TimeToTimeRecord(ActTime, TR, Status)** — Time to TimeRecord

**TimeToCalendarRecord(ActTime, CR, Status)** — Time to CalendarRecord

**TimeRecordToString(TR, TimeFormat, Str, Status)** — TimeRecord to string

**TimeRecordToTime(TR, ActTime, Status)** — TimeRecord to time

**DurationToString(Dur, Str, Status)** — Duration to string

**DurationToDurRec(Dur, DRec, Status)** — Duration to DurationRecord

**DurRecToDuration(DRec, Dur, Status)** — DurationRecord to duration

**FDurationToString(Dur, Format, Str, Status)** — Formatted duration

---

## ASCII Operations

**CharToASCII(Char, Code)** — Character to ASCII code

**ASCIIToChar(Code, Char)** — ASCII code to character

**StringToASCIIArray(Str, Array, Status)** — Convert string to ASCII array

**ASCIIArrayToString(Array, Str, Status)** — Convert ASCII array to string

### ASCII Codes (Common)
| Code | Character |
|------|-----------|
| 48-57 | 0-9 |
| 65-90 | A-Z |
| 97-122 | a-z |
| 32 | Space |
| 13 | CR |
| 10 | LF |

---

## Window Management

### Operator Windows

**NewWindow(WindowPath, xPos, yPos, xSize, ySize, Status)** — Create window

**DeleteWindow(WindowPath, Status)** — Close window

**ToggleWindow(WindowPath, xPos, yPos, xSize, ySize, Status)** — Create/delete

### Text Editor Windows

**NewEditFile(FilePath, xPos, yPos, xSize, ySize, Status)** — Open text editor

**DeleteEditFile(FilePath, Status)** — Close text editor

**ToggleEditFile(FilePath, xPos, yPos, xSize, ySize, Status)** — Toggle editor

---

## System Management

### User Information

**CurrentUser(UserName, UserClassName)** — Get current user info

**LoggedIn(UserName)** — True if user is logged in

### Operator Interaction

**OperatorInteraction(Tag, Severity, Class, Description, OldVal, NewVal, Status)** — Log interaction

**SystemCommand(Command, Status)** — Execute system command

### Program Control

**SetShowProgram(Enable)** — Enable/disable program display

**GetPrivilegeFlag()** — Check if privilege active

**ResetPrivilegeFlag()** — Clear privilege flag

---

## System Variables

### Assign System Variables

**AssignSystemBoolean(SysVarId, Value, Status)**

**AssignSystemInteger(SysVarId, Value, Status)**

**AssignSystemReal(SysVarId, Value, Status)**

**AssignSystemString(SysVarId, Value, Status)**

### Read System Variables

**SystemBoolean(SysVarId, Status)**

**SystemInteger(SysVarId, Status)**

**SystemReal(SysVarId, Status)**

**ReadSystemString(SysVarId, Value, Status)**

### Common System Variables
| ID | Name | Type | Description |
|----|------|------|-------------|
| 1 | SysTime | Time | System time |
| 2 | ScanTime | Real | Current scan time |
| 3 | CycleCount | Integer | Cycle counter |

---

## Random Numbers

**SetSeed(Seed, Generator)** — Initialize random generator

**RandomSeed(Generator)** — Get current seed

**RandomRect(Generator)** — Rectangular distribution (0.0 to 1.0)

**RandomNorm(Generator)** — Normal distribution (mean 0, std 1)

---

## File Handling

**MoveFile(Source, Destination, Delete, AsyncOp, DebugStatus)** — Move/copy file

**CreateWriteFile(FileRef, FileName, AsyncOp, DebugStatus)** — Create new file

**OpenWriteFile(FileRef, FileName, AsyncOp, DebugStatus)** — Open for writing

**OpenReadFile(FileRef, FileName, AsyncOp, DebugStatus)** — Open for reading

**CloseFile(FileRef, AsyncOp, DebugStatus)** — Close file

**DeleteFile(FileName, AsyncOp, DebugStatus)** — Delete file

**FileExists(FileName, AsyncOp, DebugStatus)** — Check existence

**WriteString(FileRef, String, AsyncOp, DebugStatus)** — Write string

**WriteLine(FileRef, String, AsyncOp, DebugStatus)** — Write line with CR/LF

**ReadLine(FileRef, String, AsyncOp, DebugStatus)** — Read line

### Print File

**PrintFile(PrinterSysId, PrinterName, RemoteFile, LocalFile, DeleteLocal, AsyncOp, DebugStatus)** — Print text file

---

## COMLI Modem

**ComliDial(ComliMasterRef, PhoneNo, AsyncOp, DebugStatus)** — Dial remote

**ComliHangUp(ComliMasterRef, AsyncOp, DebugStatus)** — Disconnect

---

## MMS File Transfer

**GetRemoteFile(RemoteSysId, RemoteFile, LocalFile, AsyncOp, DebugStatus)** — Download file

**PutRemoteFile(RemoteSysId, RemoteFile, LocalFile, AsyncOp, DebugStatus)** — Upload file

**GetRemoteSingleFile(...)** — Download single file

**PutRemoteSingleFile(...)** — Upload single file

---

## Status Codes

### Procedure Status
| Code | Meaning |
|------|---------|
| 0 | OK |
| -1 | General error |
| -2 | Invalid parameter |
| -3 | Timeout |
| -4 | Communication error |
| -5 | File not found |
| -6 | Access denied |

### AsyncOperation Status
| Code | Meaning |
|------|---------|
| 0 | Pending |
| 1 | Done OK |
| -1 | Error |

---

## Best Practices

### String Handling
- Check status after operations
- Respect maximum lengths
- Use appropriate string types

### Time Operations
- Use TimeRecords for components
- Watch for time zone issues
- Duration for intervals

### File Operations
- Always use async operations
- Check AsyncOperation status
- Close files when done
- Handle errors gracefully

### Variable Distribution
- Use WriteVar/ReadVar for small data
- Use WriteLongVar for large records
- Always check status

### Arrays and Queues
- Check bounds
- Handle full queue conditions
- Delete when done to free memory
