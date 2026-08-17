# MIDI Router Changelog

## v2.1 — Current

### Added

- Unified MIDI Settings configuration in `midi_settings.json`.
- WebSerial commands:
  - `GETSETTINGS`
  - `SETSETTINGS <json>`
- Global **Enable Note Clone**.
- Global **Enable MIDI Clock**.
- Global **Enable MIDI CC**.
- UI synchronization for Routing Matrix, Split, Note Clone, and MIDI Settings.
- Persistent configuration loading/saving for current features.
- Explicit documentation of processor-vs-routing priority.

### MIDI behavior

- `Enable MIDI CC` controls all Channel Voice Control Change messages (`0xB0`).
- Pitch Bend (`0xE0`) is independent of the CC switch.
- Aftertouch is independent of the CC switch.
- `Enable MIDI Clock` currently controls the handled MIDI Real-Time messages as one global switch:
  - Clock (`0xF8`)
  - Start (`0xFA`)
  - Continue (`0xFB`)
  - Stop (`0xFC`)

### Processor behavior

- Keyboard Split can force an output and optionally change the output MIDI channel.
- Note Clone can fan out Note On/Note Off to multiple output MIDI channels.
- Processor-selected destinations can bypass normal Routing Matrix destination selection.
- Normal messages without a processor-forced destination use the Routing Matrix.

### Configuration

Current configuration files:

```text
routing_matrix.json
routing_table.py
split_rules.json
note_clone.json
midi_settings.json
```

Current USB protocol:

```text
GET
SET <json>

GETSPLIT
SETSPLIT <json>

GETNOTECLONE
SETNOTECLONE <json>

GETSETTINGS
SETSETTINGS <json>

MIDIRT
```

---

## v2.0

### Firmware / UI synchronization

- Added `midi_settings.json`.
- Added `GETSETTINGS` / `SETSETTINGS`.
- Added global MIDI Clock enable/disable.
- Added global MIDI CC enable/disable.
- Added UI synchronization for global MIDI settings.

---

## v1.2

### Note Clone

- Added Note Clone configuration.
- Added `GETNOTECLONE` / `SETNOTECLONE`.
- Added Note Clone UI.
- Added Note Clone Engine.
- Added multiple output MIDI channels.
- Added global Note Clone enable/disable.

---

## v1.1

### Keyboard Split

- Added Split configuration.
- Added `GETSPLIT` / `SETSPLIT`.
- Added Split UI.
- Added Split Engine.

---

## v1.0

### Routing foundation

- Added Routing Matrix.
- Added WebSerial UI.
- Added `routing_matrix.json`.
- Added generated `routing_table.py`.

---

# Planned

## Next

### CC filtering per input

- Per-input CC enable/disable.
- Keep the global CC switch as a master switch if it remains useful.
- Evaluate optional per-channel CC filtering.
- Evaluate optional individual CC-number filtering.

Preferred first model:

```text
Global CC
    │
    ├── Input 1 → ON
    ├── Input 2 → OFF
    ├── Input 3 → ON
    └── ...
```

Per-output CC filtering is not the default plan. It should be added only if a concrete routing use case requires it.

## Real-Time filtering

Potential future controls:

- Separate Clock filter.
- Separate Start filter.
- Separate Continue filter.
- Separate Stop filter.
- Active Sense.
- Reset.

Keep the current global `Enable MIDI Clock` behavior until finer granularity is actually needed.

## Future processors

- Channel Filter
- Message Filter
- Channel Remap
- Transpose
- Velocity Curve
- Program Change Filter
- SysEx Filter
- Generic Processor Chain

## Future UI

- Per-input Filter / Ignore section.
- Processor Chain Editor.
- Detailed Real-Time configuration.
- Presets.
- Import / Export.
- Configuration validation and warnings.
- Improved diagnostics / MIDI monitor.

## Long term

Develop the project into a modular MIDI Processor platform without making the Routing Engine unnecessarily complex.

Stable existing functionality should not be rewritten without a concrete requirement.
