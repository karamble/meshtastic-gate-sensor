# PCB Design Documentation


## Board Specifications

| Parameter | Value |
|-----------|-------|
| Dimensions | 75 x 66 mm |
| Layers | 2 (F.Cu + B.Cu) |
| Material | FR-4 |
| Thickness | 1.6 mm |
| Surface finish | HASL (lead-free) |
| Min trace width | 0.25 mm (signal), 0.50 mm (power) |
| Min drill | 0.8 mm |
| Via size | 1.4 mm pad / 0.8 mm drill |
| Text minimum | 0.8 mm height, 0.15 mm stroke |
| Format | KiCad 10 (S-expression, version 20221018) |
| DRC status | 0 violations, 0 unconnected nets |

## Generation

The PCB file `pcb/gate_sensor_v2.kicad_pcb` is generated programmatically by `pcb/gate_sensor_pcb_v2.py`. This Python script writes KiCad S-expressions directly with no dependency on pcbnew or SWIG. It is compatible with KiCad 7-10.

To regenerate:
```bash
cd pcb && python3 gate_sensor_pcb_v2.py
```

## Board Outline

75x66mm rectangle with a USB-C notch at the top edge (X=10 to X=29, 8mm deep) for the Heltec's USB connector. Four M3 mounting holes at the corners (4mm inset).

```
         10    29
    ┌─────┘    └──────────────────────────┐
    │     USB-C notch                     │
    │                                     │  75mm
    │  U3 Heltec    U2 RXB6   U1 Nano    │
    │                                     │
    │  C2   J4-sw              J2-PWR    │
    └─────────────────────────────────────┘
                     75mm
```

## Component Placement

### Modules (top half of board)

| Ref | Component | Position | Footprint | Notes |
|-----|-----------|----------|-----------|-------|
| U3 | Heltec LoRa32 V3 | Left side, X=7-30, Y=10-53 | 2x18 pin socket, 22.86mm row spacing | Socketed, removable |
| U1 | Arduino Nano | Right side, X=55-70, Y=12-48 | 2x15 pin socket, 15.24mm row spacing | Socketed, removable |
| U2 | RXB6 433MHz | Center, X=44, Y=12-53 | 8-pin SIP, direct solder | Not removable |

### Passive Components (between modules)

| Ref | Component | Position | Notes |
|-----|-----------|----------|-------|
| R1 | 2.2k (logic divider series) | X=34-39, Y=24.7 | Horizontal, between RXB6 and Nano |
| R2 | 3.3k (logic divider shunt) | X=34, Y=25.8-29.8 | Vertical, below R1 junction |
| R5 | 10k (DE pull-up) | X=37.5-42.6, Y=47.6 | Horizontal, left of RXB6 pin 6 |
| C1 | 100nF ceramic (bypass) | X=38-40.5, Y=16 | Horizontal, near RXB6 VDD |
| C2 | 100uF electrolytic (bulk) | X=20, Y=59-61 | Vertical, below V5/GND buses |

### Connectors (bottom of board, Y=68)

| Ref | Component | Position | Notes |
|-----|-----------|----------|-------|
| J2 | PWR IN (screw terminal) | X=8, Y=68 | 5V + GND from Waveshare |
| J4 | PWR switch (JST-PH 2mm) | X=26, Y=68 | Toggle switch inline with 5V |

## Routing Strategy

### F.Cu (Front Copper) — Primary Layer

Used for all signal traces and most power traces:

- **Signal traces** (0.25mm): D3 to R1, HELTEC_RX from R1/R2 junction to GPIO47, DE from R5 to RXB6
- **Power traces** (0.50mm): V5 bus (horizontal, Y=56), GND bus (horizontal, Y=58, 0.60mm wide), V5_IN from J2 to J4, 5V drops to modules
- **3V3**: Short bridge between Heltec R2 and R3 only

### B.Cu (Back Copper) — Secondary Layer

Used for GND drops and traces that must cross F.Cu signals:

- **GND drops**: Vertical traces from pad-level vias down to the GND bus. Offset 2+ mm from pad columns to avoid shorting to through-hole pad copper.
- **V5 feed from J4**: Via at X=34, B.Cu vertical to V5 bus (crosses GND bus underneath)
- **V5 to Nano**: B.Cu vertical at X=76.78 (avoids crossing R14 GND stub)
- **V5 to RXB6**: B.Cu vertical at X=50 (between GND drops)
- **D2/RF signal**: B.Cu from X=48 (avoids crossing D3 trace)

### GND Drop Strategy

Through-hole pads have copper on both layers. B.Cu GND drops are offset from pad columns to clear the 1.8mm pad diameter:

| Drop | Pad X | Offset X | Direction |
|------|-------|----------|-----------|
| Heltec L1 | 7.0 | 4.5 | Left |
| Heltec R1 | 29.86 | 32.5 | Right |
| Nano L4 | 55.0 | 52.5 | Left |
| Nano R14 | 72.78 | 79.0 | Right |
| R2 GND | 33.92 | 36.0 | Right |
| RXB6 pin 8 | 44.0 | 41.5 | Left |
| RXB6 pins 2-3 | 44.0 | 46.5 | Right |

### Copper Pour

GND fill zones on both F.Cu and B.Cu, following the board outline (including USB-C notch). Settings:
- Clearance: 0.30mm
- Min thickness: 0.25mm
- Thermal relief gap: 0.508mm
- Thermal bridge width: 0.508mm

## Bus Layout

```
  Y=8.7   ──── 3V3 bus (Heltec R2-R3 bridge only, not distributed) ────
  
  Y=56.0  ════ V5 power bus (F.Cu, 0.50mm) ════════════════════════════
  Y=58.0  ════ GND bus (F.Cu, 0.60mm) ═════════════════════════════════
```

The V5 and GND buses span from X=3 (left of Heltec) to X=85 (right of Nano), with vertical drops/feeds to all modules and connectors.

## Manufacturing

### JLCPCB Settings

| Parameter | Value |
|-----------|-------|
| Layers | 2 |
| PCB Thickness | 1.6mm |
| Surface Finish | HASL (lead-free) |
| Copper Weight | 1 oz |
| Min Track/Space | 0.25mm / 0.30mm |
| Min Drill | 0.8mm |
| Board Outline | Edge.Cuts layer |
| Quantity | 5 (minimum order) |

### Gerber Export

```bash
make fab     # generates Gerbers + drill files in pcb/output/
```

This runs `make gerbers` and `make drill` via the KiCad 10 Docker image (`kicad/kicad:10.0`). Output files are placed in `pcb/output/` ready for upload to JLCPCB.

### Other Make Targets

```bash
make drc          # design rule check -> pcb/output/drc_report.json
make svg          # board SVG -> pcb/output/board.svg
make pdf          # board PDF -> pcb/output/board.pdf
make pcb-stats    # board statistics
make pcb-upgrade  # upgrade to KiCad 10 format
```

## Silkscreen

- Component outlines and reference designators on F.SilkS
- Pin labels for all module pins (moved to F.Fab where they overlap copper)
- Title block: "GATE SENSOR CARRIER v2.3 / 75x66mm 2L 1.6mm HASL"
- Connector polarity markings (+5V, GND)
- Switch symbol on J4
- Verbose circuit notes on F.Fab (not visible on assembled board)

## Version History

- **v2.0**: Initial 2-layer design
- **v2.2**: DRC fixes — removed VIN/5V short, B.Cu GND drops with offset vias, B.Cu D4 routing to fix D4/GND short, 3V3 bus rerouted, text minimums enforced, 22 vias for proper 2-layer routing
