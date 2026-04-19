#!/usr/bin/env python3
"""
Post-processor: adds 3D model references to gate_sensor_v2.kicad_pcb
Outputs gate_sensor_v2_assembly.kicad_pcb for 3D viewing in KiCad.

Usage:
  python3 generate_assembly.py          # generates assembly PCB
  make assembly                         # generates + exports STEP via AppImage
"""

import os, re, sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT  = os.path.join(SCRIPT_DIR, "gate_sensor_v2.kicad_pcb")
OUTPUT = os.path.join(SCRIPT_DIR, "gate_sensor_v2_assembly.kicad_pcb")

# KiCad 3D model base path variable (KiCad 10 resolves KICAD8 vars)
M = "${KICAD8_3DMODEL_DIR}"

# ── 3D model definitions per footprint reference ────────────────────
# Each entry: list of (model_path, offset_xyz, rotation_xyz)
# Offsets are relative to footprint center, in mm.
# Calculated from pad positions in gate_sensor_pcb_v2.py.

P = 2.54  # pin pitch

# Footprint centers (from generator):
# U3: cx=18.43, cy=31.59   U1: cx=62.62, cy=29.78   U2: cx=49.0, cy=32.32
#
# NOTE: KiCad 3D model offset Y is INVERTED from PCB Y.
# PCB Y increases downward, but model offset Y increases upward (3D convention).
# So: model_offset_y = -local_pcb_y

MODELS = {
    # ── U3: Heltec LoRa32 V3 — 2x pin socket 1x18 ──
    "U3": [
        # Left row socket: pin L1 at PCB local (-11.43, -21.59) → offset Y = +21.59
        (f"{M}/Connector_PinSocket_2.54mm.3dshapes/PinSocket_1x18_P2.54mm_Vertical.step",
         (-11.43, 21.59, 0), (0, 0, 0)),
        # Right row socket: pin R1 at PCB local (11.43, -21.59) → offset Y = +21.59
        (f"{M}/Connector_PinSocket_2.54mm.3dshapes/PinSocket_1x18_P2.54mm_Vertical.step",
         (11.43, 21.59, 0), (0, 0, 0)),
    ],

    # ── U1: Arduino Nano — 2x pin socket 1x15 ──
    "U1": [
        # Left row socket: pin L1 at PCB local (-7.62, -17.78) → offset Y = +17.78
        (f"{M}/Connector_PinSocket_2.54mm.3dshapes/PinSocket_1x15_P2.54mm_Vertical.step",
         (-7.62, 17.78, 0), (0, 0, 0)),
        # Right row socket: pin R1 at PCB local (7.62, -17.78) → offset Y = +17.78
        (f"{M}/Connector_PinSocket_2.54mm.3dshapes/PinSocket_1x15_P2.54mm_Vertical.step",
         (7.62, 17.78, 0), (0, 0, 0)),
    ],

    # ── U2: RXB6 433MHz — 2x pin socket 1x04 (female socket) ──
    "U2": [
        # Group 1 (pins 1-4): pin1 at PCB local (-5.0, -20.32) → offset Y = +20.32
        (f"{M}/Connector_PinSocket_2.54mm.3dshapes/PinSocket_1x04_P2.54mm_Vertical.step",
         (-5.0, 20.32, 0), (0, 0, 0)),
        # Group 2 (pins 5-8): pin5 at PCB local (-5.0, 12.70) → offset Y = -12.70
        (f"{M}/Connector_PinSocket_2.54mm.3dshapes/PinSocket_1x04_P2.54mm_Vertical.step",
         (-5.0, -12.70, 0), (0, 0, 0)),
    ],

    # ── Resistors (axial THT, 5.08mm pitch) ──
    # R1 (2.2k): horizontal, pad1(+X)=D3, pad2(-X)=HLTC_RX
    "R1": [
        (f"{M}/Resistor_THT.3dshapes/R_Axial_DIN0204_L3.6mm_D1.6mm_P5.08mm_Horizontal.step",
         (2.54, 0, 0), (0, 0, 180)),
    ],
    # R2 (3.3k): vertical (along PCB Y), use horizontal model + 90° Z rotation
    "R2": [
        (f"{M}/Resistor_THT.3dshapes/R_Axial_DIN0204_L3.6mm_D1.6mm_P5.08mm_Horizontal.step",
         (0, 1.99, 0), (0, 0, 90)),
    ],
    # R5 (10k): horizontal, pad1(-X)=V5, pad2(+X)=DE
    "R5": [
        (f"{M}/Resistor_THT.3dshapes/R_Axial_DIN0204_L3.6mm_D1.6mm_P5.08mm_Horizontal.step",
         (-2.54, 0, 0), (0, 0, 0)),
    ],
    # R6 (4.7k): horizontal, pad1(-X)=HELTEC_TX, pad2(+X)=D4
    "R6": [
        (f"{M}/Resistor_THT.3dshapes/R_Axial_DIN0204_L3.6mm_D1.6mm_P5.08mm_Horizontal.step",
         (-2.54, 0, 0), (0, 0, 0)),
    ],

    # ── Capacitors ──
    # C1 (100nF): ceramic disc, 2.54mm pitch
    "C1": [
        (f"{M}/Capacitor_THT.3dshapes/C_Disc_D3.0mm_W1.6mm_P2.50mm.step",
         (-1.27, 0, 0), (0, 0, 0)),
    ],
    # C2 (100uF): electrolytic radial, center at (20, 60), pads along Y → rotate -90°
    # Offset Y decreased to shift model down toward pads
    "C2": [
        (f"{M}/Capacitor_THT.3dshapes/CP_Radial_D5.0mm_P2.00mm.step",
         (0, 0, 0), (0, 0, -90)),
    ],

    # ── Connectors ──
    # J2 (SOLAR IN): screw terminal 5.08mm pitch, center at (14.54, 62.0)
    # pad1 at local (-2.54, 0)
    "J2": [
        (f"{M}/TerminalBlock_Phoenix.3dshapes/TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal.step",
         (-2.54, 0, 0), (0, 0, 0)),
    ],
    # J4 (PWR_SW): JST PH 2-pin, center at (27.0, 62.0)
    # 180° Z rotation so notch faces board edge, offset flipped to match
    "J4": [
        (f"{M}/Connector_JST.3dshapes/JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical.step",
         (1.0, 0, 0), (0, 0, 180)),
    ],
}


