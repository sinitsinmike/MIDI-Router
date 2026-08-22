# =========================================
# file: main.py
# =========================================

import sys
import machine
import rp2
import utime
import ustruct

try:
    import ujson as json
except ImportError:
    import json  # type: ignore

import uselect

import SimpleMIDIDecoder


# ---------- Constants ----------
UART_BAUD = 31250

RX_PIN_BASE = 6
RX_NUM_UARTS = 4
TX_PIN_BASE = 10
TX_NUM_UARTS = 4
HW_NUM_UARTS = 2

NUM_PORTS = HW_NUM_UARTS + RX_NUM_UARTS
NUM_OUTS = HW_NUM_UARTS + TX_NUM_UARTS

ROUTING_TABLE_PATH = "routing_table.py"
MATRIX_PATH = "routing_matrix.json"
SPLIT_PATH = "split_rules.json"
NOTE_CLONE_PATH = "note_clone.json"
MIDI_SETTINGS_PATH = "midi_settings.json"


# ---------- Debug ----------
DEBUG = False


def debug_print(*args):
    if DEBUG:
        print(*args)


# ---------- MIDI Real-Time ----------
MIDI_REALTIME_CLOCK = 0xF8
MIDI_REALTIME_START = 0xFA
MIDI_REALTIME_CONTINUE = 0xFB
MIDI_REALTIME_STOP = 0xFC


# Pre-built one-byte packets avoid allocating a bytes object for every
# MIDI Clock message at runtime.
MIDI_REALTIME_BYTES = tuple(
    ustruct.pack("B", value)
    for value in range(256)
)


# ---------- LED ----------
ledpin = machine.Pin(25, machine.Pin.OUT)


def led_flash():
    ledpin.value(1)
    utime.sleep_ms(60)
    ledpin.value(0)
    utime.sleep_ms(40)


# ---------- Routing table ----------
MIDIRT = []
MIDIDEF = -1

SPLIT_RULES = []
SPLIT_STATE = {}

NOTE_NAMES = {
    "C": 0,
    "D": 2,
    "E": 4,
    "F": 5,
    "G": 7,
    "A": 9,
    "B": 11,
}


def parse_note(text):
    text = text.strip()

    if len(text) < 2:
        raise ValueError("Invalid note")

    name = text[0].upper()

    if name not in NOTE_NAMES:
        raise ValueError("Invalid note")

    semitone = NOTE_NAMES[name]
    pos = 1

    if pos < len(text):
        if text[pos] == "#":
            semitone += 1
            pos += 1
        elif text[pos] == "b":
            semitone -= 1
            pos += 1

    octave = int(text[pos:])
    midi = (octave + 1) * 12 + semitone

    if not 0 <= midi <= 127:
        raise ValueError("Note out of range")

    return midi


def _load_routing_table_py():
    global MIDIRT, MIDIDEF

    ns = {}

    try:
        with open(ROUTING_TABLE_PATH, "r") as f:
            exec(f.read(), ns, ns)

        MIDIRT = ns.get("MIDIRT", [])
        MIDIDEF = int(ns.get("MIDIDEF", -1))

        if not isinstance(MIDIRT, list):
            MIDIRT = []

    except Exception:
        MIDIRT = []
        MIDIDEF = -1


def midiRouter(s_ch, s_cmd, s_src):
    d_dst = []

    for r in MIDIRT:
        try:
            ch, cmd, src, dst = r
        except Exception:
            continue

        if (ch == -1) or (s_ch == ch):
            if (cmd == -1) or (s_cmd == cmd):
                if (src == -1) or (s_src == src):
                    d_dst.append(dst)

    if (not d_dst) and (MIDIDEF != -1):
        d_dst.append(MIDIDEF)

    return d_dst


# ---------- Matrix <-> MIDIRT ----------
def default_matrix():
    return {
        "version": 2,
        "inputs": [
            {
                "channels": [True] + [False] * 16,
                "outputs": [True] * NUM_OUTS,
            }
            for _ in range(NUM_PORTS)
        ],
        "warnings": [],
    }


