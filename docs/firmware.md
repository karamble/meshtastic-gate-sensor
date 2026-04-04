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

### Sensor Codes (required)

```c
#define CODE_OPEN    0  // Replace with learned OPEN code
#define CODE_CLOSED  0  // Replace with learned CLOSED code
```

These must be learned from your specific KERUI D026 sensor using the RCSwitch examples (see [assembly.md](assembly.md) for the learning procedure).

### Timing

| Define | Default | Description |
|--------|---------|-------------|
| `HEARTBEAT_MS` | 300000 (5 min) | Interval between "Online" heartbeat messages |
| `DEBOUNCE_MS` | 200 | Minimum time between accepted RF events (filters retransmissions) |

## Message Format

All messages are sent as plain text over SoftwareSerial at 9600 baud. Meshtastic receives them as TEXTMSG via its serial module.

### Gate Events

```
Gate: OPEN
Gate: CLOSED
```

### Heartbeat (every 5 minutes)

```
GATE NODE: Online
```

### Unknown RF Codes (debug output only, not sent to mesh)

```
RF unknown: 1234567
```

This is printed to the Nano's USB serial (115200 baud) only, not forwarded to Meshtastic. Useful during the learning phase.

## Firmware Logic

### setup()

1. Initialize USB serial at 115200 baud (debug)
2. Initialize SoftwareSerial at 9600 baud (Meshtastic)
3. Enable RCSwitch interrupt receiver on D2 (INT0)
4. Send startup heartbeat

### loop()

1. **RF event handling:** When RCSwitch receives a valid code, debounce (200ms) and send the appropriate gate event message. Unknown codes are logged to USB serial.
2. **Heartbeat:** Every 5 minutes, send "Online" status.

## Build and Upload

All commands use Make targets that wrap PlatformIO:

```bash
make build     # Compile firmware
make upload    # Flash to Nano via USB (auto-detects port)
make monitor   # Serial monitor at 115200 baud (Nano debug output)
make clean     # Clean build artifacts
```

Ensure the Nano is connected via USB. CH340 driver must be installed on the host.

## Debug Serial

The Nano's hardware UART (USB serial at 115200 baud) echoes all messages sent to Meshtastic plus unknown RF codes. Connect to the Nano's USB port and run `make monitor` to observe in real time.
