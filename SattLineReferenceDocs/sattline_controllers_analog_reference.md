# SattLine Controllers and Analog Control Reference

## Signal Flow

### Data Type: RealSignal
Standard analog signal type:
```
RealSignal = record
  Value: Real;        -- Signal value
  Quality: Integer;   -- Signal quality (0 = good)
end;
```

### Data Type: SignalPar
Connection parameters:
```
SignalPar = record
  Enable: Boolean;    -- Signal enabled
  Source: String;     -- Source identifier
end;
```

### Backtracking
Controllers send backward signals for:
- Bumpless transfer (tracking)
- Anti-reset windup
- Mode switching

---

## Analog Input Handling

### AnalogInRealS (ControlLib)
- Scales raw I/O to engineering units
- Parameters: RawMin, RawMax, EngMin, EngMax
- Outputs: Scaled value + quality

### CounterInRealS
- Converts pulse counts to analog values
- Pulse/quantity conversion factor
- Frequency or totalizing modes

### MassFlowRealS
- Differential pressure flow compensation
- Temperature/pressure compensation
- Square root extraction

### MMSToRealS / RealStoMMS
- Convert between RealSignal and MMS variables
- For distributed analog signals

---

## Filtering and Calculations

### FilterRealS
First-order filter:
- Time constant (seconds)
- Reduces noise
- Smooths transitions

### IntegratorRealS
- Integrates input over time
- Hold and reset inputs
- Limit outputs

### DifferentiatorRealS
- Rate of change calculation
- Time constant for smoothing
- Noise-sensitive, use with filter

### ChangeRateLimRealS
- Limits rate of change
- Separate rise/fall limits
- Prevents abrupt changes

### StaticFunctionRealS / StaticFunction2RealS
- 10-point piecewise linear function
- X-Y table interpolation
- For linearization or characterizers

---

## Mathematical Operations

### AddRealS / MultRealS
- Multiple input addition/multiplication
- Configurable gains per input
- Quality propagation

### SqrtRealS
- Square root extraction
- For flow calculations
- Handles negative inputs

### LimiterRealS
- Hard limits on output
- Min/max clamping

### MaxRealS / MinRealS
- Maximum/minimum selectors
- Multiple inputs (up to 8)
- Quality handling

---

## PID Controllers

### Pid (ControlLib)

**Control Modes:**
| Mode | Description |
|------|-------------|
| 0 | Auto — Normal PID control |
| 1 | Manual — Operator sets output |
| 2 | Tracking — Follow external signal |
| 3 | Initialization — Startup mode |

**Parameters (PidPar):**
```
K: Real;              -- Gain
Ti: Real;             -- Integral time (seconds)
Td: Real;             -- Derivative time (seconds)
Tf: Real;             -- Filter time (seconds)
Auto: Boolean;        -- Auto/manual mode
SP: Real;             -- Setpoint
OutMin, OutMax: Real; -- Output limits
```

**Features:**
- Anti-reset windup
- Bumpless transfer
- PV tracking
- Derivative on PV or error
- Feedforward input

### Cascade Control
- Master/slave configuration
- `CascadeLoopMaster` — Coordinates cascade
- Automatic bumpless switching

### Three-Step Controller
- For motorized valves
- Pulse outputs (up/down)
- Position feedback or time-based
- Dead zone configurable

---

## Controller Features

### Autotuning (RelayPidTuner)
- Automatic PID parameter calculation
- Relay feedback method
- Step response analysis
- Safe tuning procedure

### Gain Scheduling
- Multiple PID parameter sets
- Scheduled by external variable
- For non-linear processes
- Up to 8 parameter sets

### Adaptive Control

**Feedback Adaptive (AdaptivePid):**
- Automatic gain adjustment
- Process gain estimation
- Robust to process changes

**Feedforward Adaptive:**
- Adapts to measured disturbances
- Lead/lag compensation

### Stiction Compensation
- Detects valve oscillation
- Adds dither signal
- Configurable amplitude/frequency
- For sticky valves

---

## Fuzzy Control (FuzzyLib)

### FuzzyControl1Master / FuzzyControl2Master
- Linguistic rule-based control
- IF-THEN rule structure
- Membership functions

### Components

**FuzzySpPvIn / FuzzyPvIn:**
- Setpoint/process variable input
- Fuzzification

**FuzzyOut:**
- Defuzzification
- Output scaling

**FuzzyStrategyMaster:**
- Rule evaluation
- Inference engine

### Data Types
```
FuzzySpPvInPar: SP/PV input parameters
FuzzyPvInPar: PV input parameters
FuzzyOutPar: Output parameters
MembershipPar: Membership function definition
FuzzyStrategyType: Rule base
```

---

## Analog Outputs

### AnalogOutRealS
- Scales to raw I/O range
- Limit checking
- Quality handling

### AnalogOutStCompRealS
- Output with stiction compensation
- Dither signal addition
- Configurable pulse characteristics

### DigitalOutRealS
- Three-step motor control
- Pulse width modulation
- Position feedback option

---

## Alarms

### Alarm4RealS
- Four-level alarming (HH, H, L, LL)
- Hysteresis
- Time delay
- Deadband

### RelativeAlarm2
- Alarm relative to reference signal
- Two levels (H, L)
- Adjustable hysteresis

### Deviation Alarms
- SP-PV deviation monitoring
- Controller built-in
- Separate high/low limits

---

## Manual/Auto Handling

### ManualAutoRealS
- Manual override station
- Tracking in manual
- Bumpless transfer

### SelectorMasterRealS / SelectorSlaveRealS
- Automatic/Manual selection
- Priority logic
- Multiple inputs

### TrackingRealS
- Force signal to track another
- Override control
- Bumpless return

---

## Signal Tapping

### TapRealS
- Read signal value
- Non-intrusive
- For monitoring/logging

### TapRealFromRealS
- Extract Real from RealSignal
- For calculations

### RealToRealS / RealSToReal
- Type conversion
- Quality handling

---

## Split Range Control

### SplitRangeRealS
- Single input to multiple outputs
- Sequential operation
- Overlap/gap configurable
- For multiple actuators

### CommonRangeRealS
- Multiple inputs to single output
- Select by priority or logic
- For redundant sensors

---

## Configuration Best Practices

### PID Tuning
1. Start with conservative gains (K=1, Ti=60, Td=0)
2. Increase K until oscillation, then back off
3. Set Ti to oscillation period/1.5
4. Add Td = Ti/4 if needed
5. Use autotuner as starting point

### Signal Handling
- Always filter noisy signals
- Check quality bits
- Handle bad quality gracefully
- Scale at I/O module

### Cascade Control
- Slave 3-5x faster than master
- Tune slave first (local SP)
- Then tune master
- Use PV tracking in slave

### Output Limiting
- Set limits to physical range
- Allow small overshoot margin
- Use rate limiting for slow actuators

---

## Control Strategies

### Flow Control
- Fast loop (1-2 second cycle)
- PI control (often no derivative)
- Square root for orifice meters

### Level Control
- Slow loop (10-60 second cycle)
- P or PI control
- Watch for resonance with upstream

### Temperature Control
- Slow loop (30-300 second cycle)
- PID control
- Consider cascade with flow inner loop

### Pressure Control
- Medium speed (5-30 second cycle)
- PI control
- Watch for interaction with flow

### pH Control
- Highly non-linear
- Consider gain scheduling
- Slow response, large dead time
