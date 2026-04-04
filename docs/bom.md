# Bill of Materials (~$51)


## Core Components

| # | Component | Purpose | ~Price |
|---|-----------|---------|--------|
| 1 | Heltec WiFi LoRa 32 V3 | LoRa bridge (Meshtastic firmware) | $18 |
| 2 | Arduino Nano (CH340) | Sensor bridge MCU | $1.50 |
| 3 | RXB6 433MHz receiver (8-pin SIP) | RF signal input. 2 groups of 4 pins, 25.4mm gap. Direct solder to PCB. | $1 |
| 4 | KERUI D026 door sensor | 433MHz open/close sensor | $4 |
| 5 | Waveshare Solar Power Mgr D | Solar UPS, dual 18650 | $8 |
| 6 | 2x 18650 3000mAh | Battery backup (~57h) | $4 |
| 7 | 6V 2W solar panel | Charging source | $4 |
| 8 | IP65 junction box 150x100x70mm | Weatherproof enclosure | $3 |
| 9 | Carrier PCB v2.2 (5x from JLCPCB) | 75x66mm custom board | $1 ea |

## Passive Components

| Ref | Value | Type | Purpose |
|-----|-------|------|---------|
| R1 | 2.2k | 1/4W axial | Logic level divider — series resistor (D3 to HELTEC_RX) |
| R2 | 3.3k | 1/4W axial | Logic level divider — shunt to GND (produces 3.0V from 5V) |
| R3 | 10k | 1/4W axial | Battery voltage divider — series (BAT_RAW to BAT_DIV) |
| R4 | 10k | 1/4W axial | Battery voltage divider — shunt to GND (BAT/2 to A0) |
| R5 | 10k | 1/4W axial | DE pull-up — holds RXB6 data enable pin high via 5V |
| C1 | 100nF | Ceramic disc/MLCC | Bypass capacitor near RXB6 VDD (high-frequency noise filter) |
| C2 | 100uF | Electrolytic radial (6.3mm dia) | Bulk capacitor on 5V bus (inrush/ripple smoothing) |

## Connectors and Hardware

| # | Component | Purpose |
|---|-----------|---------|
| 1 | 2x18 female pin headers (2.54mm) | Heltec socket |
| 2 | 2x15 female pin headers (2.54mm, 15.24mm spacing) | Nano socket |
| 3 | 2x 2-pin screw terminals (5.08mm) | J2 (PWR IN), J3 (BAT MON) |
| 4 | JST-PH 2mm 2-pin connector | J4 (power switch) |
| 5 | Toggle switch or JST-PH jumper | Inline power switch for J4 |
| 6 | SMA female bulkhead connector | 433MHz antenna feedthrough |
| 7 | PG7 cable gland | Weatherproof cable entry |
| 8 | 4x M3 standoffs + screws + nuts | PCB mounting (3.2mm holes) |

## Power Notes

- **Nano powered via 5V pin** (R12 on the socket), NOT via VIN. VIN has an onboard regulator that would cause a feedback loop if connected to the regulated 5V bus.
- **RXB6 powered from 5V** (pins 4 and 5), NOT 3.3V. The superheterodyne receiver has better sensitivity at 5V. The data output is still compatible with 5V logic on Nano D2.
- **Heltec powered via 5V** on L2. Its onboard regulator steps down to 3.3V internally.
- Total system draw: ~105mA from the Waveshare 5V output.
