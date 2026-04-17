# SattLine I/O and Communication Reference

## I/O Connection

### I/O Address Format
Addresses use dot-notation: `bus.node.module.channel`
- Example central I/O: `1.4.15`
- Example remote I/O: `15.45.4.15`
- Octal numbering for Series 200 Rack I/O

### I/O Data Types
| Type | Description |
|------|-------------|
| `DigitalIn` | Boolean input signals |
| `DigitalOut` | Boolean output signals |
| `AnalogIn` | Real input signals (4-20mA, 0-10V) |
| `AnalogOut` | Real output signals |
| `CounterIn` | Pulse/frequency inputs |

### I/O Connection Principles
- Each I/O output can only be written from one program
- I/O from one control system should not be used in programs on different systems
- Direct I/O addresses used for simple connections
- Structured I/O types (`IO_PlantType`) for complex plant devices

---

## I/O Libraries

### SL200Lib / SL800Lib
Modules for SattLine 200/800 series I/O:
- `DigitalInBool` / `DigitalOutBool` — Single digital I/O
- `AnalogInReal` / `AnalogOutReal` — Single analog I/O
- `CounterIn` — Pulse counter inputs
- Block modules for 8/16/32 channel configurations

### Rack I/O Libraries
Modules for rack-based I/O systems:
- `RackDigitalIn8` / `RackDigitalOut8`
- `RackAnalogIn4` / `RackAnalogOut4`
- `RackCounterIn2`

### Alert I/O (SL200AlertIoLib)
Interface to Alert I/O systems via BIAL units:
- `AlertDigitalIn` / `AlertDigitalOut`
- `AlertAnalogIn` / `AlertAnalogOut`

### SattTop / Altop Libraries
For valve control systems:
- `SattTopChannel` / `AltopChannel`
- Serial communication based

---

## Network Communication

### MMS (Manufacturing Message Specification)
Standard protocol for SattLine network communication:
- Variable exchange between systems
- Journal access (read/write)
- File transfer
- Client-server architecture

### INCA (Industrial Communication Architecture)
ABB proprietary communication stack:
- TCP/IP stack for Control Network
- Routing between networks
- Redundancy support

### System Identity
Format: `system_type.network_address`
- Example: `ws.10.0.0.5` (workstation)
- Example: `cs.10.0.0.1` (control system)

### Routing
- Router modules for cross-network communication
- Default routing rules auto-configure local systems
- Manual routing entries for remote access

---

## PLC Communication

### COMLI Protocol
Master-slave communication protocol:
- Point-to-point or multidrop
- Serial channels (RS-232/RS-485)
- Telegram-based messaging

### COMLI Libraries

**Comli1Lib** — Master communication:
- `TelegramBoxMaster` — Message container
- `ComliMasterChannel` — Channel handler
- `ComliSetTimeAndDate` — Time sync
- `ComliGetAlarmText` / `ComliSendAlarmAck` — Alarm handling

**Comli2Lib / Comli5Lib** — Variable access:
- `ComliReadBool8` to `ComliReadBool512` — Read boolean arrays
- `ComliReadReg1` to `ComliReadReg32` — Read registers
- `ComliReadScaled1` to `ComliReadScaled32` — Read scaled values
- Corresponding `ComliWrite*` modules

**Comli3Lib** — Record transfer:
- `ComliReadRecord` / `ComliWriteRecord`
- `DataCompareMaster`

**Comli4Lib** — Slave communication:
- `ComliSlaveChannel`
- `ComliSlaveBool` / `ComliSlaveBool8` / `ComliSlaveBool32`
- `ComliSlaveInt` / `ComliSlaveInt8` / `ComliSlaveInt32`

### Siemens 3964R
- Compatible with COMLI physical layer
- Different message format

### SattBus
ABB fieldbus protocol:
- TCP/IP support
- MMS message specification
- Direct variable access

---

## Program External Communication

### MMSVarLib
For external system variable access:
- `MMSVarRead` — Read remote variable
- `MMSVarWrite` — Write remote variable
- `MMSVarSubscribe` — Subscribe to remote variable changes

### Variable Distribution
- Export variables from source system
- Import variables to destination system
- Distribution configuration in program properties

---

## Serial Communication

### SerialLib
Low-level serial communication:
- ASCII string handling
- Text I/O operations
- Printer output

### Serial Channel Configuration
- Baud rate, parity, data bits, stop bits
- Hardware/software handshake
- Local and remote printer support

---

## Communication Best Practices

### Performance
- Keep cycle times reasonable (avoid < 50ms for distributed I/O)
- Buffer history data before network transfer
- Use asynchronous operations for file transfer

### Error Handling
- Check `AsyncOperation` status
- Use `DebugStatus` for diagnostics
- Implement timeout handling
- Monitor communication status variables

### Security
- Firewall between control network and enterprise
- Authentication for remote access
- Encrypted connections where supported
- Limited privilege accounts for operators

---

## Common Data Types

### I/O Connection Types
```
DigitalInType: Boolean signal with status
DigitalOutType: Boolean output with feedback
AnalogInType: Real value with range and status
AnalogOutType: Real output with limits
CounterInType: Integer pulse count
```

### Communication Status
- `AsyncOperation` — Handle for async operations
- `Status` — Operation result (0 = OK, negative = error)
- `DebugStatus` — Extended error information

---

## System Variables

Communication-related system variables:
- `SysVar_ComliStatus` — COMLI channel status
- `SysVar_NetworkStatus` — Network connection state
- `SysVar_MMSStatus` — MMS service status

---

## Troubleshooting

| Issue | Possible Cause | Solution |
|-------|---------------|----------|
| I/O not updating | Wrong address | Check octal/decimal addressing |
| Communication timeout | Network issue | Check routing, ping test |
| MMS write fails | Wrong system ID | Verify system identity format |
| COMLI errors | Cable/termination | Check RS-485 termination |
| Slow response | High load | Reduce scan rate, optimize code |
