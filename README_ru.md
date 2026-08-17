# MIDI Router

MIDI-роутер и процессор на Raspberry Pi Pico с WebSerial UI.

Firmware построена так, чтобы отдельно держать MIDI-декодирование, обработку сообщений и маршрутизацию. Сейчас архитектура намеренно практичная и стабильная; дальнейшее направление — модульная платформа MIDI-процессоров.

## Текущее состояние

Реализовано:

- Routing Matrix
- WebSerial UI
- Keyboard Split
- Note Clone / fan-out
- глобальный Enable MIDI Clock
- глобальный Enable MIDI CC
- постоянное хранение конфигурации в JSON
- генерация `routing_table.py`
- USB-протокол настройки

Текущие файлы конфигурации:

```text
routing_matrix.json
routing_table.py
split_rules.json
note_clone.json
midi_settings.json
```

---

# Схема прохождения MIDI

Ключевое различие — между **обычной маршрутизацией** и **выходом, который принудительно выбирает/создаёт процессор**.

```text
                  MIDI INPUT
                      │
                      ▼
             ┌──────────────────┐
             │ MIDI Decoder     │
             │ SimpleMIDIDecoder│
             └────────┬─────────┘
                      │ decoded MIDI event
                      ▼
             ┌──────────────────┐
             │ Processor Engine│
             └────────┬─────────┘
                      │
         ┌────────────┼───────────────────┐
         │            │                   │
         ▼            ▼                   ▼
      Split       Note Clone          CC / Clock
         │            │                   │
         │            ├─ создаёт          ├─ discard
         │            │  clone events     │  или дальше
         │            │
         └──────┬─────┘
                │
                │ обычное событие
                │ без forced destination
                ▼
       ┌──────────────────────┐
       │ Routing Engine       │
       │ MIDIRT / Matrix      │
       └──────────┬───────────┘
                  │
         ┌────────┼─────────┐
         ▼        ▼         ▼
       OUT 1    OUT 2     OUT ...
```

## Главное правило приоритета

Для **обычного MIDI-события**:

```text
Input
  → Decoder
  → Filters / processors
  → Routing Matrix
  → Output(s)
```

Для **Split с явно указанным output**:

```text
Input
  → Decoder
  → Split
  → forced output
  → Output
```

В этом случае обычный выбор destination через Routing Matrix для данного события не используется.

Для **Note Clone**:

```text
Input
  → Decoder
  → Note Clone
  → созданные Note events
  → явно выбранный output/channel
```

Текущее поведение Note Clone: совпавшее событие обрабатывается через destinations Clone вместо обычной маршрутизации.

### Поэтому важно

Если в Routing Matrix выключить OUT, это **не выключает автоматически** destination, который явно задан в Split или Note Clone.

Например:

```text
Routing Matrix:
IN1 → OUT2 = OFF

Note Clone:
IN1 / CH1 → OUT2 / CH1+CH2
```

Note Clone всё равно отправит событие на OUT2.

Это должно быть явно отражено в UI и документации.

---

# Приоритет и ответственность

Практический порядок обработки сейчас:

```text
1. MIDI Decoder
   ↓
2. Глобальные фильтры
   - MIDI Clock
   - MIDI CC
   ↓
3. Специальные processors
   - Keyboard Split
   - Note Clone
   ↓
4. Обычная Routing Matrix
   ↓
5. MIDI Output
```

Есть важное исключение:

**Split и Note Clone могут выбрать destination явно.**

Если processor задал такой destination, он имеет приоритет над обычным выбором destination через Routing Matrix для этого события.

### Кто за что отвечает

| Слой | Отвечает за | Не отвечает за |
|---|---|---|
| Decoder | MIDI bytes → event | routing, configuration |
| CC/Clock filters | пропустить/отбросить тип сообщения | destination |
| Split | определение low/high, optional output/channel | обычную routing |
| Note Clone | fan-out и clone channels/output | обычную routing |
| Routing Matrix | обычное input/channel → output | processing/filtering |
| UART TX | физическую передачу | routing decisions |

---

# Конфигурационные файлы

## `routing_matrix.json`

Routing Matrix из Web UI.

Определяет обычную маршрутизацию по input, MIDI channel и output.

## `routing_table.py`

Генерируется из `routing_matrix.json`.

Формат:

```text
[MIDI CH, MIDI CMD, source port, destination port]
```

Firmware загружает эти правила в `MIDIRT`.

## `split_rules.json`

Правила Keyboard Split.

Split может задавать:

- input
- MIDI channel
- split note
- low/high output
- low/high MIDI channel

## `note_clone.json`

Правила Note Clone.

Правило может задавать:

- input
- MIDI channel
- output
- один или несколько output MIDI channels

Глобальный Enable Note Clone здесь не хранится.

## `midi_settings.json`

Глобальные переключатели:

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

`SET` сохраняет Matrix, генерирует `routing_table.py`, перечитывает таблицу и синхронизирует сохранённую Matrix.

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

## Диагностика

```text
MIDIRT
```

Browser UI общается с firmware через эти команды. UI не редактирует файлы Pico напрямую.

---

# Web UI

Сейчас UI содержит:

- Routing Matrix
- Keyboard Split
- Note Clone
- MIDI Settings

MIDI Settings:

- **Enable Note Clone**
- **Enable MIDI Clock**
- **Enable MIDI CC**

Текущая семантика:

- Enable MIDI CC управляет всеми `Control Change` (`0xB0`) глобально.
- Pitch Bend (`0xE0`) не зависит от Enable MIDI CC.
- Aftertouch не зависит от Enable MIDI CC.
- Enable MIDI Clock сейчас является одним глобальным переключателем для Real-Time сообщений, которые обрабатывает decoder.

---

# Runtime Rules

Во время обработки MIDI нельзя:

- парсить JSON
- обращаться к filesystem
- выполнять blocking USB operations
- перечитывать configuration
- зависеть от состояния browser/UI

Конфигурация должна быть заранее загружена в RAM.

---

# План развития

## Ближайшие задачи

- [ ] CC filtering **per input**
- [ ] решить, нужна ли дополнительно фильтрация CC по MIDI channel
- [ ] оценить отдельные переключатели Clock / Start / Continue / Stop
- [ ] улучшить diagnostics и status reporting
- [ ] явно показывать в UI взаимодействие Processor и Routing Matrix

### Направление CC filtering

Первый вариант:

```text
Input 1 → CC allowed
Input 2 → CC blocked
Input 3 → CC allowed
```

То есть фильтр привязывается к **Input**.

Это логичнее, чем per-output, потому что фильтр отвечает на вопрос:

> какие CC мы принимаем от конкретного MIDI-источника?

Возможное дальнейшее расширение:

```text
Input
  └── MIDI Channel
       └── CC / Message Type
```

Per-output CC filtering добавлять только если появится реальная задача:

> разные CC-наборы для разных destination.

## Среднесрочно

- [ ] Channel Filter
- [ ] Message Filter
- [ ] Channel Remap
- [ ] Transpose
- [ ] Velocity Curve
- [ ] Program Change Filter
- [ ] более точная Real-Time фильтрация
- [ ] SysEx filtering/support
- [ ] Presets
- [ ] Import / Export configuration

## Долгосрочно

Возможное развитие в полноценный Processor Chain:

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

Generic Processor Chain следует вводить только тогда, когда он решает конкретную задачу. Нельзя ломать стабильные текущие функции только ради абстракции.

---

# Философия проекта

- Simple
- Deterministic
- Modular
- Сначала стабильность, потом абстракция
- Processor не должен владеть routing
- Routing должен оставаться простым
- Новые функции по возможности должны быть изолированными
