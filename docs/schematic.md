# Schematic Description


## Architecture

```
  KERUI D026          RXB6 433MHz        Arduino Nano         Heltec LoRa32 V3
  door sensor         receiver           (ATmega328P)         (Meshtastic)
  +-----------+       +----------+       +--------------+     +----------------+
  | 433 MHz   |~~~~~> | DATA  ---|------>| D2 (INT0)    |     |                |
  | open/close|       | DE <-R5- |--+    |              |     |                |
  +-----------+       | VDD      |  |    | D3 (TX)  ----|--+  |                |
                      | GND      |  |    |              |  |  |                |
                      +----------+  |    | A0 <---------|--|--|- BAT divider   |
                                    |    |              |  |  |                |
                                    |    |         5V --|--|--|- 5V            |
                                    |    |        GND --|--|--|- GND           |
                                    |    +--------------+  |  |                |
                                    |                      |  |                |
                                    |    Logic Level Div   |  |                |
                                    |    +------------+    |  |                |
                                    |    | R1 2.2k    |<---+  |                |
                                    |    |   +--jct---|------->| GPIO47 (RX)   |
                                    |    | R2 3.3k    |       |                |
                                    |    |   +--GND   |       |                |
                                    |    +------------+       +----------------+
                                    |
  Waveshare Solar     J4 (switch)   |
  Power Mgr D         +-----+      |
  +-----------+  J2   |IN|OUT|------+----> 5V bus
  | 5V OUT  --|------->  |   |
  | BAT pin --|--J3-->| BAT divider: R3(10k)+R4(10k) -> A0
  | GND     --|------>| GND bus
  +-----------+       +-----+
```

## Net List

| Net | Description | Connected Pins |
|-----|-------------|----------------|
| GND | Ground | Heltec L1, R1; Nano L4, R14; RXB6 pins 2,3,8; R2 pad2; R4 pad2; C1 pad2; C2 pad2; J2 pin2; J3 pin2 |
| 5V | Main power bus | Heltec L2; Nano R12 (5V pin); RXB6 pins 4,5 (VDD); R5 pad1; C1 pad1; C2 pad1; J4 pin2 (switch out) |
| 5V_IN | Unswitched input | J2 pin1 (Waveshare 5V); J4 pin1 (switch in) |
| 3V3 | 3.3V (Heltec only) | Heltec R2, R3 (bridged, not distributed) |
| D3 | SoftwareSerial TX | Nano L6 (D3); R1 pad1 |
| D4 | RF DATA (named D4 on PCB, mapped to Nano D2) | Nano L5 (D2/INT0); RXB6 pin 7 (DATA) |
| BAT_DIV | Battery midpoint | Nano R4 (A0); R3 pad2; R4 pad1 |
| BAT_RAW | Battery raw voltage | J3 pin1 (Waveshare BAT); R3 pad1 |
| HELTEC_RX | Level-shifted serial | R1 pad2; R2 pad1; Heltec L13 (GPIO47) |
| DE | RXB6 data enable | RXB6 pin 6 (DE); R5 pad2 |

**Note on D4 net naming:** The PCB net is called "D4" for historical reasons. On the Nano, this signal connects to physical pin D2 (L5), which provides INT0 for RCSwitch interrupt-driven reception. The firmware uses `RF_PIN 2` (D2).

## Pin Assignments

### Heltec WiFi LoRa 32 V3 (U3) — 2x18 pins

Left row (L1-L18), top to bottom (USB end to antenna end):

| Pin | Label | Net | Function |
|-----|-------|-----|----------|
| L1 | GND | GND | Ground |
| L2 | 5V | 5V | Power input (from 5V bus) |
| L3 | Ve | -- | |
| L4 | Ve | -- | |
| L5-L12 | GPIO44,TX43,RST,... | -- | Unused |
| L13 | GPIO47 | HELTEC_RX | **Serial RX** (Meshtastic serial module) |
| L14-L18 | 48,26,21,20,19 | -- | Unused |

Right row (R1-R18):

| Pin | Label | Net | Function |
|-----|-------|-----|----------|
| R1 | GND | GND | Ground |
| R2 | 3V3 | 3V3 | 3.3V output (bridged to R3) |
| R3 | 3V3 | 3V3 | 3.3V output |
| R4-R18 | GPIO37-7 | -- | Unused |

