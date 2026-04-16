# Meshtastic Gate & Door Sensor

Carrier board + firmware that bridges a cheap 433 MHz wireless door sensor onto a private Meshtastic LoRa mesh. A trigger on the door raises an event on the mesh — no WiFi, no cloud, no gateway.

## Architecture

```
KERUI D026 (433 MHz) → RXB6 Receiver → Arduino Nano → UART → Heltec LoRa32 V3 → LoRa mesh
```

The 433 MHz sensor broadcasts a fixed code on every open/close event. An Arduino Nano decodes the code with `rc-switch` on D2 (INT0) and forwards a short text line over SoftwareSerial D3 → voltage divider → Heltec GPIO47. The Heltec runs stock Meshtastic with the serial module in `TEXTMSG` mode at 9600 baud and relays each line into the mesh. A 10 s debounce collapses the KERUI retransmit burst into one mesh event per physical opening.

Firmware emits `Gate: TRIGGERED` on every event and `GATE NODE: Online` every 5 minutes as a heartbeat. KERUI D026 sends the same code on open and close, so `CODE_CLOSED` is disabled by default — one code per event is all you get.

Powered by a Waveshare Solar Power Manager D with 2× 18650 batteries and a 6 V 2 W solar panel. Total draw ≈ 105 mA.

## Carrier PCB v2.3

Custom 75×66 mm 2-layer board with:

- Heltec LoRa32 V3 socket (2×18 pins)
- Arduino Nano socket (2×15 pins, 15.24 mm row spacing)
- RXB6 433 MHz receiver (8-pin SIP, direct solder)
- Logic level divider 2.2k / 3.3k (5V → 3.0V on GPIO47)
- Hardening: 10k DE pull-up, 100nF bypass, 100µF bulk
- GND copper pour on both layers
- 0 DRC violations, 34 netlist self-checks pass

Generated programmatically by `pcb/gate_sensor_pcb_v2.py` and validated with KiCad 10.

## Build

Requires Docker (for KiCad CLI) and PlatformIO.

```bash
make help            # show all targets

# PCB
make drc             # design rule check
make fab             # export Gerbers + drill for JLCPCB

# Firmware
make build           # compile
make upload          # flash the Nano
make monitor         # 115200 USB serial monitor
make learn-sensor    # discover a new 433 MHz sensor's code

# Heltec Meshtastic flash & configure (stock firmware)
./scripts/flash-heltec-meshtastic.sh           # defaults (auto-detect, EU_868)
./scripts/flash-heltec-meshtastic.sh --help
```

The flash script downloads the latest stock Meshtastic release, flashes the Heltec V3, applies the gate-sensor config (GPIO47 RX at 9600 baud, TEXTMSG mode, owner name `GateSensor`/`GATE`, GPS disabled, Bluetooth disabled) and verifies every setting before closing.

## Learning a new sensor

If you're using a different 433 MHz sensor than the KERUI D026, discover its code with:

```bash
make learn-sensor
```

Trigger the sensor a few times and watch for repeating `RF unknown: <decimal>` lines. Copy the decimal into `CODE_OPEN` in `firmware/include/config.h`, re-run `make upload`, and the sensor will fire `Gate: TRIGGERED` on the mesh. See [docs/learn-sensor.md](docs/learn-sensor.md) for details.

## Project Structure

```
├── Makefile                      # build targets (KiCad Docker + PlatformIO)
├── pcb/
│   ├── gate_sensor_pcb_v2.py     # PCB generator script
│   ├── gate_sensor_v2.kicad_pcb  # generated board
│   ├── test_netlist.py           # 34-check PCB self-test
│   ├── generate_assembly.py      # 3D assembly view generator
│   └── logo_silk.json            # raccoon logo silkscreen data
├── firmware/
│   ├── platformio.ini            # PlatformIO config (board=nanoatmega328new)
│   ├── src/main.cpp              # bridge firmware
│   └── include/config.h          # sensor codes, pin defs, timing
├── scripts/
│   └── flash-heltec-meshtastic.sh  # Heltec flash + config
├── docs/
│   ├── schematic.md              # schematic + netlist
│   ├── pcb.md                    # PCB design documentation
│   ├── firmware.md               # firmware documentation
│   ├── assembly.md               # assembly and setup guide
│   ├── learn-sensor.md           # discovering a new 433 MHz sensor code
│   ├── bom.md                    # bill of materials
│   └── ordering.md               # JLCPCB ordering guide
└── pin-outs/                     # component pinout reference images
```

## BOM

~$52 total for one complete sensor node. See [docs/bom.md](docs/bom.md) for the full bill of materials.

## License

MIT