def _sanitize_matrix(mtx):
    if not isinstance(mtx, dict):
        return default_matrix()

    inputs = mtx.get("inputs")

    if not isinstance(inputs, list) or len(inputs) != NUM_PORTS:
        return default_matrix()

    out = {
        "version": 2,
        "inputs": [],
        "warnings": [],
    }

    for i in range(NUM_PORTS):
        row = inputs[i] if isinstance(inputs[i], dict) else {}

        ch = row.get("channels")
        outs = row.get("outputs")

        if not isinstance(ch, list) or len(ch) != 17:
            ch = [True] + [False] * 16
        else:
            ch = [bool(x) for x in ch[:17]]

        if not isinstance(outs, list) or len(outs) != NUM_OUTS:
            outs = [True] * NUM_OUTS
        else:
            outs = [bool(x) for x in outs[:NUM_OUTS]]

        out["inputs"].append(
            {
                "channels": ch,
                "outputs": outs,
            }
        )

    return out


def compile_midirt_from_matrix(mtx):
    mtx = _sanitize_matrix(mtx)
    midirt = []

    for src, row in enumerate(mtx["inputs"]):
        channels = row["channels"]
        outputs = row["outputs"]

        dsts = [
            d
            for d, on in enumerate(outputs)
            if on
        ]

        if not dsts:
            continue

        if channels[0]:
            for dst in dsts:
                midirt.append([-1, -1, src, dst])
        else:
            for ch in range(1, 17):
                if channels[ch]:
                    for dst in dsts:
                        midirt.append([ch, -1, src, dst])

    return midirt


def decompile_matrix_from_midirt():
    mtx = default_matrix()
    warnings = []

    per_src = [
        {
            "all_dsts": set(),
            "ch_dsts": [set() for _ in range(17)],
            "any_other": False,
        }
        for _ in range(NUM_PORTS)
    ]

    rules = MIDIRT if isinstance(MIDIRT, list) else []

    for r in rules:
        try:
            ch, cmd, src, dst = r
        except Exception:
            continue

        try:
            src = int(src)
            dst = int(dst)
            ch = int(ch)
            cmd = int(cmd)
        except Exception:
            continue

        if not (0 <= src < NUM_PORTS and 0 <= dst < NUM_OUTS):
            continue

        if cmd != -1:
            per_src[src]["any_other"] = True
            continue

        if ch == -1:
            per_src[src]["all_dsts"].add(dst)

        elif 1 <= ch <= 16:
            per_src[src]["ch_dsts"][ch].add(dst)

        else:
            per_src[src]["any_other"] = True

    for src in range(NUM_PORTS):
        row = mtx["inputs"][src]
        info = per_src[src]

        outs_union = set(info["all_dsts"])

        for ch in range(1, 17):
            outs_union |= info["ch_dsts"][ch]

        row["outputs"] = [
            d in outs_union
            for d in range(NUM_OUTS)
        ]

        if info["all_dsts"]:
            row["channels"] = [True] + [False] * 16

        else:
            ch_flags = [False] * 17

            for ch in range(1, 17):
                if info["ch_dsts"][ch]:
                    ch_flags[ch] = True

            row["channels"] = ch_flags

        if info["any_other"]:
            warnings.append(
                "SRC {}: есть правила, которые UI не отображает "
                "(CMD!= -1 или нестандартные).".format(src)
            )

    mtx["warnings"] = warnings

    return mtx


def write_routing_table_py(midirt, mididef=-1):
    by_src = [[] for _ in range(NUM_PORTS)]

    for ch, cmd, src, dst in midirt:
        try:
            src_i = int(src)
            dst_i = int(dst)
        except Exception:
            continue

        if 0 <= src_i < NUM_PORTS and 0 <= dst_i < NUM_OUTS:
            by_src[src_i].append(
                [
                    int(ch),
                    int(cmd),
                    src_i,
                    dst_i,
                ]
            )

    lines = []

    lines.append(
        "# Auto-generated by USB WebSerial UI. "
        "You can still edit manually.\n"
    )
    lines.append(
        "# [MIDI CH, MIDI CMD, source port, destination port]\n"
    )
    lines.append(
        "# -1 means ANY. Ports are 0..5.\n\n"
    )

    lines.append("MIDIRT = [\n")

    for src in range(NUM_PORTS):
        lines.append(
            "    # Вход {} на корпусе, в коде {}\n".format(
                src + 1,
                src,
            )
        )

        for r in by_src[src]:
            lines.append(
                "    {},\n".format(r)
            )

        lines.append("\n")

    lines.append("]\n\n")
    lines.append(
        "MIDIDEF = {}\n".format(int(mididef))
    )

    with open(ROUTING_TABLE_PATH, "w") as f:
        f.write("".join(lines))


