# MIDI Router Roadmap

## Core

-   [x] Routing Engine
-   [x] Processor Engine
-   [x] Split Processor

------------------------------------------------------------------------

## MIDI

### Processors

-   [x] Split Processor
-   [ ] Channel Filter
-   [ ] Message Filter
-   [ ] Channel Remap
-   [ ] MIDI Clone (Fan-out)
-   [ ] Transpose
-   [ ] Velocity Curve

### Real-Time

-   [ ] MIDI Clock
-   [ ] Start
-   [ ] Continue
-   [ ] Stop
-   [ ] Active Sense
-   [ ] Reset

### Input Filters (Ignore)

-   [ ] Control Change (CC)
-   [ ] Program Change (PC)
-   [ ] SysEx
-   [ ] MIDI Clock
-   [ ] Transport (Start / Continue / Stop)
-   [ ] Active Sense
-   [ ] Reset

### System

-   [ ] SysEx Support

------------------------------------------------------------------------

## Web UI

-   [ ] Ignore Section
-   [ ] Processor Chain Editor
-   [ ] Real-Time Configuration (if needed)
-   [ ] Presets
-   [ ] Import / Export Configuration

------------------------------------------------------------------------

## Customer Tasks

### ✅ MIDI Split

Implemented.

------------------------------------------------------------------------

### 🔜 MIDI Processor Chain

``` text
Input
  │
  ▼
Channel Filter
  keep CH16
  │
  ▼
Message Filter
  keep Notes only
  │
  ▼
MIDI Clone
  CH16 → CH1
       → CH2
       → CH3
       → CH4
  │
  ▼
Routing Engine
  │
  ▼
OUT1
```

This task is implemented using Processors only:

1.  Keep only Channel 16.
2.  Keep only Note On / Note Off.
3.  Clone Channel 16 to Channels 1--4.
4.  Route all cloned messages to the same output.

No dedicated merge processor is required. The Routing Engine naturally
serializes all generated MIDI messages to the selected output.

------------------------------------------------------------------------

## Long-Term Vision

The project evolves into a modular MIDI Processor platform.

``` text
Input
  │
  ▼
Input Filters
  │
  ▼
Processor Engine
  ├── Channel Filter
  ├── Message Filter
  ├── Split
  ├── Transpose
  ├── Velocity Curve
  ├── Channel Remap
  └── MIDI Clone
  │
  ▼
Routing Engine
  │
  ▼
Outputs
```

New functionality should preferably be implemented as a new Processor
rather than modifying existing ones.
