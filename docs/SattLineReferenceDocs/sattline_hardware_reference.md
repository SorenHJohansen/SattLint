# SattLine Hardware Reference

## Control Systems

### SattLine 200 (SL200)
- DIN rail mounting
- Distributed I/O system
- Modular architecture
- NNbus for I/O communication

### CPU80
- DIN rail mounting
- Higher performance than SL200
- Compatible I/O
- Enhanced communication

### System Components

**Central System:**
- CPU module
- Power supply
- Communication modules
- BIAL (Alert interface)

**Remote I/O:**
- RACN (remote adapter)
- RANN (rack adapter)
- DIN rail I/O units
- Distributed nodes

---

## I/O Systems

### Series 200 I/O

**Digital I/O:**
- DI8/DI16 — Digital input modules
- DO8/DO16 — Digital output modules
- Relay outputs available

**Analog I/O:**
- AI4/AI8 — Analog input (4-20mA, 0-10V)
- AO2/AO4 — Analog output
- 12-bit or 16-bit resolution

**Counter I/O:**
- CI2/CI4 — Counter input
- Frequency measurement
- Pulse counting

**Special Modules:**
- Temperature (thermocouple, RTD)
- Position (encoder)
- Communication (serial, fieldbus)

### Rack I/O

**RANN** — Rack adapter for local I/O
- 19" rack mounting
- Up to 16 I/O slots
- NNbus connection

**RACN** — Rack adapter for remote I/O
- Extended distance
- Fiber optic option
- Same I/O cards as RANN

### Addressing

**Central I/O:**
```
Adapter.Module.Channel
0.4.15 — Adapter 0, module 4, channel 15
```

**Remote I/O:**
```
Bus.Node.Module.Channel
15.45.4.15 — Bus 15, node 45, module 4, channel 15
```

**Note:** Series 200 Rack I/O uses octal numbering

---

## Communication Hardware

### Network Interfaces

**Ethernet:**
- 10/100 Mbps
- TCP/IP stack
- MMS over TCP/IP
- Standard RJ45

**Serial Ports:**
- RS-232 for programming
- RS-485 for COMLI
- RS-422 for SattBus

### Control Network
- Dedicated industrial network
- Redundancy support
- Deterministic timing
- MMS protocol

### Fieldbus

**SattBus:**
- ABB proprietary
- Master-slave
- Up to 31 devices
- Various physical layers

**Foundation Fieldbus:**
- H1 (31.25 kbps)
- HSE (100 Mbps)
- Function blocks

**Profibus:**
- DP (distributed I/O)
- PA (process automation)
- Master-slave

**DeviceNet:**
- CAN-based
- Up to 64 nodes
- 125-500 kbps

---

## Operator Stations

### Hardware Components

**Workstation:**
- Industrial PC
- Windows operating system
- SattLine software

**Display:**
- Industrial monitors
- Touch screen option
- Various sizes (15"-24")

**Keyboard:**
- Industrial keyboard
- Function keys
- Emergency stop

**Pointing Devices:**
- Trackball
- Touchpad
- Touchscreen

### Redundancy

**Server Redundancy:**
- Primary/backup servers
- Automatic failover
- Shared storage

**Network Redundancy:**
- Dual network paths
- Ring topology
- Automatic switchover

---

## Installation

### Environmental Requirements

**Temperature:**
- Operating: 0°C to +55°C
- Storage: -20°C to +70°C

**Humidity:**
- 5% to 95% non-condensing

**Vibration:**
- IEC 60068-2-6
- Industrial environments

**EMC:**
- IEC 61131-2
- CE marking

### Power Supply

**SL200:**
- 24 VDC
- Redundant option
- Battery backup for memory

**Rack I/O:**
- 24 VDC or 120/240 VAC
- Power calculation per rack
- Fusing requirements

### Grounding
- Single point ground
- Shield grounding
- Isolation requirements
- Surge protection

---

## Cabling

### I/O Cabling

**Digital I/O:**
- Twisted pair
- Shielded for noise immunity
- 0.5-1.5 mm²

**Analog I/O:**
- Shielded twisted pair
- Separate from power
- 0.5-1.0 mm²

**Network:**
- Cat 5e or better
- Shielded in industrial areas
- Proper termination

### Cable Routing
- Separate trays for power/signal
- Cross at 90°
- Avoid loops
- Label clearly

---

## Hardware Configuration

### Hardware Builder
- Graphical configuration tool
- Module selection
- Address assignment
- Parameter setting

### Configuration Steps
1. Select control system type
2. Add I/O modules
3. Configure addresses
4. Set parameters
5. Validate configuration

### Download
- Compile configuration
- Download to controller
- Verify I/O
- Test signals

---

## Maintenance

### Preventive Maintenance
- Visual inspection
- Connection tightening
- Filter cleaning
- Backup verification

### Diagnostics
- LED indicators
- System diagnostics
- I/O status
- Communication status

### Replacement
- Hot-swap where supported
- Configuration preservation
- Spare parts inventory
- Replacement procedure

---

## Safety

### Safety Standards
- IEC 61508 (functional safety)
- IEC 61511 (process safety)
- SIL ratings
- Safety PLCs

### Safety I/O
- Safety digital inputs
- Safety digital outputs
- Certified modules
- Redundant channels

### Emergency Stop
- Hardwired E-stop
- Safety relays
- Two-channel
- Monitored

---

## Specifications Summary

### SL200 Controller
| Parameter | Specification |
|-----------|---------------|
| Scan time | 10 ms typical |
| I/O capacity | 1000+ points |
| Memory | 1-8 MB |
| Communication | Ethernet, serial |

### CPU80 Controller
| Parameter | Specification |
|-----------|---------------|
| Scan time | 5 ms typical |
| I/O capacity | 2000+ points |
| Memory | 8-32 MB |
| Communication | Ethernet, multiple serial |

### Analog Input
| Parameter | Specification |
|-----------|---------------|
| Ranges | 4-20mA, 0-10V, ±10V |
| Resolution | 12 or 16 bit |
| Accuracy | ±0.1% |
| Isolation | Channel-to-channel |

### Analog Output
| Parameter | Specification |
|-----------|---------------|
| Ranges | 4-20mA, 0-10V |
| Resolution | 12 bit |
| Accuracy | ±0.2% |
| Load | 750Ω (current) |

---

## Best Practices

### Design
- Size for 20% spare I/O
- Use standard modules
- Plan for expansion
- Document thoroughly

### Installation
- Follow manufacturer guidelines
- Use qualified personnel
- Test before startup
- Document as-built

### Maintenance
- Regular inspection schedule
- Keep spares on-site
- Train maintenance staff
- Update documentation
