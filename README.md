# MIDI Router

A Raspberry Pi Pico MIDI router and processor with a WebSerial UI.

The firmware is intentionally organized so that MIDI decoding, processing, and routing remain separate. The current implementation is pragmatic and stable; the long-term direction is a modular MIDI processor platform.

## Current status

Implemented:

- Routing Matrix
- WebSerial UI
- Keyboard Split
- Note Clone / fan-out
- Global MIDI Clock enable/disable
- Global MIDI CC enable/disable
- Persistent JSON configuration
- Generated `routing_table.py`
- USB configuration protocol

Current configuration files:

```text
routing_matrix.json
routing_table.py
split_rules.json
note_clone.json
midi_settings.json
```

---

# Signal Flow

The important distinction is between **normal routing** and **processor-forced/generated output**.

```text
                 MIDI INPUT PORT
                       │
                       ▼
              ┌─────────────────┐
              │ MIDI Decoder    │
              │ SimpleMIDIDecoder
              └────────┬────────┘
                       │ decoded MIDI event
                       ▼
              ┌─────────────────┐
              │ Processor       │
              │ Engine          │
              └────────┬────────┘
                       │
          ┌────────────┼──────────────────┐
          │            │                  │
          ▼            ▼                  ▼
       Split        Note Clone       CC / Clock
          │            │                  │
          │            ├─ generates       ├─ discard
          │            │  clone events    │  or continue
          │            │
          └──────┬─────┘
                 │
                 │ normal event
                 │ with no forced destination
                 ▼
        ┌─────────────────────┐
        │ Routing Engine      │
        │ MIDIRT / Matrix     │
        └──────────┬──────────┘
                   │
          ┌────────┼────────┐
          ▼        ▼        ▼
        OUT 1    OUT 2    OUT ...
```

## The key priority rule

For a **normal MIDI event**:

```text
Input
  → Decoder
  → Filters / processors
  → Routing Matrix
  → Output(s)
```

For a **Split event with an explicit output**:

```text
Input
  → Decoder
  → Split
  → forced output
  → Output
```

The normal Routing Matrix destination selection is not used for that processor-forced destination.

For a **Note Clone event**:

```text
Input
  → Decoder
  → Note Clone
  → generated Note events
  → explicitly selected clone output/channel(s)
```

The current Note Clone implementation handles the matching note event through the clone destinations instead of normal routing.

This means that disabling an output in the Routing Matrix does **not** automatically disable an explicitly configured Split or Note Clone destination.

That behavior is intentional and must be kept clear in the UI.

---

# Priority and Ownership

The current practical priority is:

```text
1. MIDI Decoder
   ↓
2. Global filters
   - MIDI Clock
   - MIDI CC
   ↓
3. Special processors
   - Keyboard Split
   - Note Clone
   ↓
4. Normal Routing Matrix
   ↓
5. MIDI Output
```

There is an important exception: Split and Note Clone may produce an explicit destination. When they do, that destination has priority over normal Routing Matrix destination selection for that event.

### What each layer owns

| Layer | Owns | Does not own |
|---|---|---|
| Decoder | MIDI byte → event | routing, configuration |
| CC/Clock filters | discard/allow message classes | destination |
| Split | note-zone decision, optional output/channel remap | normal routing |
| Note Clone | fan-out and clone channels/output | normal routing |
| Routing Matrix | normal source/channel → output mapping | processing/filtering |
| UART TX | physical transmission | routing decisions |

---

# Configuration

## `routing_matrix.json`

The Web UI Routing Matrix.

Defines normal routing by input, MIDI channel, and output.

## `routing_table.py`

Generated from `routing_matrix.json`.

Format:

```text
[MIDI CH, MIDI CMD, source port, destination port]
```

The firmware loads this table into `MIDIRT`.

## `split_rules.json`

Keyboard Split rules.

A split can select:

- input
- MIDI channel
- split note
- low/high output
- low/high MIDI channel

## `note_clone.json`

Note Clone rules.

A rule can select:

- input
- MIDI channel
- output
- one or more output MIDI channels

The global enable state is not stored here.

## `midi_settings.json`

Global feature switches:

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

## Routing Matrix

```text
GET
SET <json>
```

`SET` stores the matrix, generates `routing_table.py`, reloads it, and synchronizes the saved matrix.

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

## Diagnostics

```text
MIDIRT
```

The browser UI communicates with the firmware through these commands. The UI does not directly edit Pico files.

---

# Web UI

Current controls:

- Routing Matrix
- Keyboard Split
- Note Clone
- MIDI Settings

MIDI Settings currently contains:

- **Enable Note Clone**
- **Enable MIDI Clock**
- **Enable MIDI CC**

Current semantics:

- Enable MIDI CC controls all `Control Change` messages (`0xB0`) globally.
- Pitch Bend (`0xE0`) is independent of the CC switch.
- Aftertouch is independent of the CC switch.
- Enable MIDI Clock currently controls the Real-Time messages handled by the decoder as one global switch.

---

# Runtime Rules

During MIDI processing:

- do not parse JSON
- do not access the filesystem
- do not perform blocking USB operations
- do not reload configuration
- do not depend on browser/UI state

Configuration is loaded into RAM during startup or USB configuration commands.

---

# Future Roadmap

## Near term

- [ ] CC filtering per input
- [ ] Decide whether CC filtering also needs MIDI-channel granularity
- [ ] Evaluate separate Clock / Start / Continue / Stop controls
- [ ] Improve diagnostics and status reporting
- [ ] Document processor/routing interactions in the UI

### CC filtering direction

The preferred first design is:

```text
Input 1 → CC allowed
Input 2 → CC blocked
Input 3 → CC allowed
```

Per-input filtering is more natural than per-output filtering because the filter describes what is accepted from a MIDI source.

Possible later granularity:

```text
Input
  └── MIDI Channel
       └── CC / Message Type
```

Per-output CC filtering should only be added if a real use case requires controlling different CC sets for different destinations.

## Medium term

- [ ] Channel Filter
- [ ] Message Filter
- [ ] Channel Remap
- [ ] Transpose
- [ ] Velocity Curve
- [ ] Program Change Filter
- [ ] More precise Real-Time filtering
- [ ] SysEx filtering/support
- [ ] Presets
- [ ] Import/export configuration

## Long term

A generic Processor Chain may evolve toward:

```text
INPUT
  │
  ▼
Decoder
  │
  ▼
Filters
  │
  ▼
Processors
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
OUTPUTS
```

The generic chain should only be introduced when it solves a concrete requirement. Stable current features should not be destabilized merely for abstraction.

---

# Design Philosophy

- Simple
- Deterministic
- Modular
- Stable before abstract
- Processor logic should not own routing
- Routing should remain simple
- New features should be isolated whenever practical
