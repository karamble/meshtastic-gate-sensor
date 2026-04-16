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
| SoftwareSerial | built-in | UART TX on D3 to Heltec (9600 baud). RX pin defined but unused. |

## Pin Configuration

Defined in `firmware/include/config.h`:

| Define | Value | Function |
|--------|-------|----------|
| `RF_PIN` | 2 | RXB6 DATA input. D2 = INT0 (required by RCSwitch `enableReceive`). |
| `SERIAL_TX` | 3 | SoftwareSerial TX to Heltec GPIO47 via level divider. |
| `SERIAL_RX` | 4 | SoftwareSerial RX (unused, placeholder — Heltec TX not connected). |

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

### Timing

| Define | Default | Description |
|--------|---------|-------------|
| `HEARTBEAT_MS` | 300000 (5 min) | Interval between "Online" heartbeat messages |
| `DEBOUNCE_MS` | 10000 (10 s) | Minimum time between accepted RF events. Collapses the KERUI retransmit burst (4–10 copies per trigger) into one mesh event per physical opening. |

## Message Format

All messages are sent as plain text over SoftwareSerial at 9600 baud. Meshtastic receives them as TEXTMSG via its serial module.

### Gate Events

```
Gate: TRIGGERED
```

A single event is emitted per physical trigger. The 10 s debounce collapses the KERUI retransmit burst into one mesh message. The sensor fires the same code on open and close, so there is no separate `OPEN` / `CLOSED` text.

### Heartbeat (every 5 minutes)

```
GATE NODE: Online
```

### Unknown RF Codes (debug output only, not sent to mesh)

```
RF unknown: 1234567
```

Printed to the Nano's USB serial (115200 baud) only, not forwarded to Meshtastic. Used by `make learn-sensor` to discover the decimal code for a new sensor.

## Firmware Logic

### setup()

1. Initialize USB serial at 115200 baud (debug)
2. Initialize SoftwareSerial at 9600 baud (Meshtastic)
3. Enable RCSwitch interrupt receiver on D2 (INT0)
4. Send startup heartbeat

### loop()

1. **RF event handling:** When rc-switch receives a valid code, the 10 s debounce window is checked. If the code matches `CODE_OPEN`, `Gate: TRIGGERED` is sent to the mesh and echoed on USB serial. If it matches `CODE_CLOSED` (when configured), `Gate: CLOSED` is sent. Unrecognised codes are logged to USB serial as `RF unknown: <decimal>` and not forwarded.
2. **Heartbeat:** Every 5 minutes, send `GATE NODE: Online` on both the mesh UART and USB serial.

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
