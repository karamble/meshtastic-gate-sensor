# Assembly and Setup Guide


## Prerequisites

- Soldering iron with fine tip (for through-hole components)
- Solder (0.8mm rosin core recommended)
- Wire strippers and flush cutters
- Multimeter (for continuity checks)
- USB-A to Mini-B cable (for Arduino Nano)
- USB-C cable (for Heltec LoRa32 V3)
- Computer with PlatformIO installed

## Phase 1: PCB Assembly

### Soldering Order

Solder components in this order (smallest to largest, inside to outside):

1. **Passive components (R1, R2, R5, C1)**
   - R1 (2.2k) — horizontal, between Nano and RXB6 areas
   - R2 (3.3k) — vertical, below R1 junction
   - R5 (10k) — horizontal, left of RXB6 pin 6 area (DE pull-up)
   - C1 (100nF ceramic) — horizontal, near RXB6 VDD area

2. **C2 (100uF electrolytic)** — observe polarity (+) marked on silkscreen and capacitor stripe

3. **Pin headers for Heltec (U3)** — 2x18 female pin sockets. Solder from the back side. Use the Heltec module itself as an alignment jig (insert pins, flip, solder).

4. **Pin headers for Arduino Nano (U1)** — 2x15 female pin sockets, 15.24mm (600mil) row spacing. Same technique.

5. **RXB6 receiver (U2)** — direct solder, 8-pin SIP. This module is NOT socketed. Align pin 1 (ANT) to the board marking. The module body extends to the right of the pin column.

6. **Connectors**
   - J2 (PWR IN) — 2-pin screw terminal at bottom left. Pin 1 = +5V, Pin 2 = GND.
   - J4 (PWR SW) — JST-PH 2mm connector. Pin 1 = IN (from J2), Pin 2 = OUT (to 5V bus).

### Post-Solder Checks

Before inserting any modules, use a multimeter to verify:

1. **No shorts:** Check resistance between 5V and GND buses (should be high, not zero)
2. **Continuity:** Verify J2 pin1 to J4 pin1 (5V_IN path)
3. **Divider resistors:** Measure across R1+R2 (should read ~5.5k)
4. **Power switch:** With a jumper wire in J4, verify J2 pin1 reaches the 5V bus

## Phase 2: Learning the Sensor Code

The production firmware already logs every decoded 433 MHz code to USB serial, so no separate learning sketch is needed. The default `CODE_OPEN` in `firmware/include/config.h` is preloaded with the KERUI D026 value (`150910`) — skip this phase if you are using that exact sensor and it triggers correctly.

### Learning Procedure

1. **Flash the current firmware:**
   ```bash
   make upload
   ```

2. **Open the learning monitor:**
   ```bash
   make learn-sensor
   ```
   This streams the Nano's USB serial at 115200 baud.

3. **Trigger the sensor** (open/close the door) several times. Unknown codes appear as:
   ```
   RF unknown: 150910
   RF unknown: 150910
   RF unknown: 150910
   ```
   EV1527 / PT2260-style sensors retransmit the same code 4–10 times per trigger — ignore one-off values (noise, neighboring remotes).

4. **Update `firmware/include/config.h`:**
   ```c
   #define CODE_OPEN    150910   // your learned value
   ```
   KERUI D026 emits the same code on open and close, so `CODE_CLOSED` stays at `0` (disabled). If your sensor emits a distinct close code, set it there.

5. **Re-flash and verify:**
   ```bash
   make upload
   make monitor
   ```
   Trigger the sensor and confirm you see `Gate: TRIGGERED` lines (one per physical trigger — the 10 s debounce collapses each retransmit burst into a single mesh event).

See [learn-sensor.md](learn-sensor.md) for the full walkthrough.

## Phase 3: Meshtastic Flash & Configure

The Heltec LoRa32 V3 runs stock Meshtastic firmware with the serial module enabled. Both the firmware flash and the serial-module configuration are automated by `scripts/flash-heltec-meshtastic.sh`.

### Prerequisites

- Python tools: `pip install esptool meshtastic`
- GitHub CLI: `gh` (used to fetch the latest Meshtastic release)
- `.env` file at the project root with your 256-bit mesh PSK:
  ```bash
  cp .env.example .env
  # Edit .env and set MESH_PSK to a base64-encoded 256-bit key
  ```

### One-command Flash + Configure

Connect the Heltec via USB-C, put it in boot mode (hold BOOT, press and release RST, release BOOT), then run:

```bash
./scripts/flash-heltec-meshtastic.sh              # defaults: auto-detect port, EU_868, latest release
./scripts/flash-heltec-meshtastic.sh -r US        # US region
./scripts/flash-heltec-meshtastic.sh --help       # all options
```

The script downloads the latest stock Meshtastic release, erases flash, writes firmware + BLE OTA + LittleFS, then applies the full gate-sensor config and verifies every setting before closing.

### Settings Applied

