# GoTailMe Gate & Door Sensor

Meshtastic gate sensor carrier board — monitors 433 MHz wireless door/window sensors and relays open/close events to a LoRa mesh network.

## Architecture

```
KERUI D026 (433MHz) → RXB6 Receiver → Arduino Nano → UART → Heltec LoRa32 V3 → Meshtastic LoRa Mesh
```

A 433 MHz wireless door sensor broadcasts an RF code on every open/close event. An Arduino Nano receives the code via an RXB6 superheterodyne receiver and forwards plain text over UART to a Heltec LoRa32 V3 running Meshtastic firmware. Meshtastic relays the message to your private channel.

Powered by a Waveshare Solar Power Manager D with 2x 18650 batteries and a 6V 2W solar panel.

## Carrier PCB v2.2

Custom 75x66mm 2-layer carrier board with:
- Heltec LoRa32 V3 socket (2x18 pins)
- Arduino Nano socket (2x15 pins)
- RXB6 433MHz receiver (8-pin SIP, direct solder)
- Logic level divider (5V → 3.0V for UART)
- Hardening: DE pull-up, bypass cap, bulk cap
- GND copper pour on both layers
- 0 DRC violations

Generated programmatically by `pcb/gate_sensor_pcb_v2.py` and validated with KiCad 10.

## Build

Requires Docker (for KiCad CLI) and PlatformIO.

```bash
make help           # show all targets

# PCB
make drc            # design rule check
make fab            # export Gerbers + drill for JLCPCB

# Firmware
make build          # compile
make upload         # flash to Nano
make monitor        # serial monitor
```

## Project Structure

```
├── Makefile                    # build targets (KiCad Docker + PlatformIO)
├── pcb/
│   ├── gate_sensor_pcb_v2.py  # PCB generator script
│   ├── gate_sensor_v2.kicad_pcb
│   └── logo_silk.json         # raccoon logo silkscreen data
├── firmware/
│   ├── platformio.ini
│   ├── src/main.cpp           # bridge firmware
│   └── include/config.h       # sensor codes, pin defs, timing
├── docs/
│   ├── schematic.md           # full schematic description
│   ├── pcb.md                 # PCB design documentation
│   ├── firmware.md            # firmware documentation
│   ├── assembly.md            # assembly and setup guide
│   ├── bom.md                 # bill of materials
│   └── ordering.md            # JLCPCB ordering guide
└── pin-outs/                  # component pinout references (WebP)
```

## BOM

~$52 total for one complete sensor node. See [docs/bom.md](docs/bom.md) for the full bill of materials.


## License

MIT