def load_matrix_from_file():
    try:
        with open(MATRIX_PATH, "r") as f:
            return _sanitize_matrix(
                json.loads(f.read())
            )

    except Exception:
        mtx = decompile_matrix_from_midirt()
        save_matrix_to_file(mtx)
        return mtx


def save_matrix_to_file(mtx):
    mtx = _sanitize_matrix(mtx)

    with open(MATRIX_PATH, "w") as f:
        f.write(json.dumps(mtx))

    return mtx


# ---------- Split ----------
def default_splits():
    return {
        "version": 1,
        "splits": [],
    }


def load_split_file():
    global SPLIT_RULES

    try:
        with open(SPLIT_PATH, "r") as f:
            obj = json.loads(f.read())

        if not isinstance(obj, dict):
            return default_splits()

        if "splits" not in obj:
            obj["splits"] = []

        rules = obj["splits"]

        for rule in rules:
            if not isinstance(rule, dict):
                continue

            try:
                rule["split_note_num"] = parse_note(
                    rule["split_note"]
                )
            except Exception:
                rule["split_note_num"] = 60

        SPLIT_RULES = rules

        return obj

    except Exception:
        obj = default_splits()
        save_split_file(obj)
        return obj


def save_split_file(obj):
    global SPLIT_RULES

    if not isinstance(obj, dict):
        obj = default_splits()

    if "splits" not in obj:
        obj["splits"] = []

    with open(SPLIT_PATH, "w") as f:
        f.write(json.dumps(obj))

    rules = obj["splits"]

    for rule in rules:
        if not isinstance(rule, dict):
            continue

        try:
            rule["split_note_num"] = parse_note(
                rule["split_note"]
            )
        except Exception:
            rule["split_note_num"] = 60

    SPLIT_RULES = rules

    return obj


# ---------- Note Clone ----------
NOTE_CLONE_ENABLED = False
NOTE_CLONE_RULES = []
MIDI_SETTINGS = {
    "version": 1,
    "clock_enabled": True,
    "cc_enabled": True,
    "note_clone_enabled": True,
}


def default_midi_settings():
    return {
        "version": 1,
        "clock_enabled": True,
        "cc_enabled": True,
        "note_clone_enabled": True,
    }


def _sanitize_midi_settings(obj):
    if not isinstance(obj, dict):
        return default_midi_settings()

    return {
        "version": 1,
        "clock_enabled": bool(
            obj.get("clock_enabled", True)
        ),
        "cc_enabled": bool(
            obj.get("cc_enabled", True)
        ),
        "note_clone_enabled": bool(
            obj.get("note_clone_enabled", True)
        ),
    }


def save_midi_settings_file(obj):
    global MIDI_SETTINGS
    global NOTE_CLONE_ENABLED

    MIDI_SETTINGS = _sanitize_midi_settings(obj)

    NOTE_CLONE_ENABLED = bool(
        MIDI_SETTINGS["note_clone_enabled"]
    )

    with open(MIDI_SETTINGS_PATH, "w") as f:
        f.write(json.dumps(MIDI_SETTINGS))

    return MIDI_SETTINGS


def load_midi_settings_file():
    global MIDI_SETTINGS
    global NOTE_CLONE_ENABLED

    try:
        with open(MIDI_SETTINGS_PATH, "r") as f:
            obj = json.loads(f.read())

        MIDI_SETTINGS = _sanitize_midi_settings(obj)

    except Exception:
        MIDI_SETTINGS = default_midi_settings()

        MIDI_SETTINGS["note_clone_enabled"] = bool(
            NOTE_CLONE_ENABLED
        )

        save_midi_settings_file(MIDI_SETTINGS)

    NOTE_CLONE_ENABLED = bool(
        MIDI_SETTINGS["note_clone_enabled"]
    )

    return MIDI_SETTINGS

def default_note_clone():
    return {
        "version": 1,
        "rules": [],
    }


def load_note_clone_file():
    global NOTE_CLONE_RULES

    try:
        with open(NOTE_CLONE_PATH, "r") as f:
            obj = json.loads(f.read())

        if not isinstance(obj, dict):
            obj = default_note_clone()

        rules = obj.get("rules", [])

        if not isinstance(rules, list):
            rules = []

        NOTE_CLONE_RULES = rules

        return obj

    except Exception:
        obj = default_note_clone()
        save_note_clone_file(obj)
        return obj


