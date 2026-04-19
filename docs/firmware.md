# Firmware Documentation


## Overview

The firmware runs on the Arduino Nano (ATmega328P) and acts as a bridge between the 433MHz RF receiver and the Meshtastic LoRa mesh network. It decodes gate open/close events from the KERUI D026 sensor via the RXB6 receiver and forwards text messages over UART to the Heltec LoRa32 V3 running Meshtastic.

## Project Structure

```
firmware/
  platformio.ini      PlatformIO project config
  include/
    config.h          Sensor codes, pin definitions, timing
  src/
    main.cpp          Main firmware (setup + loop)
```

## Build Environment

- **Framework:** Arduino
- **Platform:** Atmel AVR (`atmelavr`)
- **Board:** `nanoatmega328` (Arduino Nano, ATmega328P, CH340 USB-UART)
- **Build system:** PlatformIO (via Make wrapper)

## Libraries

| Library | Version | Purpose |
|---------|---------|---------|
| rc-switch | ^2.6.4 | 433MHz RF protocol decoding. Uses hardware interrupt INT0 on pin D2. |
| SoftwareSerial | built-in | UART TX on D3 to Heltec (9600 baud) via R1/R2 divider; RX on D4 from Heltec GPIO48 via R6 series resistor. |

## Pin Configuration

Defined in `firmware/include/config.h`:

| Define | Value | Function |
|--------|-------|----------|
| `RF_PIN` | 2 | RXB6 DATA input. D2 = INT0 (required by RCSwitch `enableReceive`). |
| `SERIAL_TX` | 3 | SoftwareSerial TX to Heltec GPIO47 via level divider. |
| `SERIAL_RX` | 4 | SoftwareSerial RX ← R6 (4.7k) ← Heltec GPIO48 (Meshtastic serial TX). |

**Note on GPIO47:** The Heltec V3 Meshtastic serial module must be configured to use GPIO47 as its RX pin. GPIO44 is shared with the CP2102 USB-UART and causes conflicts.

## Configuration

Edit `firmware/include/config.h` before building:

### Sensor Codes