def model_sexpr(path, offset, rotation):
    """Generate KiCad S-expression for a 3D model entry."""
    ox, oy, oz = offset
    rx, ry, rz = rotation
    return (
        f'    (model "{path}"\n'
        f'      (offset (xyz {ox:.4f} {oy:.4f} {oz:.4f}))\n'
        f'      (scale (xyz 1 1 1))\n'
        f'      (rotate (xyz {rx:.4f} {ry:.4f} {rz:.4f}))\n'
        f'    )'
    )


def find_footprint_blocks(text):
    """Find all footprint blocks and their reference names.
    Returns list of (ref_name, start_idx, end_idx) where end_idx
    points to the closing ')' of the footprint block."""
    blocks = []
    i = 0
    while i < len(text):
        # Find '(footprint "'
        match = re.search(r'\(footprint\s+"([^"]+)"', text[i:])
        if not match:
            break
        start = i + match.start()
        ref = match.group(1)

        # Find matching closing paren
        depth = 0
        j = start
        while j < len(text):
            if text[j] == '(':
                depth += 1
            elif text[j] == ')':
                depth -= 1
                if depth == 0:
                    blocks.append((ref, start, j))
                    break
            j += 1
        i = j + 1
    return blocks


def main():
    if not os.path.exists(INPUT):
        print(f"Error: {INPUT} not found. Run gate_sensor_pcb_v2.py first.")
        sys.exit(1)

    with open(INPUT, 'r') as f:
        text = f.read()

    # Process footprints in reverse order so indices stay valid
    blocks = find_footprint_blocks(text)
    blocks.reverse()

    added = 0
    for ref, start, end in blocks:
        if ref in MODELS:
            model_entries = "\n".join(
                model_sexpr(path, offset, rot)
                for path, offset, rot in MODELS[ref]
            )
            # Insert model entries before the closing ')' of the footprint
            text = text[:end] + "\n" + model_entries + "\n  " + text[end:]
            added += len(MODELS[ref])

    # Also skip MH (mount holes) — no model needed

    with open(OUTPUT, 'w') as f:
        f.write(text)

    print(f"""
Assembly PCB generated — {added} 3D models added
Output: {OUTPUT}

Components with 3D models:
  U3  Heltec LoRa32 V3   → 2x PinSocket 1x18
  U1  Arduino Nano        → 2x PinSocket 1x15
  U2  RXB6 433MHz         → 2x PinSocket 1x04
  R1  2.2k (level shift)  → Axial resistor
  R2  3.3k (level shift)  → Axial resistor (vertical)
  R5  10k (DE pullup)     → Axial resistor
  R6  4.7k (GPIO48 series)→ Axial resistor
  C1  100nF (bypass)      → Ceramic disc cap
  C2  100uF (bulk)        → Electrolytic radial cap
  J2  SOLAR IN            → Screw terminal 5.08mm
  J4  PWR SW              → JST PH 1x02

To view in 3D:
  1. Open {os.path.basename(OUTPUT)} in KiCad PCB Editor
  2. Press Alt+3 (or View → 3D Viewer)

To export STEP:
  make assembly-step
""")


if __name__ == "__main__":
    main()