def save_note_clone_file(obj):
    global NOTE_CLONE_RULES

    if not isinstance(obj, dict):
        obj = default_note_clone()

    if (
        "rules" not in obj
        or not isinstance(obj["rules"], list)
    ):
        obj["rules"] = []

    with open(NOTE_CLONE_PATH, "w") as f:
        f.write(json.dumps(obj))

    NOTE_CLONE_RULES = obj["rules"]

    return obj


# ---------- USB Serial protocol ----------
def _usb_write_line(s):
    sys.stdout.write(s + "\n")


_usb_poll = uselect.poll()
_usb_poll.register(sys.stdin, uselect.POLLIN)
_usb_buf = ""


def _usb_read_lines_nonblocking():
    global _usb_buf

    lines = []

    while True:
        ev = _usb_poll.poll(0)

        if not ev:
            break

        try:
            ch = sys.stdin.read(1)
        except Exception:
            break

        if not ch:
            break

        _usb_buf += ch

        while "\n" in _usb_buf:
            line, _usb_buf = _usb_buf.split(
                "\n",
                1,
            )

            line = line.rstrip("\r")

            if line:
                lines.append(line)

    return lines


# ---------- USB command handler ----------
def _handle_usb_command(line):
    line = line.strip()

    if not line:
        return

    if line == "GET":
        mtx = load_matrix_from_file()
        _usb_write_line(
            "OK " + json.dumps(mtx)
        )
        return

    if line == "GETSPLIT":
        obj = load_split_file()
        _usb_write_line(
            "OK " + json.dumps(obj)
        )
        return

    if line == "GETNOTECLONE":
        obj = load_note_clone_file()
        _usb_write_line(
            "OK " + json.dumps(obj)
        )
        return

    if line == "GETSETTINGS":
        obj = load_midi_settings_file()

        _usb_write_line(
            "OK " + json.dumps(obj)
        )

        return

    if line.startswith("SETNOTECLONE "):
        payload = line[13:]

        try:
            obj = json.loads(payload)
            save_note_clone_file(obj)
            _usb_write_line("OK")

        except Exception as e:
            _usb_write_line(
                "ERR " + str(e)
            )

        return

    if line.startswith("SETSETTINGS "):
        payload = line[12:]

        try:
            obj = json.loads(payload)
            save_midi_settings_file(obj)
            _usb_write_line("OK")

        except Exception as e:
            _usb_write_line(
                "ERR " + str(e)
            )

        return

    if line.startswith("SET "):
        payload = line[4:]

        try:
            mtx = json.loads(payload)
            mtx = save_matrix_to_file(mtx)

            midirt = compile_midirt_from_matrix(mtx)

            write_routing_table_py(
                midirt,
                mididef=MIDIDEF,
            )

            _load_routing_table_py()

            mtx2 = decompile_matrix_from_midirt()
            save_matrix_to_file(mtx2)

            _usb_write_line("OK")

        except Exception as e:
            _usb_write_line(
                "ERR " + str(e)
            )

        return

    if line.startswith("SETSPLIT "):
        payload = line[9:]

        try:
            obj = json.loads(payload)
            save_split_file(obj)
            _usb_write_line("OK")

        except Exception as e:
            _usb_write_line(
                "ERR " + str(e)
            )

        return

    if line == "MIDIRT":
        try:
            with open(ROUTING_TABLE_PATH, "r") as f:
                txt = f.read()

            _usb_write_line("BEGIN")

            for ln in txt.splitlines():
                _usb_write_line(ln)

            _usb_write_line("END")

        except Exception as e:
            _usb_write_line(
                "ERR " + str(e)
            )

        return

    _usb_write_line(
        "ERR unknown command"
    )


# ---------- PIO UART RX ----------
@rp2.asm_pio(
    in_shiftdir=rp2.PIO.SHIFT_RIGHT
)
def uart_rx():
    # fmt: off
    label("start")
    wait(0, pin, 0)
    set(x, 7)                 [10]

    label("rbitloop")
    in_(pins, 1)
    jmp(x_dec, "rbitloop")    [6]

    jmp(pin, "good_stop")
    jmp("start")

    label("good_stop")
    push(block)
    # fmt: on