The firmware holds up to `MAX_CODES` (default 16) 433 MHz codes in a runtime-mutable list persisted in EEPROM. Codes are added, removed, listed, and cleared over the mesh via the `CODE_*` commands (see the [CMD Protocol](#cmd-protocol) section). An RF frame that matches **any** registered code fires `Gate: TRIGGERED:<code>`.

```c
#define DEFAULT_CODE_OPEN 150910  // factory seed (KERUI D026); 0 disables auto-seeding
#define MAX_CODES         16      // max distinct sensor codes
```

On a fresh chip (all EEPROM code slots `0xFFFFFFFF`), the firmware seeds the list with `DEFAULT_CODE_OPEN` so an out-of-the-box install still detects the calibrated KERUI D026 without any CMDs. To learn a new sensor, use `make learn-sensor` (the production firmware prints every unrecognised code to USB serial as `RF unknown: <decimal>`) and then register the decimal via `@Gate CODE_ADD:<decimal>`.

### Sensor Identity

| Define | Default | Description |
|--------|---------|-------------|
| `SENSOR_NAME` | `"Gate"` | Instance prefix on every frame — `Gate: STATUS: ...`, `Gate: TRIGGERED`. Mirrors AntiHunter's `AH34:` pattern so AH-format parsers find the id. |
| `SENSOR_TYPE` | `"GATESENSOR"` | Uppercase sensor-class identifier written into the STATUS frame's `Type:` field. DigiNode CC classifies nodes by this value, not by the prefix, so a future `MotionHall` build can ship `SENSOR_TYPE "MOTION"` without any dispatcher changes. |

### Timing

| Define | Default | Description |
|--------|---------|-------------|
| `DEFAULT_HB_MIN` | 30 | Default heartbeat interval in minutes (compile-time fallback). The effective interval is runtime-configurable via the `HB_INTERVAL` command and persisted in EEPROM. |
| `HB_MIN_MIN` / `HB_MIN_MAX` | 1 / 60 | Accepted range for `HB_INTERVAL`. Values outside the range are rejected with `HB_ACK:ERROR`. |
| `DEFAULT_DEBOUNCE_SEC` | 10 | Default RF debounce window (seconds). Collapses the KERUI retransmit burst (4–10 copies per trigger) into one mesh event per physical opening. Runtime-configurable via `DEBOUNCE_SET:<seconds>` and persisted in EEPROM. |
| `DEBOUNCE_MIN_SEC` / `DEBOUNCE_MAX_SEC` | 1 / 60 | Accepted range for `DEBOUNCE_SET`. Values outside the range are rejected with `DEBOUNCE_ACK:ERROR`. |

### EEPROM

| Addr | Size | Purpose |
|------|------|---------|
| 0–1 | 2 B (`uint16_t`) | `bootCount` — incremented once per `setup()`. A fresh `0xFFFF` resets to 0. |
| 2 | 1 B (`uint8_t`) | `hbEnabled` — `0xFF`/`1`=on, `0`=off. Mutated by `HB_ON`/`HB_OFF`. |
| 3 | 1 B (`uint8_t`) | `hbIntervalMin` — heartbeat interval (minutes). `0xFF` or out-of-range → `DEFAULT_HB_MIN`. Mutated by `HB_INTERVAL`. |
| 4 | 1 B (`uint8_t`) | `debounceSec` — RF debounce window (seconds). `0xFF` or out-of-range → `DEFAULT_DEBOUNCE_SEC`. Mutated by `DEBOUNCE_SET`. |
| 5 | 1 B | reserved |
| 6–9 | 4 B (`uint32_t`) | `hitCount` — persistent RF trigger counter. `0xFFFFFFFF` (fresh chip) treated as 0. Mutated on every TRIGGERED event and by `HITS_RESET`. |
| 10–11 | 2 B | reserved |
| 12–75 | 64 B | `codes[16]` × `uint32_t` — registered 433 MHz codes. `0xFFFFFFFF` = empty slot. Mutated by `CODE_ADD`/`CODE_REMOVE`/`CODE_CLEAR`. |

Writes use `EEPROM.put`/`EEPROM.update` so unchanged bytes don't consume write cycles. At ATmega328P's 100k-write endurance and an expected write rate of ~10 triggers/day, the hit counter cell will outlast the rest of the hardware.

## Message Format

All messages are sent as plain text over SoftwareSerial at 9600 baud. Meshtastic receives them as TEXTMSG via its serial module.

### STATUS Heartbeat (on boot + every 30 minutes)

```
Gate: STATUS: Mode:ARMED Scan:GATE Hits:3 Temp:0.0C Up:00:15:32 Type:GATESENSOR Boot:5
```

The frame matches the AntiHunter STATUS regex used by CC PRO
(`meshtastic-rewrite.parser.ts:10`) and is also recognised by DigiNode CC's
sensor classifier. The `Type:` field is the authoritative sensor-class
identifier — DigiNode CC ignores the prefix and classifies purely on this
value, so future sensor variants (DOOR, WINDOW, MOTION) can classify without
any backend changes.

| Field | Source | Notes |
|-------|--------|-------|
| `Gate:` | `SENSOR_NAME` | Instance prefix |
| `STATUS:` | literal | AH regex anchor |
| `Mode:ARMED` | constant | AH-required. Reserved for future DISARMED state. |
| `Scan:GATE` | constant | AH-required. Identifies what kind of RF traffic this sensor watches for. |
| `Hits:<n>` | in-RAM counter | Cumulative count of RF triggers since boot |
| `Temp:0.0C` | placeholder | AH-required field; Nano has no accurate temperature sensor |
| `Up:HH:MM:SS` | `millis() / 1000` | Uptime since last boot |
| `Type:GATESENSOR` | `SENSOR_TYPE` | Sensor-class identifier (the extensibility hook) |
| `Boot:<n>` | EEPROM `uint16_t` | Cumulative boot count across power cycles |

### Gate Events

```
Gate: TRIGGERED:<decimal>
```

A single event is emitted per physical trigger. The debounce window (default 10 s, `DEBOUNCE_SET` configurable) collapses the KERUI retransmit burst into one mesh message. The `<decimal>` is the decoded 433 MHz code, enabling correlation against `CODE_LIST` to identify which physical sensor fired. Event frames do not classify a node on their own — DigiNode CC relies on the node having already been classified via a prior STATUS broadcast.

### Unknown RF Codes (debug output only, not sent to mesh)

```
RF unknown: 1234567
```

Printed to the Nano's USB serial (115200 baud) only, not forwarded to Meshtastic. Used by `make learn-sensor` to discover the decimal code for a new sensor.

## CMD Protocol

The Nano listens for command frames on its SoftwareSerial RX pin (D4, fed by Heltec GPIO48 through R6). Commands are plain text forwarded by the Heltec's Meshtastic serial module in `TEXTMSG` mode.

### Wire format

```
@<target> <verb>[:<param1>[:<param2>...]]\n
```

- `<target>` — `ALL` for broadcast, or the sensor's identity. Matched case-insensitively against `SENSOR_NAME` (default `"Gate"`), so `@Gate`, `@GATE`, and `@gate` all hit.
- `<verb>` — uppercase command name.
- `<params>` — colon-delimited.
- Terminated by `\n` (TEXTMSG preserves the payload's line framing).

Frames that don't begin with `@` are ignored. Frames whose target doesn't match `ALL` or `SENSOR_NAME` are ignored — the sensor will not respond on another node's behalf.

### Identity invariant

The target-matching code assumes the Heltec's Meshtastic owner short-name is the same string as the Nano's `SENSOR_NAME`. This is set by `scripts/flash-heltec-meshtastic.sh` (`--set-owner-short "GATE"`) and must be kept in sync if `SENSOR_NAME` ever changes. TEXTMSG mode strips envelope metadata, so the Nano cannot discover the Heltec's short-name at runtime.

### Commands

| Verb | Params | ACK | Effect |
|------|--------|-----|--------|
| `STATUS` | none | *(none — the STATUS frame itself is the reply)* | Emits the STATUS heartbeat frame on demand. |
| `HB_ON` | none | `Gate: HB_ACK:OK` | Enables periodic STATUS broadcasts. Persisted. |
| `HB_OFF` | none | `Gate: HB_ACK:OK` | Suspends periodic STATUS broadcasts. Boot STATUS and `@… STATUS` queries still work. Persisted. |
| `HB_INTERVAL` | `<minutes>` in `[1, 60]` | `Gate: HB_ACK:OK` or `HB_ACK:ERROR` | Changes the heartbeat interval and restarts the timer so the next STATUS fires `<minutes>` from the command. Persisted. |
| `REBOOT` | none | `Gate: REBOOT_ACK:OK` (emitted before reset) | Watchdog-triggered reset. The Nano comes back in ~1 s and re-emits the boot STATUS with `Boot:` incremented. |
| `HITS_RESET` | none | `Gate: HITS_RESET_ACK:OK` | Zeros the persistent hit counter. |
| `DEBOUNCE_SET` | `<seconds>` in `[1, 60]` | `Gate: DEBOUNCE_ACK:OK` or `DEBOUNCE_ACK:ERROR` | Changes the RF event debounce window. Persisted. |
| `CODE_ADD` | `<decimal>` in `[1, 16777215]` (24-bit) | `Gate: CODE_ACK:OK` / `CODE_ACK:EXISTS` / `CODE_ACK:FULL` / `CODE_ACK:ERROR` | Adds a 433 MHz code to the match list. Persisted. |
| `CODE_REMOVE` | `<decimal>` | `Gate: CODE_ACK:OK` / `CODE_ACK:NOT_FOUND` / `CODE_ACK:ERROR` | Removes a code from the list. Persisted. |
| `CODE_LIST` | none | `Gate: CODES:<code>,<code>,…` or `Gate: CODES:NONE` | Lists all registered codes as a single text frame (not a `CODE_ACK`). |
| `CODE_CLEAR` | none | `Gate: CODE_ACK:OK` | Empties the entire code list. Persisted. |

Unknown verbs are silently ignored (no NACK spam on the mesh).

### TRIGGERED event format

When a received RF code matches any registered entry, the firmware emits:

```
Gate: TRIGGERED:<decimal>
```

Example: `Gate: TRIGGERED:150910`. Downstream parsers can correlate the `<decimal>` against the list returned by `CODE_LIST` to identify which physical sensor fired.

### Examples

```
@ALL STATUS                    → Gate: STATUS: …
@Gate STATUS                   → Gate: STATUS: …
@Gate HB_OFF                   → Gate: HB_ACK:OK
@Gate HB_INTERVAL:5            → Gate: HB_ACK:OK
@Gate REBOOT                   → Gate: REBOOT_ACK:OK (then the Nano resets)
@Gate HITS_RESET               → Gate: HITS_RESET_ACK:OK
@Gate DEBOUNCE_SET:5           → Gate: DEBOUNCE_ACK:OK
@Gate CODE_LIST                → Gate: CODES:150910
@Gate CODE_ADD:4444222         → Gate: CODE_ACK:OK
@Gate CODE_ADD:150910          → Gate: CODE_ACK:EXISTS
@Gate CODE_REMOVE:4444222      → Gate: CODE_ACK:OK
@Gate CODE_REMOVE:404          → Gate: CODE_ACK:NOT_FOUND
@Gate CODE_CLEAR               → Gate: CODE_ACK:OK
@Other STATUS                  → (ignored)
```

## Firmware Logic

### setup()

1. Initialize USB serial at 115200 baud (debug)
2. Initialize SoftwareSerial at 9600 baud (Meshtastic)
3. Enable RCSwitch interrupt receiver on D2 (INT0)
4. Read `bootCount` from EEPROM, increment, write back
5. Load `hbEnabled` and `hbIntervalMin` from EEPROM (fall back to defaults on 0xFF / out-of-range)
6. Send the first STATUS frame

### loop()

1. **RF event handling:** When rc-switch receives a valid code, the 10 s debounce window is checked. If the code matches `CODE_OPEN`, `hitCount` is incremented and `Gate: TRIGGERED` is sent to the mesh and echoed on USB serial. `CODE_CLOSED` is handled the same way (when configured). Unrecognised codes are logged to USB serial as `RF unknown: <decimal>` and not forwarded.
2. **Inbound CMD handling:** `pollCmd()` drains the SoftwareSerial RX buffer into a line buffer. On `\n`, the line is dispatched to the verb handlers described in the [CMD Protocol](#cmd-protocol) section.
3. **STATUS heartbeat:** When `hbEnabled` is true and `hbIntervalMin * 60000` ms have elapsed since the last STATUS, send the STATUS frame on both the mesh UART and USB serial.

## Build and Upload

All commands use Make targets that wrap PlatformIO:

```bash
make build          # Compile firmware
make upload         # Flash to Nano via USB (auto-detects port)
make monitor        # Serial monitor at 115200 baud (Nano debug output)
make learn-sensor   # USB serial monitor tuned for discovering a new 433 MHz sensor code
make clean          # Clean build artifacts
```

Ensure the Nano is connected via USB. CH340 driver must be installed on the host.

## Debug Serial

The Nano's hardware UART (USB serial at 115200 baud) echoes all messages sent to Meshtastic plus unknown RF codes. Connect to the Nano's USB port and run `make monitor` to observe in real time.