**Why GPIO47 instead of GPIO44:** GPIO44 is shared with the CP2102 USB-UART on the Heltec V3. Using GPIO47 (L13) avoids conflict and allows USB serial to remain available for Meshtastic configuration.

### Arduino Nano (U1) — 2x15 pins, 15.24mm (600mil) row spacing

Left row (L1-L15):

| Pin | Label | Net | Function |
|-----|-------|-----|----------|
| L1 | D1 | -- | |
| L2 | D0 | -- | |
| L3 | RST | -- | |
| L4 | GND | GND | Ground |
| L5 | D2 | D4 | **RF DATA input** (INT0 for RCSwitch) |
| L6 | D3 | D3 | **SoftwareSerial TX** to Heltec |
| L7-L15 | D4-D12 | -- | Unused |

Right row (R1-R15):

| Pin | Label | Net | Function |
|-----|-------|-----|----------|
| R1-R3 | D13,3V3,REF | -- | |
| R4 | A0 | BAT_DIV | **Battery ADC** (voltage divider midpoint) |
| R5-R11 | A1-A7 | -- | Unused |
| R12 | 5V | 5V | **Power input** (from 5V bus, not VIN) |
| R13 | RST | -- | |
| R14 | GND | GND | Ground |
| R15 | VIN | -- | **Not connected** (VIN has onboard regulator; shorting to 5V feeds output back to input) |

### RXB6 433MHz Receiver (U2) — 8-pin SIP, direct solder

Two groups of 4 pins at 2.54mm pitch, 25.4mm gap between groups. Module body extends to the right of the pin column.

| Pin | Group | Label | Net | Function |
|-----|-------|-------|-----|----------|
| 1 | 1 | ANT | -- | Antenna (17.3cm wire or SMA) |
| 2 | 1 | GND | GND | Ground |
| 3 | 1 | GND | GND | Ground |
| 4 | 1 | VDD | 5V | Power (5V, not 3.3V) |
| 5 | 2 | VDD | 5V | Power (5V) |
| 6 | 2 | DE | DE | Data Enable (pulled high via R5) |
| 7 | 2 | DATA | D4 | Data output to Nano D2 |
| 8 | 2 | GND | GND | Ground |

## Logic Level Divider (5V to 3.3V)

Converts the Nano's 5V SoftwareSerial TX to a safe level for the Heltec's 3.3V GPIO47.

```
  Nano D3 (5V) ──── R1 (2.2k) ────┬──── Heltec GPIO47 (HELTEC_RX)
                                   │
                                R2 (3.3k)
                                   │
                                  GND
```

Output voltage: 5V x 3.3k / (2.2k + 3.3k) = **3.0V** (safe for 3.3V logic input)

## Battery Voltage Divider

Scales the Waveshare BAT pin voltage (0-8.4V for 2S 18650) to the Nano's 0-5V ADC range.

```
  J3 BAT+ (BAT_RAW) ── R3 (10k) ──┬── Nano A0 (BAT_DIV)
                                    │
                                 R4 (10k)
                                    │
                                   GND
```

ADC reads BAT/2. Firmware multiplies by 2 to get actual voltage. With 5V reference and 10-bit ADC: resolution = 5.0 / 1024 * 2 = ~9.8mV per step.

## Power Circuit

```
  J2 (Waveshare 5V OUT) ──[5V_IN]──> J4 pin1 (switch IN)
                                           │
                                      [toggle switch]
                                           │
                                      J4 pin2 (switch OUT) ──[5V]──> V5 bus
                                                                        │
                                                    ┌───────────────────┼───────────────┐
                                                    │                   │               │
                                               Heltec L2          Nano R12 (5V)    RXB6 VDD
                                                                                   (pins 4,5)
```

All modules are powered from the switched 5V bus. The Nano is powered via its 5V pin (bypassing its onboard voltage regulator). The RXB6 runs on 5V for better sensitivity.

## Hardening Components

| Ref | Value | Purpose | Placement |
|-----|-------|---------|-----------|
| R5 | 10k | DE pull-up to 5V | Between V5 bus and RXB6 pin 6 (DE). Keeps data enable active. |
| C1 | 100nF ceramic | Bypass capacitor | Near RXB6 VDD (pin 4). Filters high-frequency noise on power supply. |
| C2 | 100uF electrolytic | Bulk capacitor | On V5/GND bus near J4 switch. Smooths inrush current and voltage dips. |