# ---------- PIO UART TX ----------
@rp2.asm_pio(
    sideset_init=rp2.PIO.OUT_HIGH,
    out_init=rp2.PIO.OUT_HIGH,
    out_shiftdir=rp2.PIO.SHIFT_RIGHT,
)
def uart_tx():

    pull(block).side(1) [7]

    set(x, 7).side(0) [7]

    nop().side(0) [7]

    label("bitloop")

    out(pins, 1) [7]

    jmp(x_dec, "bitloop") [7]

    nop().side(1) [7]

    nop().side(1) [7]


# ---------- UART objects ----------
hw_uarts = []

for i in range(HW_NUM_UARTS):
    t_uart = machine.UART(
        i,
        UART_BAUD,
    )

    hw_uarts.append(t_uart)
    led_flash()


rx_uarts = []

for i in range(RX_NUM_UARTS):
    rsm = rp2.StateMachine(
        i,
        uart_rx,
        freq=8 * UART_BAUD,
        in_base=machine.Pin(
            RX_PIN_BASE + i
        ),
        jmp_pin=machine.Pin(
            RX_PIN_BASE + i
        ),
    )

    rsm.active(1)
    rx_uarts.append(rsm)
    led_flash()


tx_uarts = []

for i in range(TX_NUM_UARTS):
    tsm = rp2.StateMachine(
        RX_NUM_UARTS + i,
        uart_tx,
        freq=16 * UART_BAUD,
        sideset_base=machine.Pin(
            TX_PIN_BASE + i
        ),
        out_base=machine.Pin(
            TX_PIN_BASE + i
        ),
    )

    tsm.active(1)
    tx_uarts.append(tsm)
    led_flash()


def pio_midi_send(
    pio_uart,
    cmd,
    ch,
    b1,
    b2,
):
    sm = tx_uarts[pio_uart]
    status = (cmd + ch - 1) & 0xFF

    sm.put(status)
    sm.put(b1 & 0xFF)

    if cmd not in (0xC0, 0xD0):
        sm.put(b2 & 0xFF)


def pio_midi_realtime_send(
    pio_uart,
    cmd,
):
    tx_uarts[pio_uart].put(cmd & 0xFF)


def uart_midi_send(
    uart,
    cmd,
    ch,
    b1,
    b2,
):
    status = (cmd + ch - 1) & 0xFF

    debug_print(
        "UART",
        "status=",
        hex(status),
        "cmd=",
        hex(cmd),
        "ch=",
        ch,
        "bytes=",
        (
            [status, b1 & 0xFF]
            if cmd in (0xC0, 0xD0)
            else [
                status,
                b1 & 0xFF,
                b2 & 0xFF,
            ]
        ),
    )

    if cmd in (0xC0, 0xD0):
        hw_uarts[uart].write(
            ustruct.pack(
                "BB",
                status,
                b1 & 0xFF,
            )
        )

    else:
        hw_uarts[uart].write(
            ustruct.pack(
                "BBB",
                status,
                b1 & 0xFF,
                b2 & 0xFF,
            )
        )


def uart_midi_realtime_send(
    uart,
    cmd,
):
    hw_uarts[uart].write(
        MIDI_REALTIME_BYTES[cmd & 0xFF]
    )


def midi_send(
    uart,
    cmd,
    ch,
    b1,
    b2,
):
    debug_print(
        "SEND",
        "uart=",
        uart,
        "cmd=",
        hex(cmd),
        "ch=",
        ch,
        "b1=",
        b1,
        "b2=",
        b2,
    )

    if uart < HW_NUM_UARTS:
        uart_midi_send(
            uart,
            cmd,
            ch,
            b1,
            b2,
        )

    else:
        pio_midi_send(
            uart - HW_NUM_UARTS,
            cmd,
            ch,
            b1,
            b2,
        )


def midi_realtime_send(
    uart,
    cmd,
):
    if uart < HW_NUM_UARTS:
        uart_midi_realtime_send(
            uart,
            cmd,
        )
    else:
        pio_midi_realtime_send(
            uart - HW_NUM_UARTS,
            cmd,
        )