| Setting | Value | Notes |
|---------|-------|-------|
| `lora.region` | `EU_868` (configurable `-r`) | Select the region your mesh operates in |
| Channel PSK (index 0) | `$MESH_PSK` | 256-bit private-channel key from `.env` |
| `position.gps_mode` | `NOT_PRESENT` | Gate sensor has no GPS module |
| `telemetry.device_update_interval` | `1800` | Telemetry broadcast every 30 min |
| `serial.enabled` | `true` | Serial module on |
| `serial.echo` | `false` | Don't echo mesh text back out the UART |
| `serial.rxd` | `47` | GPIO47 (Heltec L13). NOT GPIO44 (conflicts with CP2102 USB-UART). |
| `serial.txd` | `48` | Parked on unused GPIO. NOT `0` — GPIO0 is the ESP32-S3 boot strap and silently kills RX. |
| `serial.baud` | `BAUD_9600` | Matches Nano SoftwareSerial (`MESH_BAUD`) |
| `serial.timeout` | `0` | Defaults |
| `serial.mode` | `TEXTMSG` | Each UART line arrives in the mesh as a chat message |
| Owner long / short | `GateSensor` / `GATE` | Human-readable node identity |
| `bluetooth.enabled` | `false` | Not used; saves power |

Separate invocations are available if you need them:

```bash
./scripts/flash-heltec-meshtastic.sh --flash-only       # write firmware, skip config
./scripts/flash-heltec-meshtastic.sh --config-only      # configure an already-flashed device
./scripts/flash-heltec-meshtastic.sh --confirm-config   # read back and verify without re-applying
```

### Verify Meshtastic

1. Insert the Heltec into the PCB socket
2. Power on via J4 switch
3. On another Meshtastic node on the same channel/PSK (phone app or second device), you should see the heartbeat: `GATE NODE: Online` every 5 minutes.

## Phase 4: Enclosure Assembly

### Components

- IP65 junction box 150x100x70mm
- SMA female bulkhead connector (for 433MHz antenna)
- PG7 cable gland (for solar panel cable)
- M3 standoffs, screws, and nuts (4 sets)
- 17.3cm wire antenna or external 433MHz antenna with SMA

### Assembly Steps

1. **Drill enclosure holes:**
   - SMA bulkhead hole on one side (typically 6.5mm)
   - PG7 cable gland hole on the bottom (12mm)
   - Optional: second PG7 for USB access during development

2. **Mount standoffs:** Install M3 standoffs inside the enclosure, matching the PCB's four corner mounting holes (4mm inset from edges).

3. **Install SMA connector:** Mount the SMA bulkhead connector. Connect a short wire from the SMA inner conductor to RXB6 pin 1 (ANT). Alternatively, solder a 17.3cm wire antenna directly to pin 1.

4. **Install cable gland:** Thread the solar panel and Waveshare power cables through the PG7 gland before connecting to J2.

5. **Mount PCB:** Secure the PCB to the standoffs with M3 screws.

6. **Wire power:**
   - Waveshare 5V OUT to J2 (observe polarity: pin 1 = +5V, pin 2 = GND)
   - Toggle switch between J4 pin 1 and pin 2 (or insert a JST-PH jumper)

7. **Insert modules:** Plug in the Heltec V3 and Arduino Nano into their sockets. The Heltec's USB-C connector should align with the board's USB-C notch.

8. **Seal:** Close the enclosure. Tighten the PG7 gland around the cable. Ensure the IP65 gasket is seated properly.

## Phase 5: Testing

### Bench Test (before enclosure)

1. Connect Waveshare Solar Power Manager D with batteries
2. Wire 5V and GND to J2
3. Insert jumper or switch on J4
4. Power on — Heltec should boot Meshtastic, Nano should send `GATE NODE: Online` heartbeat
5. Trigger the KERUI D026 sensor — each physical trigger should emit a single `Gate: TRIGGERED` message on the mesh (the 10 s debounce collapses the retransmit burst)

### Field Test

1. Mount the enclosure at the gate location
2. Position the solar panel for maximum sun exposure
3. Verify RF range: trigger the sensor at maximum expected distance
4. Monitor the mesh network for 24 hours:
   - `GATE NODE: Online` heartbeats every 5 minutes
   - `Gate: TRIGGERED` within a few seconds of each open/close

### Troubleshooting

| Symptom | Check |
|---------|-------|
| No heartbeat messages | Verify Meshtastic serial config (`serial.rxd=47`, `serial.txd=48`, `BAUD_9600`, `TEXTMSG`). Re-run `flash-heltec-meshtastic.sh --confirm-config`. Check 5V bus. |
| Gate events not detected | Verify `CODE_OPEN` in `firmware/include/config.h` matches your sensor — run `make learn-sensor` and check for `RF unknown: <decimal>` lines. Check RXB6 antenna. |
| Duplicate events per trigger | Confirm `DEBOUNCE_MS` is 10000 (10 s). Shorter values let the KERUI retransmit burst through as multiple events. |
| Messages garbled | Check logic level divider (R1/R2). Measure voltage at Heltec GPIO47 — should be ~3.0V when Nano TX is high. |
| No RF reception | Verify RXB6 is powered (5V on pins 4,5). Check DE pin pulled high (R5). Try shorter antenna distance. |
| Nano not booting | Verify power on Nano 5V pin (R12), not VIN. Check for solder bridges. Clone Nanos use optiboot — `platformio.ini` must be `board=nanoatmega328new` (115200 baud bootloader). |
| Meshtastic RX dead after config | If `serial.txd=0` got set, the ESP32-S3 UART init fails silently and also kills RX. Re-run the flash script to reset `txd=48`. |
