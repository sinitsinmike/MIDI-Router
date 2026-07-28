# Firmware Architecture

## Overview

```
          MIDI UART RX
                │
                ▼
      +-------------------+
      | Processor Engine  |
      +-------------------+
                │
                ▼
      +-------------------+
      |  Routing Engine   |
      +-------------------+
                │
                ▼
          MIDI UART TX
```

---

# Design Principles

- Routing never modifies MIDI messages.
- Processors never perform routing.
- Processors never access UART directly.
- Processors never read or write configuration files.
- Configuration is loaded only during startup or USB configuration commands.
- MIDI processing must not allocate dynamic memory.

---

# Routing Engine

Purpose:

Route MIDI messages according to the routing matrix.

Input:

- Input Port
- MIDI Channel

Output:

- One or more Output Ports

The Routing Engine:

- does not modify channel
- does not modify note
- does not filter messages
- does not duplicate messages

---

# Processor Engine

Purpose:

Modify MIDI messages before routing.

Current processor order:

1. Split
2. CC Filter
3. Duplicate

Future processors:

- Transpose
- Velocity Curve
- Program Change Filter
- Clock Filter
- SysEx Filter

Every processor:

- receives one MIDI message
- may modify it
- may discard it
- may emit multiple messages
- must not know about Routing

---

# Configuration Files

routing_matrix.json

split_rules.json

cc_filter.json

duplicate_rules.json

Each file is independent.

---

# USB Protocol

Routing

- GETROUTE
- SETROUTE

Split

- GETSPLIT
- SETSPLIT

CC Filter

- GETFILTER
- SETFILTER

Duplicate

- GETDUP
- SETDUP

Diagnostics

- GETMIDIRT

Compatibility aliases

- GET → GETROUTE
- SET → SETROUTE
- MIDIRT → GETMIDIRT

---

# Runtime Rules

During MIDI processing it is forbidden to:

- allocate new lists
- allocate new dictionaries
- parse JSON
- access filesystem
- perform blocking operations

All configuration must already be loaded into RAM.

---

# Performance Goals

- Deterministic processing time
- No garbage collection during MIDI processing
- Minimal latency
- Minimal jitter

---

# Project Philosophy

Simple.

Deterministic.

Modular.

Every new feature should be implemented as a new Processor whenever possible.

Routing Engine should remain unchanged.


# Message Ownership

During processing there is only one active MIDI message.

Processors should modify the existing message whenever possible.

Only Duplicate is allowed to emit additional messages.

No processor should retain references to a message after returning.