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

```c
#define CODE_OPEN    150910  // KERUI D026 — transmits same code on open and close
#define CODE_CLOSED  0       // disabled — sensor does not emit a distinct close code
```

`CODE_OPEN` ships pre-calibrated for the KERUI D026 used in this build. For any other 433 MHz sensor, discover its decimal code with `make learn-sensor` — the production firmware prints every decoded code to USB serial as `RF unknown: <decimal>`. Set `CODE_OPEN` to the repeating value and re-flash. See [learn-sensor.md](learn-sensor.md) for the full procedure.

`CODE_CLOSED` stays at `0` (disabled) for the KERUI D026 because it emits the same code on open and close. If your sensor emits a distinct close code, set it here.

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
| `DEBOUNCE_MS` | 10000 (10 s) | Minimum time between accepted RF events. Collapses the KERUI retransmit burst (4–10 copies per trigger) into one mesh event per physical opening. |

### EEPROM

| Define | Addr | Size | Purpose |
|--------|------|------|---------|
| `EEPROM_ADDR_BOOTCOUNT` | 0 | 2 bytes (`uint16_t`) | Persistent boot counter, incremented once per `setup()` and reported in the STATUS frame's `Boot:` field. A fresh `0xFFFF` EEPROM reads as "never written" and resets to 0 before the first increment. |
| `EEPROM_ADDR_HB_EN` | 2 | 1 byte (`uint8_t`) | Heartbeat enabled flag. `0xFF` (fresh chip) and `1` mean on; `0` means off. Mutated by `HB_ON` / `HB_OFF`. |
| `EEPROM_ADDR_HB_MIN` | 3 | 1 byte (`uint8_t`) | Heartbeat interval in minutes. `0xFF` or any value outside `[HB_MIN_MIN, HB_MIN_MAX]` falls back to `DEFAULT_HB_MIN`. Mutated by `HB_INTERVAL:<min>`. |

Writes use `EEPROM.update` so unchanged values don't consume write cycles.

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
Gate: TRIGGERED
```

A single event is emitted per physical trigger. The 10 s debounce collapses the KERUI retransmit burst into one mesh message. The sensor fires the same code on open and close, so there is no separate `OPEN` / `CLOSED` text. Event frames do not classify a node on their own — DigiNode CC relies on the node having already been classified via a prior STATUS broadcast.

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
| `HB_ON` | none | `Gate: HB_ACK:OK` | Enables periodic STATUS broadcasts. Persisted in EEPROM. |
| `HB_OFF` | none | `Gate: HB_ACK:OK` | Suspends periodic STATUS broadcasts. Boot STATUS and `@… STATUS` queries still work. Persisted in EEPROM. |
| `HB_INTERVAL` | `<minutes>` in `[1,60]` | `Gate: HB_ACK:OK` on valid, `Gate: HB_ACK:ERROR` on invalid | Changes the heartbeat interval. Resets the timer so the next STATUS fires `<minutes>` from the command, not from the previous heartbeat. Persisted in EEPROM. |

Unknown verbs are silently ignored (no NACK spam on the mesh).

### Examples

```
@ALL STATUS                 → Gate: STATUS: …
@Gate STATUS                → Gate: STATUS: …
@Gate HB_OFF                → Gate: HB_ACK:OK
@Gate HB_ON                 → Gate: HB_ACK:OK
@Gate HB_INTERVAL:5         → Gate: HB_ACK:OK   (next STATUS in 5 min)
@Gate HB_INTERVAL:0         → Gate: HB_ACK:ERROR
@Gate HB_INTERVAL:99        → Gate: HB_ACK:ERROR
@Other STATUS               → (ignored)
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
