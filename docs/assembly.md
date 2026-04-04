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

1. **Passive components (R1-R5, C1)**
   - R1 (2.2k) — horizontal, between Nano and RXB6 areas
   - R2 (3.3k) — vertical, below R1 junction
   - R3 (10k) — horizontal, right of Nano area
   - R4 (10k) — vertical, below R3 junction
   - R5 (10k) — horizontal, left of RXB6 pin 6 area (DE pull-up)
   - C1 (100nF ceramic) — horizontal, near RXB6 VDD area

2. **C2 (100uF electrolytic)** — observe polarity (+) marked on silkscreen and capacitor stripe

3. **Pin headers for Heltec (U3)** — 2x18 female pin sockets. Solder from the back side. Use the Heltec module itself as an alignment jig (insert pins, flip, solder).

4. **Pin headers for Arduino Nano (U1)** — 2x15 female pin sockets, 15.24mm (600mil) row spacing. Same technique.

5. **RXB6 receiver (U2)** — direct solder, 8-pin SIP. This module is NOT socketed. Align pin 1 (ANT) to the board marking. The module body extends to the right of the pin column.

6. **Connectors**
   - J2 (PWR IN) — 2-pin screw terminal at bottom left. Pin 1 = +5V, Pin 2 = GND.
   - J3 (BAT MON) — 2-pin screw terminal at bottom right. Pin 1 = BAT+, Pin 2 = GND.
   - J4 (PWR SW) — JST-PH 2mm connector. Pin 1 = IN (from J2), Pin 2 = OUT (to 5V bus).

### Post-Solder Checks

Before inserting any modules, use a multimeter to verify:

1. **No shorts:** Check resistance between 5V and GND buses (should be high, not zero)
2. **Continuity:** Verify J2 pin1 to J4 pin1 (5V_IN path)
3. **Divider resistors:** Measure across R1+R2 (should read ~5.5k), R3+R4 (should read ~20k)
4. **Power switch:** With a jumper wire in J4, verify J2 pin1 reaches the 5V bus

## Phase 2: Learning Sensor Codes

Before configuring the main firmware, you need to discover the RF codes transmitted by your KERUI D026 sensor.

### Learning Procedure

1. **Upload the RCSwitch ReceiveDemo sketch** to the Nano:
   - In PlatformIO, open the RCSwitch library examples
   - Use the `ReceiveDemo_Simple` example
   - Ensure the interrupt pin matches D2 (INT0): `mySwitch.enableReceive(0);` (interrupt 0 = pin D2)
   - Upload and open serial monitor at 9600 baud

2. **Trigger the sensor:**
   - Open the gate/door to trigger the OPEN event
   - Note the decimal code shown in the serial monitor
   - Close the gate/door to trigger the CLOSED event
   - Note the decimal code

3. **Update config.h:**
   ```c
   #define CODE_OPEN    1234567  // Replace with your OPEN code
   #define CODE_CLOSED  7654321  // Replace with your CLOSED code
   ```

4. **Build and upload the main firmware:**
   ```bash
   make build && make upload
   ```

5. **Verify:** Open `make monitor` (115200 baud). Trigger the sensor and confirm you see `Gate: OPEN` and `Gate: CLOSED` messages.

## Phase 3: Meshtastic Configuration

The Heltec LoRa32 V3 must be running Meshtastic firmware with the serial module enabled.

### Flash Meshtastic

1. Download the latest Meshtastic firmware from https://meshtastic.org/downloads
2. Flash the Heltec V3 variant using the Meshtastic web flasher or `esptool.py`

### Configure Serial Module

Using the Meshtastic Python CLI, app, or web interface:

```bash
meshtastic --set serial.enabled true
meshtastic --set serial.rxd 47
meshtastic --set serial.baud BAUD_9600
meshtastic --set serial.mode TEXTMSG
```

| Setting | Value | Notes |
|---------|-------|-------|
| `serial.enabled` | `true` | Enable the serial module |
| `serial.rxd` | `47` | GPIO47 (Heltec L13). NOT GPIO44 (conflicts with CP2102). |
| `serial.txd` | `0` | Disabled (Nano does not receive from Heltec) |
| `serial.baud` | `BAUD_9600` | Must match firmware `MESH_BAUD` |
| `serial.mode` | `TEXTMSG` | Messages appear as text in the mesh chat |

### Verify Meshtastic

1. Insert the Heltec into the PCB socket
2. Power on via J4 switch
3. On another Meshtastic node (phone app or second device), you should see heartbeat messages: `GATE NODE: Online [BATT OK] 4.02V`

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
   - Waveshare BAT pin to J3 pin 1, Waveshare GND to J3 pin 2
   - Toggle switch between J4 pin 1 and pin 2 (or insert a JST-PH jumper)

7. **Insert modules:** Plug in the Heltec V3 and Arduino Nano into their sockets. The Heltec's USB-C connector should align with the board's USB-C notch.

8. **Seal:** Close the enclosure. Tighten the PG7 gland around the cable. Ensure the IP65 gasket is seated properly.

## Phase 5: Testing

### Bench Test (before enclosure)

1. Connect Waveshare Solar Power Manager D with batteries
2. Wire 5V and GND to J2, BAT to J3
3. Insert jumper or switch on J4
4. Power on — Heltec should boot Meshtastic, Nano should send heartbeat
5. Trigger KERUI D026 sensor — verify messages on the mesh network
6. Check battery voltage reading (should match multimeter measurement within ~0.1V)

### Field Test

1. Mount the enclosure at the gate location
2. Position the solar panel for maximum sun exposure
3. Verify RF range: trigger the sensor at maximum expected distance
4. Monitor the mesh network for 24 hours:
   - Heartbeats every 5 minutes
   - Battery voltage stable or rising (with solar)
   - Gate events within a few seconds of triggering

### Troubleshooting

| Symptom | Check |
|---------|-------|
| No heartbeat messages | Verify Meshtastic serial config (GPIO47, 9600 baud, TEXTMSG). Check 5V bus. |
| Gate events not detected | Verify sensor codes in config.h. Check RXB6 antenna. Run `make monitor` for debug output. |
| Wrong battery voltage | Verify R3/R4 values (both 10k). Check J3 wiring polarity. |
| Messages garbled | Check logic level divider (R1/R2). Measure voltage at Heltec GPIO47 — should be ~3.0V when Nano TX is high. |
| No RF reception | Verify RXB6 is powered (5V on pins 4,5). Check DE pin pulled high (R5). Try shorter antenna distance. |
| Nano not booting | Verify power on Nano 5V pin (R12), not VIN. Check for solder bridges. |
