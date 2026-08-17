# MIDI Router Roadmap

This document describes the current project state and future direction.

The older roadmap terminology (`Duplicate`, `GETDUP`, `GETFILTER`, `GETROUTE`) is historical. The current firmware uses **Note Clone**, **MIDI Settings**, and the current USB commands documented below.

---

# Current State

## v1.0 — Routing Foundation

- [x] Routing Matrix
- [x] WebSerial UI
- [x] `routing_matrix.json`
- [x] generated `routing_table.py`

## v1.1 — Keyboard Split

- [x] Split configuration
- [x] `GETSPLIT` / `SETSPLIT`
- [x] Split UI
- [x] Split Engine
- [x] Input selection
- [x] MIDI channel selection
- [x] Low/high note zones
- [x] Forced output selection
- [x] Optional output MIDI channel
- [x] Split state for related channel messages

## v1.2 — Note Clone

- [x] Note Clone configuration
- [x] `GETNOTECLONE` / `SETNOTECLONE`
- [x] Note Clone UI
- [x] Note Clone Engine
- [x] Multiple output MIDI channels
- [x] Note On / Note Off cloning
- [x] Global Note Clone enable/disable

## v2.0 — Firmware / UI Synchronization

- [x] `midi_settings.json`
- [x] `GETSETTINGS` / `SETSETTINGS`
- [x] Global MIDI Clock enable/disable
- [x] Global MIDI CC enable/disable
- [x] UI synchronization for global MIDI settings

## v2.1 — Current UI

- [x] Enable Note Clone
- [x] Enable MIDI Clock
- [x] Enable MIDI CC
- [x] Unified Save / Load
- [x] Routing Matrix + Split + Clone + MIDI Settings in one UI
- [x] Persistent JSON configuration
- [x] Documented processor/routing priority

---

# Current MIDI Processing

## Keyboard Split

Split can:

- select an input
- select a MIDI channel
- divide notes into low/high zones
- force each zone to an output
- optionally change the output MIDI channel

## Note Clone

Note Clone can:

- select an input
- select a MIDI channel
- select an output
- generate Note On / Note Off on multiple output MIDI channels

A matching enabled Clone rule handles the matching note event through its explicit clone destinations instead of normal routing.

## Global MIDI CC

Current:

- [x] Global `Enable MIDI CC`
- [x] Blocks all Control Change (`0xB0`) messages when disabled
- [x] Pitch Bend is independent
- [x] Aftertouch is independent

## Global MIDI Real-Time

Current:

- [x] Global `Enable MIDI Clock`
- [x] Clock (`0xF8`)
- [x] Start (`0xFA`)
- [x] Continue (`0xFB`)
- [x] Stop (`0xFC`)

The UI currently exposes one global Real-Time switch.

---

# Routing / Processor Priority

```text
MIDI Input
    │
    ▼
MIDI Decoder
    │
    ▼
Global filters
    ├── MIDI CC
    └── MIDI Real-Time
    │
    ▼
Processors
    ├── Keyboard Split
    └── Note Clone
    │
    ▼
Routing Matrix
    │
    ▼
MIDI Outputs
```

For a normal event:

```text
Input → Decoder → Filters/Processors → Routing Matrix → Output(s)
```

For a Split event with an explicit destination:

```text
Input → Decoder → Split → Forced Output
```

For a Clone event:

```text
Input → Decoder → Clone → Explicit Clone Output/Channel(s)
```

A processor-forced or processor-generated destination may bypass normal Routing Matrix destination selection.

Therefore:

```text
Routing Matrix:
IN1 → OUT2 = OFF

Note Clone:
IN1 → OUT2 / CH1+CH2
```

still sends the Clone event to OUT2.

This behavior is intentional and must remain documented.

---

# Configuration Files

```text
routing_matrix.json
routing_table.py
split_rules.json
note_clone.json
midi_settings.json
```

`routing_table.py` is generated from the Routing Matrix.

`midi_settings.json` currently contains:

```json
{
  "version": 1,
  "clock_enabled": true,
  "cc_enabled": true,
  "note_clone_enabled": true
}
```

---

# USB Protocol

## Routing

```text
GET
SET <json>
MIDIRT
```

## Split

```text
GETSPLIT
SETSPLIT <json>
```

## Note Clone

```text
GETNOTECLONE
SETNOTECLONE <json>
```

## MIDI Settings

```text
GETSETTINGS
SETSETTINGS <json>
```

---

# Next Planned Version

## CC Filtering Per Input

- [ ] Per-input CC enable/disable
- [ ] Keep global CC as a master switch if useful
- [ ] Evaluate optional per-channel filtering
- [ ] Evaluate optional individual CC-number filtering

Preferred model:

```text
Global CC
    │
    ├── Input 1 → ON
    ├── Input 2 → OFF
    ├── Input 3 → ON
    └── ...
```

Per-input is preferred before per-output because the first requirement is to decide which CC messages are accepted from each MIDI source.

Per-output CC filtering remains optional and should only be added for a concrete destination-specific use case.

---

# Future Real-Time Filtering

- [ ] Separate Clock filter
- [ ] Separate Start filter
- [ ] Separate Continue filter
- [ ] Separate Stop filter
- [ ] Active Sense
- [ ] Reset

Do not split the current global control until there is a real requirement.

---

# Future MIDI Processors

- [ ] Channel Filter
- [ ] Message Filter
- [ ] Channel Remap
- [ ] Transpose
- [ ] Velocity Curve
- [ ] Program Change Filter
- [ ] SysEx Filter
- [ ] Generic Processor Chain

---

# Future UI

- [ ] Per-input Filter / Ignore section
- [ ] Processor Chain Editor
- [ ] Real-Time detailed configuration
- [ ] Presets
- [ ] Import / Export
- [ ] Configuration validation / warnings
- [ ] Diagnostics / MIDI monitor improvements

---

# Long-Term Vision

```text
Input
  │
  ▼
MIDI Decoder
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
  └── Note Clone
  │
  ▼
Routing Engine
  │
  ▼
Outputs
```

The Generic Processor Chain should be introduced only when it solves a concrete requirement.

Stable existing features should not be rewritten merely for abstraction.