# ---------- Processor Engine ----------
def process_split(
    ch,
    cmd,
    d1,
    d2,
    src,
):
    input_ch = ch
    state_key = (src, input_ch)
    forced_output = None

    if cmd not in (0x80, 0x90):
        state = SPLIT_STATE.get(state_key)

        if state:
            if state.get("last_zone") == "low":
                return (
                    state.get("low_output"),
                    state.get(
                        "low_channel",
                        ch,
                    ),
                    cmd,
                    d1,
                    d2,
                )

            if state.get("last_zone") == "high":
                return (
                    state.get("high_output"),
                    state.get(
                        "high_channel",
                        ch,
                    ),
                    cmd,
                    d1,
                    d2,
                )

        return None, ch, cmd, d1, d2

    for rule in SPLIT_RULES:
        if not isinstance(rule, dict):
            continue

        if not rule.get("enabled", True):
            continue

        if rule.get("input") != src:
            continue

        if rule.get("channel") != input_ch:
            continue

        split = rule.get(
            "split_note_num",
            60,
        )

        state = SPLIT_STATE.setdefault(
            state_key,
            {
                "low_count": 0,
                "high_count": 0,
                "low_output": None,
                "high_output": None,
                "low_channel": None,
                "high_channel": None,
                "last_zone": None,
            },
        )

        if d1 < split:
            low = rule.get("low", {})

            forced_output = low.get(
                "output"
            )

            ch = low.get(
                "channel",
                input_ch,
            )

            state["low_output"] = forced_output
            state["low_channel"] = ch

            if cmd == 0x90 and d2 > 0:
                state["last_zone"] = "low"
                state["low_count"] += 1
            else:
                state["low_count"] = max(
                    0,
                    state["low_count"] - 1,
                )

        else:
            high = rule.get("high", {})

            forced_output = high.get(
                "output"
            )

            ch = high.get(
                "channel",
                input_ch,
            )

            state["high_output"] = forced_output
            state["high_channel"] = ch

            if cmd == 0x90 and d2 > 0:
                state["last_zone"] = "high"
                state["high_count"] += 1
            else:
                state["high_count"] = max(
                    0,
                    state["high_count"] - 1,
                )

        break

    return (
        forced_output,
        ch,
        cmd,
        d1,
        d2,
    )


def process_note_clone(
    ch,
    cmd,
    d1,
    d2,
    src,
):
    if not NOTE_CLONE_ENABLED:
        return False, []

    for rule in NOTE_CLONE_RULES:
        if not isinstance(rule, dict):
            continue

        if not rule.get("enabled", True):
            continue

        if rule.get("input") != src:
            continue

        if rule.get("channel") != ch:
            continue

        if cmd not in (0x80, 0x90):
            return True, []

        output = rule.get("output")
        output_channels = rule.get(
            "output_channels",
            [],
        )

        if not isinstance(
            output_channels,
            list,
        ):
            return True, []

        destinations = []

        for output_ch in output_channels:
            destinations.append(
                (
                    output,
                    output_ch,
                    cmd,
                    d1,
                    d2,
                )
            )

        return True, destinations

    return False, []


def process_midi(
    ch,
    cmd,
    d1,
    d2,
    src,
):
    (
        forced_output,
        output_ch,
        cmd,
        d1,
        d2,
    ) = process_split(
        ch,
        cmd,
        d1,
        d2,
        src,
    )

    if forced_output is None:
        return (
            None,
            ch,
            output_ch,
            cmd,
            d1,
            d2,
        )

    return (
        [forced_output],
        ch,
        output_ch,
        cmd,
        d1,
        d2,
    )


# ---------- MIDI Real-Time callback ----------
def doMidiRealtime(
    cmd,
    src,
):
    if not MIDI_SETTINGS["clock_enabled"]:
        return

    destinations = midiRouter(
        -1,
        cmd,
        src,
    )

    if DEBUG:
        debug_print(
            "REALTIME RX",
            "src=",
            src,
            "cmd=",
            hex(cmd),
            "destinations=",
            destinations,
        )

    for d in destinations:
        midi_realtime_send(
            d,
            cmd,
        )

