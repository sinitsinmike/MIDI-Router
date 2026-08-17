# =========================================
# file: SimpleMIDIDecoder.py
# =========================================

# Simple MIDI Decoder
# for MicroPython on Raspberry Pi Pico
#
# MIT License
#
# Copyright (c) 2022 Michael Sinitsin
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.


class SimpleMIDIDecoder:

    def __init__(self, idx=-1):
        self.idx = idx
        self.ch = 0
        self.cmd = 0
        self.d1 = 0
        self.d2 = 0
        self.data_count = 0

        self.cbThruFn = 0
        self.cbNoteOnFn = 0
        self.cbNoteOffFn = 0
        self.cbRealtimeFn = 0

    def cbThru(self, callback):
        self.cbThruFn = callback

    def ThruFn(self, ch, cmd, d1, d2, idx):
        if self.cbThruFn:
            if idx != -1:
                self.cbThruFn(ch, cmd, d1, d2, idx)
            else:
                self.cbThruFn(ch, cmd, d1, d2)
        else:
            if d2 == -1:
                print(
                    "Thru ",
                    ch,
                    ":",
                    hex(cmd),
                    ":",
                    d1,
                )
            else:
                print(
                    "Thru ",
                    ch,
                    ":",
                    hex(cmd),
                    ":",
                    d1,
                    ":",
                    d2,
                )

    def cbNoteOn(self, callback):
        self.cbNoteOnFn = callback

    def NoteOnFn(self, ch, cmd, note, level, idx):
        if self.cbNoteOnFn:
            if idx != -1:
                self.cbNoteOnFn(
                    ch,
                    cmd,
                    note,
                    level,
                    idx,
                )
            else:
                self.cbNoteOnFn(
                    ch,
                    cmd,
                    note,
                    level,
                )
        else:
            print(
                "NoteOn ",
                ch,
                ":",
                note,
                ":",
                level,
            )

    def cbNoteOff(self, callback):
        self.cbNoteOffFn = callback

    def NoteOffFn(self, ch, cmd, note, level, idx):
        if self.cbNoteOffFn:
            if idx != -1:
                self.cbNoteOffFn(
                    ch,
                    cmd,
                    note,
                    level,
                    idx,
                )
            else:
                self.cbNoteOffFn(
                    ch,
                    cmd,
                    note,
                    level,
                )
        else:
            print(
                "NoteOff ",
                ch,
                ":",
                note,
                ":",
                level,
            )

    def cbRealtime(self, callback):
        self.cbRealtimeFn = callback

    def RealtimeFn(self, cmd, idx):
        if self.cbRealtimeFn:
            if idx != -1:
                self.cbRealtimeFn(cmd, idx)
            else:
                self.cbRealtimeFn(cmd)

    def read(self, mb):
        if 0x80 <= mb <= 0xEF:
            # MIDI Voice Category Message.
            # This starts or replaces Running Status.
            self.cmd = mb & 0xF0
            self.ch = 1 + (mb & 0x0F)

            self.d1 = 0
            self.d2 = 0
            self.data_count = 0

        elif 0xF0 <= mb <= 0xF7:
            # MIDI System Common.
            # System Common messages are not currently decoded.
            self.cmd = 0
            self.d1 = 0
            self.d2 = 0
            self.data_count = 0

        elif 0xF8 <= mb <= 0xFF:
            # MIDI System Real-Time.
            #
            # Real-Time messages may appear between any bytes of another
            # MIDI message. They must therefore NOT modify Running Status
            # or the partially received MIDI message.
            if mb in (0xF8, 0xFA, 0xFB, 0xFC):
                self.RealtimeFn(
                    mb,
                    self.idx,
                )

        else:
            # MIDI Data byte.
            if self.cmd == 0:
                return

            if self.cmd == 0x80:
                # Note Off.
                if self.d1 == 0:
                    self.d1 = mb
                else:
                    self.d2 = mb

                    self.NoteOffFn(
                        self.ch,
                        self.cmd,
                        self.d1,
                        self.d2,
                        self.idx,
                    )

                    self.d1 = 0
                    self.d2 = 0

            elif self.cmd == 0x90:
                # Note On.
                if self.d1 == 0:
                    self.d1 = mb
                else:
                    self.d2 = mb

                    if self.d2 == 0:
                        self.NoteOffFn(
                            self.ch,
                            self.cmd,
                            self.d1,
                            self.d2,
                            self.idx,
                        )
                    else:
                        self.NoteOnFn(
                            self.ch,
                            self.cmd,
                            self.d1,
                            self.d2,
                            self.idx,
                        )

                    self.d1 = 0
                    self.d2 = 0

            elif self.cmd == 0xC0:
                # Program Change.
                self.d1 = mb

                self.ThruFn(
                    self.ch,
                    self.cmd,
                    self.d1,
                    -1,
                    self.idx,
                )

                self.d1 = 0

            elif self.cmd == 0xD0:
                # Channel Pressure.
                self.d1 = mb

                self.ThruFn(
                    self.ch,
                    self.cmd,
                    self.d1,
                    -1,
                    self.idx,
                )

                self.d1 = 0

            else:
                # All other Channel Voice messages have two data bytes.
                if self.data_count == 0:
                    self.d1 = mb
                    self.data_count = 1
                else:
                    self.d2 = mb

                    self.ThruFn(
                        self.ch,
                        self.cmd,
                        self.d1,
                        self.d2,
                        self.idx,
                    )

                    self.d1 = 0
                    self.d2 = 0
                    self.data_count = 0