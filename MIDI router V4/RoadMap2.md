Core

* ✅ Routing Engine
* ✅ Processor Engine
* ✅ Split Processor

MIDI

Processors

* ✅ Split Processor
* 🔜 Channel Filter
* 🔜 Message Filter
* 🔜 Channel Remap
* 🔜 MIDI Clone (Fan-out)

Real-Time

* 🔜 MIDI Real-Time
    * Clock
    * Start
    * Continue
    * Stop
    * Active Sense
    * Reset

Filters

* 🔜 Input Filters (Ignore)
    * CC
    * Program Change
    * SysEx
    * Clock
    * Transport
    * Active Sense
    * Reset

System

* ⏳ SysEx support

UI

* 🔜 Ignore section
* 🔜 Processor chain editor
* 🔜 Real-Time configuration (если понадобится)

Customer Tasks

✅ MIDI Split

Реализовано.

⸻

🔜 MIDI Processor Chain
Input

↓
Channel Filter
keep ch16

↓
Message Filter
keep Notes only

↓
MIDI Clone
ch16 →
    ch1
    ch2
    ch3
    ch4

↓
Routing Engine

↓
OUT
То есть задача

ch1+ch2+ch3+ch4 => один OUT

вообще не требует никакого “сумматора”.

Это уже умеет Routing Engine.

Каждый Processor просто создаёт ещё один MIDI-пакет.

Получится примерно так:
NoteOn ch16 C4

↓

Clone

↓

NoteOn ch1 C4
NoteOn ch2 C4
NoteOn ch3 C4
NoteOn ch4 C4

↓

Routing Engine

↓

OUT1
Все четыре сообщения уйдут в один и тот же UART подряд.

⸻

И вот тут появляется очень важная мысль

До этого мы говорили про Split, но сейчас становится видно, что проект постепенно превращается в конструктор MIDI-процессоров.

Например:
Input

↓

Channel Filter

↓

Message Filter

↓

Split

↓

Transpose

↓

Velocity Curve

↓

Clone

↓

Routing
И каждый из этих блоков ничего не знает про остальные.

Именно такую архитектуру используют профессиональные MIDI-процессоры (Bome, MIDI Solutions, Blokas, Conductive Labs и т.п.).

Поэтому я бы больше не думал в терминах “добавить ещё одну функцию”. Я бы думал в терминах добавить ещё один Processor. Тогда любые новые задачи пользователей будут собираться из уже существующих блоков, а не потребуют переписывать прошивку.