# ---------- MIDI callbacks ----------
def doMidiNoteOn(
    ch,
    cmd,
    note,
    vel,
    src,
):
    matched, destinations = process_note_clone(
        ch,
        cmd,
        note,
        vel,
        src,
    )

    if matched:
        for (
            output,
            output_ch,
            out_cmd,
            out_note,
            out_vel,
        ) in destinations:
            debug_print(
                "NOTE CLONE TX",
                "src=",
                src,
                "input_ch=",
                ch,
                "output=",
                output,
                "output_ch=",
                output_ch,
                "cmd=",
                hex(out_cmd),
                "note=",
                out_note,
                "velocity=",
                out_vel,
            )

            midi_send(
                output,
                out_cmd,
                output_ch,
                out_note,
                out_vel,
            )

        return

    (
        forced_outputs,
        input_ch,
        output_ch,
        cmd,
        note,
        vel,
    ) = process_midi(
        ch,
        cmd,
        note,
        vel,
        src,
    )

    if forced_outputs is None:
        for d in midiRouter(
            input_ch,
            cmd,
            src,
        ):
            midi_send(
                d,
                cmd,
                output_ch,
                note,
                vel,
            )

    else:
        for d in forced_outputs:
            midi_send(
                d,
                cmd,
                output_ch,
                note,
                vel,
            )


def doMidiNoteOff(
    ch,
    cmd,
    note,
    vel,
    src,
):
    matched, destinations = process_note_clone(
        ch,
        cmd,
        note,
        vel,
        src,
    )

    if matched:
        for (
            output,
            output_ch,
            out_cmd,
            out_note,
            out_vel,
        ) in destinations:
            midi_send(
                output,
                out_cmd,
                output_ch,
                out_note,
                out_vel,
            )

        return

    (
        forced_outputs,
        input_ch,
        output_ch,
        cmd,
        note,
        vel,
    ) = process_midi(
        ch,
        cmd,
        note,
        vel,
        src,
    )

    if forced_outputs is None:
        for d in midiRouter(
            input_ch,
            cmd,
            src,
        ):
            midi_send(
                d,
                cmd,
                output_ch,
                note,
                vel,
            )

    else:
        for d in forced_outputs:
            midi_send(
                d,
                cmd,
                output_ch,
                note,
                vel,
            )


def doMidiThru(
    ch,
    cmd,
    d1,
    d2,
    src,
):
    if cmd == 0xB0 and not MIDI_SETTINGS["cc_enabled"]:
        return

    matched, destinations = process_note_clone(
        ch,
        cmd,
        d1,
        d2,
        src,
    )

    if matched:
        for (
            output,
            output_ch,
            out_cmd,
            out_note,
            out_vel,
        ) in destinations:
            debug_print(
                "NOTE CLONE TX",
                "src=",
                src,
                "input_ch=",
                ch,
                "output=",
                output,
                "output_ch=",
                output_ch,
                "cmd=",
                hex(out_cmd),
                "note=",
                out_note,
                "velocity=",
                out_vel,
            )

            midi_send(
                output,
                out_cmd,
                output_ch,
                out_note,
                out_vel,
            )

        return

    (
        forced_outputs,
        input_ch,
        output_ch,
        cmd,
        d1,
        d2,
    ) = process_midi(
        ch,
        cmd,
        d1,
        d2,
        src,
    )

    if forced_outputs is None:
        destinations = midiRouter(
            input_ch,
            cmd,
            src,
        )
    else:
        destinations = forced_outputs

    if cmd == 0xE0:
        debug_print(
            "PITCH TX",
            "destinations=",
            destinations,
            "ch=",
            output_ch,
            "raw=",
            [d1, d2],
        )

    for d in destinations:
        midi_send(
            d,
            cmd,
            output_ch,
            d1,
            d2,
        )


# ---------- MIDI decoders ----------
md = []

for i in range(NUM_PORTS):
    dec = SimpleMIDIDecoder.SimpleMIDIDecoder(i)

    dec.cbNoteOn(doMidiNoteOn)
    dec.cbNoteOff(doMidiNoteOff)
    dec.cbThru(doMidiThru)
    dec.cbRealtime(doMidiRealtime)

    md.append(dec)


# ---------- Boot ----------
_load_routing_table_py()
load_matrix_from_file()
load_split_file()
load_note_clone_file()
load_midi_settings_file()

_usb_write_line("OK ready")

# ---------- Main loop ----------
while True:

    for i in range(HW_NUM_UARTS):
        if hw_uarts[i].any():
            b = hw_uarts[i].read(1)[0]

            debug_print(
                "RAW RX UART",
                i,
                "byte=",
                hex(b),
                "dec=",
                b,
            )

            md[i].read(b)

    for i in range(RX_NUM_UARTS):
        if rx_uarts[i].rx_fifo():
            md[
                HW_NUM_UARTS + i
            ].read(
                rx_uarts[i].get() >> 24
            )

    for line in _usb_read_lines_nonblocking():
        _handle_usb_command(line)