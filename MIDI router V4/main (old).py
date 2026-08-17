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

NUM_PORTS = HW_NUM_UARTS + RX_NUM_UARTS  # 6 inputs
NUM_OUTS = HW_NUM_UARTS + TX_NUM_UARTS   # 6 outputs

ROUTING_TABLE_PATH = "routing_table.py"
MATRIX_PATH = "routing_matrix.json"


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
        "version": 1,
        "inputs": [
            {"channels": [True] + [False] * 16, "outputs": [True] * NUM_OUTS}
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

    out = {"version": 1, "inputs": [], "warnings": []}
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

        out["inputs"].append({"channels": ch, "outputs": outs})

    return out


def compile_midirt_from_matrix(mtx):
    mtx = _sanitize_matrix(mtx)
    midirt = []
    for src, row in enumerate(mtx["inputs"]):
        channels = row["channels"]
        outputs = row["outputs"]
        dsts = [d for d, on in enumerate(outputs) if on]
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
        {"all_dsts": set(), "ch_dsts": [set() for _ in range(17)], "any_other": False}
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
        row["outputs"] = [(d in outs_union) for d in range(NUM_OUTS)]

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
                "SRC {}: есть правила, которые UI не отображает (CMD!= -1 или нестандартные).".format(src)
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
            by_src[src_i].append([int(ch), int(cmd), src_i, dst_i])

    lines = []
    lines.append("# Auto-generated by USB WebSerial UI. You can still edit manually.\n")
    lines.append("# [MIDI CH, MIDI CMD, source port, destination port]\n")
    lines.append("# -1 means ANY. Ports are 0..5.\n\n")
    lines.append("MIDIRT = [\n")
    for src in range(NUM_PORTS):
        lines.append("    # Вход {} на корпусе, в коде {}\n".format(src + 1, src))
        for r in by_src[src]:
            lines.append("    {},\n".format(r))
        lines.append("\n")
    lines.append("]\n\n")
    lines.append("MIDIDEF = {}\n".format(int(mididef)))

    with open(ROUTING_TABLE_PATH, "w") as f:
        f.write("".join(lines))


def load_matrix_from_file():
    try:
        with open(MATRIX_PATH, "r") as f:
            return _sanitize_matrix(json.loads(f.read()))
    except Exception:
        mtx = decompile_matrix_from_midirt()
        save_matrix_to_file(mtx)
        return mtx


def save_matrix_to_file(mtx):
    mtx = _sanitize_matrix(mtx)
    with open(MATRIX_PATH, "w") as f:
        f.write(json.dumps(mtx))
    return mtx


# ---------- USB Serial protocol ----------
# Commands (single line):
#   GET
#   SET <json>
#   MIDIRT
#
# Responses:
#   OK <json>
#   OK
#   BEGIN ...file... END
#   ERR <message>


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
            line, _usb_buf = _usb_buf.split("\n", 1)
            line = line.rstrip("\r")
            if line:
                lines.append(line)
    return lines


def _handle_usb_command(line):
    line = line.strip()
    if not line:
        return

    if line == "GET":
        mtx = load_matrix_from_file()
        _usb_write_line("OK " + json.dumps(mtx))
        return

    if line.startswith("SET "):
        payload = line[4:]
        try:
            mtx = json.loads(payload)
            mtx = save_matrix_to_file(mtx)
            midirt = compile_midirt_from_matrix(mtx)
            write_routing_table_py(midirt, mididef=MIDIDEF)
            _load_routing_table_py()
            mtx2 = decompile_matrix_from_midirt()
            save_matrix_to_file(mtx2)
            _usb_write_line("OK")
        except Exception as e:
            _usb_write_line("ERR " + str(e))
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
            _usb_write_line("ERR " + str(e))
        return

    _usb_write_line("ERR unknown command")


# ---------- PIO UART RX/TX ----------
@rp2.asm_pio(in_shiftdir=rp2.PIO.SHIFT_RIGHT)
def uart_rx():
    # fmt: off
    label("start")
    wait(0, pin, 0)
    set(x, 7)                 [10]
    label("rbitloop")
    in_(pins, 1)
    jmp(x_dec, "rbitloop")     [6]
    jmp(pin, "good_stop")
    jmp("start")
    label("good_stop")
    push(block)
    # fmt: on


@rp2.asm_pio(
    sideset_init=rp2.PIO.OUT_HIGH,
    out_init=rp2.PIO.OUT_HIGH,
    out_shiftdir=rp2.PIO.SHIFT_RIGHT,
)
def uart_tx():
    # fmt: off
    pull(block)                .side(1)  [7]
    set(x, 7)                  .side(0)  [7]
    label("bitloop")
    out(pins, 1)               .side(0)  [6]
    jmp(x_dec, "bitloop")      .side(0)  [6]
    nop()                      .side(1)  [6]
    # fmt: on


# ---------- UART objects ----------
hw_uarts = []
for i in range(HW_NUM_UARTS):
    t_uart = machine.UART(i, UART_BAUD)
    hw_uarts.append(t_uart)
    led_flash()

rx_uarts = []
for i in range(RX_NUM_UARTS):
    rsm = rp2.StateMachine(
        i,
        uart_rx,
        freq=8 * UART_BAUD,
        in_base=machine.Pin(RX_PIN_BASE + i),
        jmp_pin=machine.Pin(RX_PIN_BASE + i),
    )
    rsm.active(1)
    rx_uarts.append(rsm)
    led_flash()

tx_uarts = []
for i in range(TX_NUM_UARTS):
    tsm = rp2.StateMachine(
        RX_NUM_UARTS + i,
        uart_tx,
        freq=8 * UART_BAUD,
        sideset_base=machine.Pin(TX_PIN_BASE + i),
        out_base=machine.Pin(TX_PIN_BASE + i),
    )
    tsm.active(1)
    tx_uarts.append(tsm)
    led_flash()


def pio_midi_send(pio_uart, cmd, ch, b1, b2):
    sm = tx_uarts[pio_uart]
    status = (cmd + ch - 1) & 0xFF
    sm.put(status)
    sm.put(b1 & 0xFF)
    if cmd not in (0xC0, 0xD0):
        sm.put(b2 & 0xFF)


def uart_midi_send(uart, cmd, ch, b1, b2):
    status = (cmd + ch - 1) & 0xFF
    if cmd in (0xC0, 0xD0):
        hw_uarts[uart].write(ustruct.pack("BB", status, b1 & 0xFF))
    else:
        hw_uarts[uart].write(ustruct.pack("BBB", status, b1 & 0xFF, b2 & 0xFF))


def midi_send(uart, cmd, ch, b1, b2):
    if uart < HW_NUM_UARTS:
        uart_midi_send(uart, cmd, ch, b1, b2)
    else:
        pio_midi_send(uart - HW_NUM_UARTS, cmd, ch, b1, b2)


# ---------- MIDI callbacks ----------
def doMidiNoteOn(ch, cmd, note, vel, src):
    for d in midiRouter(ch, cmd, src):
        midi_send(d, cmd, ch, note, vel)


def doMidiNoteOff(ch, cmd, note, vel, src):
    for d in midiRouter(ch, cmd, src):
        midi_send(d, cmd, ch, note, vel)


def doMidiThru(ch, cmd, d1, d2, src):
    for d in midiRouter(ch, cmd, src):
        midi_send(d, cmd, ch, d1, d2)


md = []
for i in range(NUM_PORTS):
    dec = SimpleMIDIDecoder.SimpleMIDIDecoder(i)
    dec.cbNoteOn(doMidiNoteOn)
    dec.cbNoteOff(doMidiNoteOff)
    dec.cbThru(doMidiThru)
    md.append(dec)


# ---------- Boot ----------
_load_routing_table_py()
load_matrix_from_file()

_usb_write_line("OK ready")  # visible to WebSerial

# ---------- Main loop ----------
while True:
    for i in range(HW_NUM_UARTS):
        if hw_uarts[i].any():
            md[i].read(hw_uarts[i].read(1)[0])

    for i in range(RX_NUM_UARTS):
        if rx_uarts[i].rx_fifo():
            md[HW_NUM_UARTS + i].read(rx_uarts[i].get() >> 24)

    for line in _usb_read_lines_nonblocking():
        _handle_usb_command(line)