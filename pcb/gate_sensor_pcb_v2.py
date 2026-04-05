#!/usr/bin/env python3
"""
Gate Sensor Carrier PCB v2.2 — KiCad S-expression generator
Writes gate_sensor_v2.kicad_pcb directly — NO pcbnew / SWIG dependency.
Compatible with KiCad 7–10.  Runs inside or outside KiCad.

v2.2 changes (compact layout):
  - Board shrunk from 90x75mm to 75x66mm
  - R3/R4 moved from right of Nano to below Nano (X≈60, Y≈50)
  - Connectors J2/J3/J4 moved up to Y=62
  - V5/GND buses moved up (Y=55/57)
  - All routing updated for new positions
  - Mounting holes repositioned for smaller board

v2.1 changes (from expert DRC review):
  - Fixed VIN/5V short (removed V5 from Nano VIN pin)
  - GND drops routed on B.Cu via vias (eliminates track crossings)
  - D2 signal routed via B.Cu (fixes D2/GND short at RXB6)
  - 3V3 bus rerouted above components (fixes 3V3/pad shorts)
  - V5 feed uses B.Cu to cross GND bus
  - All text >= 0.8mm height, 0.15mm stroke (JLCPCB minimum)
  - Verbose notes moved to F.Fab layer
  - Added B.Mask and B.SilkS layers
  - 22 vias for proper 2-layer routing
"""

import os

def _build():
    P = 2.54  # standard pin pitch (mm)

    # ── Formatting ──────────────────────────────────────
    def f(v): return "{:.4f}".format(float(v))

    # ── Net registry ────────────────────────────────────
    _nets = {"": 0}; _nid = [0]
    def N(name):
        if name not in _nets: _nid[0] += 1; _nets[name] = _nid[0]
        return name
    GND = N("GND"); V5 = N("5V"); V5_IN = N("5V_IN"); V33 = N("3V3")
    D3_NET = N("D3"); D2_NET = N("D2")
    HLTC_RX = N("HELTEC_RX"); DE_NET = N("DE")

    _body = []
    def emit(s): _body.append(s)

    # ── Drawing primitives ──────────────────────────────
    MIN_TEXT = 0.8
    STROKE_W = 0.15

    def gr_line(x1, y1, x2, y2, layer="Edge.Cuts", w=0.05):
        emit(f'  (gr_line (start {f(x1)} {f(y1)}) (end {f(x2)} {f(y2)}) (layer "{layer}") (width {f(w)}))')

    def gr_circle(cx, cy, r, layer="F.CrtYd", w=0.05):
        emit(f'  (gr_circle (center {f(cx)} {f(cy)}) (end {f(cx+r)} {f(cy)}) (layer "{layer}") (width {f(w)}))')

    def gr_text(text, x, y, layer="F.SilkS", size=0.8, angle=0):
        sz = max(size, MIN_TEXT)
        ang = f' {f(angle)}' if angle else ""
        emit(f'  (gr_text "{text}" (at {f(x)} {f(y)}{ang}) (layer "{layer}")\n'
             f'    (effects (font (size {f(sz)} {f(sz)}) (thickness {f(STROKE_W)}))))')

    def silk(x1, y1, x2, y2, w=0.15):
        gr_line(x1, y1, x2, y2, "F.SilkS", w)

    def fab(x1, y1, x2, y2, w=0.10):
        gr_line(x1, y1, x2, y2, "F.Fab", w)

    def silk_box(x1, y1, x2, y2, w=0.15):
        for a, b in [((x1,y1),(x2,y1)), ((x2,y1),(x2,y2)),
                      ((x2,y2),(x1,y2)), ((x1,y2),(x1,y1))]:
            silk(a[0], a[1], b[0], b[1], w)

    def fab_box(x1, y1, x2, y2, w=0.10):
        for a, b in [((x1,y1),(x2,y1)), ((x2,y1),(x2,y2)),
                      ((x2,y2),(x1,y2)), ((x1,y2),(x1,y1))]:
            fab(a[0], a[1], b[0], b[1], w)

    def txt(text, x, y, size=0.8, layer="F.SilkS", angle=0):
        gr_text(text, x, y, layer, size, angle)

    def trk(x1, y1, x2, y2, net, layer="F.Cu", w=0.25):
        nid = _nets.get(net, 0)
        emit(f'  (segment (start {f(x1)} {f(y1)}) (end {f(x2)} {f(y2)})'
             f' (width {f(w)}) (layer "{layer}") (net {nid}))')

    def via_hole(x, y, net, drill=0.8, size=1.4):
        nid = _nets.get(net, 0)
        emit(f'  (via (at {f(x)} {f(y)}) (size {f(size)}) (drill {f(drill)})'
             f' (layers "F.Cu" "B.Cu") (net {nid}))')

    # ── Footprint class ─────────────────────────────────
    class FP_:
        def __init__(s, ref, val, cx, cy):
            s.ref = ref; s.val = val; s.cx = cx; s.cy = cy; s._p = []
        def pad(s, num, ax, ay, drill, size, net=None, square=False):
            rx, ry = ax - s.cx, ay - s.cy
            shape = "rect" if square else "circle"
            nid = _nets.get(net, 0) if net else 0
            ns = f' (net {nid} "{net}")' if net else ""
            s._p.append(f'    (pad "{num}" thru_hole {shape} (at {f(rx)} {f(ry)})'
                        f' (size {f(size)} {f(size)}) (drill {f(drill)})'
                        f' (layers "*.Cu" "*.Mask"){ns})')
        def npth(s, ax, ay, d):
            rx, ry = ax - s.cx, ay - s.cy
            s._p.append(f'    (pad "" np_thru_hole circle (at {f(rx)} {f(ry)})'
                        f' (size {f(d)} {f(d)}) (drill {f(d)}) (layers "*.Cu" "*.Mask"))')
        def emit_fp(s):
            ps = "\n".join(s._p)
            emit(f'  (footprint "{s.ref}" (layer "F.Cu")\n'
                 f'    (at {f(s.cx)} {f(s.cy)})\n'
                 f'    (fp_text reference "{s.ref}" (at 0 -4) (layer "F.Fab")\n'
                 f'      (effects (font (size {f(MIN_TEXT)} {f(MIN_TEXT)})'
                 f' (thickness {f(STROKE_W)}))))\n'
                 f'    (fp_text value "{s.val}" (at 0 4) (layer "F.Fab")\n'
                 f'      (effects (font (size {f(MIN_TEXT)} {f(MIN_TEXT)})'
                 f' (thickness {f(STROKE_W)}))))\n'
                 + (ps + "\n" if ps else "") + "  )")

    _fps = []
    def new_fp(ref, val, cx, cy):
        fp_ = FP_(ref, val, cx, cy); _fps.append(fp_); return fp_

    def np_hole(x, y, d=3.2):
        fp_ = new_fp("MH", "M3_MountHole", x, y)
        fp_.npth(x, y, d)
        gr_circle(x, y, 3.6, "F.CrtYd", 0.05)

    # ══════════════════════════════════════════════════════
    #  BOARD OUTLINE  (75 x 66 mm with USB-C notch)
    # ══════════════════════════════════════════════════════
    BW, BH = 75.0, 66.0
    NX1, NX2, NH = 10.0, 29.0, 8.0

    outline = [(0,0),(NX1,0),(NX1,NH),(NX2,NH),(NX2,0),
               (BW,0),(BW,BH),(0,BH),(0,0)]
    for i in range(len(outline) - 1):
        a, b = outline[i], outline[i+1]
        gr_line(a[0], a[1], b[0], b[1], "Edge.Cuts", 0.05)

    for mx, my in [(3.5,3.5),(71.5,3.5),(3.5,62.5),(71.5,62.5)]:
        np_hole(mx, my, 3.2)

    txt("USB-C", (NX1+NX2)/2 - 3, NH + 2.0)

    # ══════════════════════════════════════════════════════
    #  U3 — HELTEC LoRa32 V3  (2×18 pins, per actual board photo)
    # ══════════════════════════════════════════════════════
    HLTC_XL = 7.0; HLTC_XR = HLTC_XL + 22.86; HLTC_Y0 = 10.0

    # Left row: 18 pins, top (USB end) to bottom (antenna end)
    # GPIO47 (L13) used for Meshtastic serial RX — avoids GPIO44/CP2102 conflict
    HL_NETS = [GND, V5, None, None, None, None, None, None,
               None, None, None, None, HLTC_RX, None, None, None, None, None]
    HL_LBLS = ["GND","5V","Ve","Ve","44","TX43","RST","C",
               "36","35","34","33","47/RX","48","26","21","20","19"]
    # Right row: 18 pins
    HR_NETS = [GND, V33, V33] + [None]*15
    HR_LBLS = ["GND","3V3","3V3","37","46","45","42","41",
               "40","39","38","1","2","3","4","5","6","7"]

    u3 = new_fp("U3", "Heltec_LoRa32_V3",
                (HLTC_XL+HLTC_XR)/2, HLTC_Y0 + 8.5*P)
    for i, n in enumerate(HL_NETS):
        u3.pad(f"L{i+1}", HLTC_XL, HLTC_Y0 + i*P, 0.8, 1.8, n, i == 0)
    for i, n in enumerate(HR_NETS):
        u3.pad(f"R{i+1}", HLTC_XR, HLTC_Y0 + i*P, 0.8, 1.8, n, i == 0)

    hx1, hx2 = HLTC_XL - 1.8, HLTC_XR + 1.8
    hy1, hy2 = HLTC_Y0 - 1.5, HLTC_Y0 + 17*P + 1.0  # 18 pins = 17 gaps + margin
    silk_box(hx1, hy1, hx2, hy2)
    fab_box(hx1 - .5, hy1 - .5, hx2 + .5, hy2 + .5)
    # Pin 1 marker
    silk(HLTC_XL - 1.8, HLTC_Y0 - 1.5, HLTC_XL + 0.2, HLTC_Y0 - 1.5)
    silk(HLTC_XL - 1.8, HLTC_Y0 - 1.5, HLTC_XL - 1.8, HLTC_Y0 + 0.5)

    txt("U3  HELTEC LoRa32 V3", 16, hy1 - 2.5, layer="F.Fab")
    # Name inside frame — vertical (90° CCW)
    txt("HELTEC LoRa32 V3", (HLTC_XL+HLTC_XR)/2 - 1, (hy1+hy2)/2 + 3, angle=90)
    txt("SOCKET", (HLTC_XL+HLTC_XR)/2 + 1.5, (hy1+hy2)/2 - 1, angle=90)

    for i, lb in enumerate(HL_LBLS):
        txt(lb, HLTC_XL - 5.0, HLTC_Y0 + i*P - 0.33)
    # R-column labels — all on F.SilkS (R1/R2 moved right, clears pins 40-42)
    for i, lb in enumerate(HR_LBLS):
        txt(lb, HLTC_XR + 3.5, HLTC_Y0 + i*P - 0.33)

    # ══════════════════════════════════════════════════════
    #  U1 — ARDUINO NANO  (2 x 15 pins)
    # ══════════════════════════════════════════════════════
    NANO_XL = 55.0; NANO_XR = NANO_XL + 15.24; NANO_Y0 = 12.0  # 15.24mm = 600mil standard

    # LEFT side — analog/power (D13 at USB end, VIN at bottom)
    # FIX v2.1: L15 (VIN) set to None — VIN has onboard regulator,
    # shorting VIN to 5V feeds regulator output back to input.
    # L2 (3V3) left unconnected — Nano has its own 3.3V regulator,
    # connecting Heltec 3V3 would cause regulator contention.
    NL_NETS = [None, None, None, None, None, None, None,
               None, None, None, None, V5, None, GND, None]
    NL_LBLS = ["D13","3V3","REF","A0","A1","A2","A3",
               "A4","A5","A6","A7","5V","RST","GND","VIN"]
    # RIGHT side — digital (D12 at USB end, D1/TX at bottom)
    # D2 (R11) = RXB6 DATA (INT0 for RCSwitch), D3 (R10) = SoftwareSerial TX
    NR_NETS = [None, None, None, None, None, None, None,
               None, None, D3_NET, D2_NET, GND, None, None, None]
    NR_LBLS = ["D12","D11","D10","D9","D8","D7","D6",
               "D5","D4","D3","D2","GND","RST","D1","D0"]

    u1 = new_fp("U1", "Arduino_Nano_Socket",
                (NANO_XL+NANO_XR)/2, NANO_Y0 + 7*P)
    for i, n in enumerate(NL_NETS):
        u1.pad(f"L{i+1}", NANO_XL, NANO_Y0 + i*P, 0.8, 1.8, n, i == 0)
    for i, n in enumerate(NR_NETS):
        u1.pad(f"R{i+1}", NANO_XR, NANO_Y0 + i*P, 0.8, 1.8, n, i == 0)

    nx1, nx2 = NANO_XL - 1.8, NANO_XR + 1.5
    ny1, ny2 = NANO_Y0 - 1.5, NANO_Y0 + 14*P + 1.5  # 15 pins = 14 gaps + margin
    fab_box(nx1, ny1, nx2, ny2)  # full outline on F.Fab
    # Silk box with shortened right edge to avoid GND label overlap
    silk_box(nx1, ny1, NANO_XR + 1.0, ny2)
    fab_box(nx1 - .5, ny1 - .5, nx2 + .5, ny2 + .5)
    silk(NANO_XL - 1.8, NANO_Y0 - 1.5, NANO_XL + 0.2, NANO_Y0 - 1.5)
    silk(NANO_XL - 1.8, NANO_Y0 - 1.5, NANO_XL - 1.8, NANO_Y0 + 0.5)

    txt("U1  ARDUINO NANO", NANO_XL, ny1 - 2.5, layer="F.Fab")
    # Name inside frame — vertical (90° CCW)
    txt("ARDUINO NANO", (NANO_XL+NANO_XR)/2 - 1, (ny1+ny2)/2 + 1, angle=90)
    txt("SOCKET", (NANO_XL+NANO_XR)/2 + 1.5, (ny1+ny2)/2 - 1, angle=90)
    # USB label at top of Nano frame (matching Heltec)
    txt("USB", (NANO_XL+NANO_XR)/2, ny1 + 2.0)

    for i, lb in enumerate(NL_LBLS):
        txt(lb, NANO_XL - 3.5, NANO_Y0 + i*P - 0.33)
    for i, lb in enumerate(NR_LBLS):
        txt(lb, NANO_XR + 3.0, NANO_Y0 + i*P - 0.33)

    # ══════════════════════════════════════════════════════
    #  U2 — RXB6 433 MHz Receiver  (8 pins SIP, direct solder, VERTICAL)
    #  2 groups of 4 pins, 2.54mm pitch within group, 25.4mm between groups.
    #  Group 1 (pins 1-4): ANT GND GND VDD    (top)
    #  Group 2 (pins 5-8): VDD DE  DATA GND   (bottom)
    #  Total span: 40.64mm vertical. Module body extends to the right.
    #  DATA (pin 7) → D2_NET.  DE (pin 6) unconnected.
    # ══════════════════════════════════════════════════════
    RXB6_GRP_GAP = 25.4   # gap between pin groups
    RXB6_X  = 44.0        # pin column X (between Heltec R=29.86 and Nano L=55)
    RXB6_Y0 = 12.0        # pin 1 (ANT) Y — top of board

    # Pin Y positions: group1 top-to-bottom, then gap, group2
    RXB6_PIN_Y = [RXB6_Y0 + i*P for i in range(4)] + \
                 [RXB6_Y0 + 3*P + RXB6_GRP_GAP + i*P for i in range(4)]
    # pin1=12.0  pin4=19.62  pin5=45.02  pin8=52.64

    RXB6_NETS = [None, GND, GND, V5, V5, DE_NET, D2_NET, GND]
    RXB6_LBLS = ["ANT","GND","GND","5V","5V","DE","DATA","GND"]

    u2 = new_fp("U2", "RXB6_433MHz_DirectSolder",
                RXB6_X + 5.0, (RXB6_PIN_Y[0] + RXB6_PIN_Y[7]) / 2)
    for i, n in enumerate(RXB6_NETS):
        u2.pad(str(i+1), RXB6_X, RXB6_PIN_Y[i], 0.9, 1.8, n, i == 0)

    # Module body (~10×43mm, extends to the right of pin column)
    rxb_x1 = RXB6_X - 2.0; rxb_x2 = RXB6_X + 2.0  # slim frame, 4mm wide
    rxb_y1 = RXB6_PIN_Y[0] - 1.5; rxb_y2 = RXB6_PIN_Y[7] + 1.5
    silk_box(rxb_x1, rxb_y1, rxb_x2, rxb_y2)
    txt("U2 RXB6 433MHz", rxb_x1 + 1, rxb_y1 - 1.5, layer="F.Fab")
    # Name inside frame — vertical (90° CCW)
    txt("RXB6 433MHz", RXB6_X, (rxb_y1+rxb_y2)/2, angle=90)
    txt("DIRECT SOLDER", rxb_x1, rxb_y2 + 1.5, layer="F.Fab")
    # Pin labels — move pins near R5/C1 area to F.Fab to avoid silk-over-copper
    for i, lb in enumerate(RXB6_LBLS):
        pin_y = RXB6_PIN_Y[i]
        if 14.0 < pin_y < 18.0 or 45.0 < pin_y < 50.0:
            txt(lb, RXB6_X - 5.0, pin_y - 0.33, layer="F.Fab")
        else:
            txt(lb, RXB6_X - 5.0, pin_y - 0.33)

    # ══════════════════════════════════════════════════════
    #  R1–R4  Resistors
    # ══════════════════════════════════════════════════════
    R1_DIV_Y = 24.70         # voltage divider Y (kept for clean GPIO47 routing)

    # R1 (2.2 k) — series, logic level divider
    # Shifted right 2mm from v2.2 to clear Heltec R-column silk labels (pins 40-42)
    R1_X1, R1_X2, R1_Y = 41.0, 41.0 - 5.08, R1_DIV_Y
    r1 = new_fp("R1", "2.2k", (R1_X1+R1_X2)/2, R1_Y)
    r1.pad("1", R1_X1, R1_Y, 0.8, 1.6, D3_NET, True)
    r1.pad("2", R1_X2, R1_Y, 0.8, 1.6, HLTC_RX)
    fab_box(R1_X2 - 1.2, R1_Y - 1.4, R1_X1 + 1.2, R1_Y + 1.4)
    txt("R1 2k2", (R1_X1+R1_X2)/2, R1_Y - 3.0)

    # R2 (3.3 k) — shunt, logic level divider
    # Pad 1 offset 1.1mm down from R1 pad2 to clear hole-to-hole minimum
    R2_X, R2_Y1, R2_Y2 = R1_X2, R1_Y + 1.1, R1_Y + 5.08
    r2 = new_fp("R2", "3.3k", R2_X, (R2_Y1+R2_Y2)/2)
    r2.pad("1", R2_X, R2_Y1, 0.8, 1.6, HLTC_RX, True)
    r2.pad("2", R2_X, R2_Y2, 0.8, 1.6, GND)
    fab_box(R2_X - 1.4, R2_Y1 - 1.0, R2_X + 1.4, R2_Y2 + 1.0)
    txt("R2 3k3", R2_X + 2.0, (R2_Y1+R2_Y2)/2 - 0.33)

    # ══════════════════════════════════════════════════════
    #  R5, C1, C2  Hardening components
    # ══════════════════════════════════════════════════════

    # R5 (10k) — DE pull-up: RXB6 pin 6 (DE) to 5V
    # Placed left of RXB6 pin column, horizontal, bridging DE to V5
    R5_X1, R5_X2, R5_Y = 34.5, 34.5 + 5.08, RXB6_PIN_Y[5]  # pin 6 Y = 47.56
    # R5 pad2 at X=39.58, pin 6 at X=44 — pad edges 2.52mm apart, clean gap
    r5 = new_fp("R5", "10k_PU", (R5_X1+R5_X2)/2, R5_Y)
    r5.pad("1", R5_X1, R5_Y, 0.8, 1.6, V5, True)
    r5.pad("2", R5_X2, R5_Y, 0.8, 1.6, DE_NET)
    fab_box(R5_X1 - 1.2, R5_Y - 1.4, R5_X2 + 1.2, R5_Y + 1.4)
    txt("R5 10k", R5_X1, R5_Y + 2.5, layer="F.Fab")
    txt("DE pullup", R5_X1, R5_Y + 2.5, layer="F.Fab")

    # C1 (100nF) — bypass cap near RXB6 VDD (pin 4)
    # Placed left of RXB6, vertical, between V5 and GND
    # C1 placed horizontally to avoid V5/GND trace crossing
    C1_X1 = 38.0; C1_X2 = C1_X1 + 2.54; C1_Y = 16.0
    c1 = new_fp("C1", "100nF", (C1_X1+C1_X2)/2, C1_Y)
    c1.pad("1", C1_X1, C1_Y, 0.8, 1.6, V5, True)
    c1.pad("2", C1_X2, C1_Y, 0.8, 1.6, GND)
    fab_box(C1_X1 - 1.0, C1_Y - 1.4, C1_X2 + 1.0, C1_Y + 1.4)
    txt("C1 100nF", C1_X1, C1_Y - 3.0)

    # C2 (100µF) — bulk electrolytic, between J2 and J4 (spaced to clear screw terminal body)
    C2_X = 25.0; C2_Y1 = 59.0; C2_Y2 = 61.0
    c2 = new_fp("C2", "100uF", C2_X, (C2_Y1+C2_Y2)/2)
    c2.pad("1", C2_X, C2_Y1, 0.8, 1.6, V5, True)  # + (positive)
    c2.pad("2", C2_X, C2_Y2, 0.8, 1.6, GND)         # - (negative)
    fab_box(C2_X - 2.8, C2_Y1 - 1.2, C2_X + 2.8, C2_Y2 + 1.2)  # 5mm cap body
    txt("C2 100uF", C2_X, C2_Y2 + 2.0)
    txt("+", C2_X - 1.5, C2_Y1 - 0.33, layer="F.Fab")

    # ══════════════════════════════════════════════════════
    #  J2, J3  Screw terminals (5.08mm pitch, Waveshare Solar Power Manager D)
    #  J4     JST PH 2-pin (2mm pitch, power switch)
    # ══════════════════════════════════════════════════════
    J2_X0, J2_Y = 12.0, 62.0
    j2 = new_fp("J2", "PWR_IN_ScrewTerm", J2_X0 + 2.54, J2_Y)
    j2.pad("1", J2_X0, J2_Y, 1.2, 2.4, V5_IN, True)
    j2.pad("2", J2_X0 + 5.08, J2_Y, 1.2, 2.4, GND)
    silk_box(J2_X0 - 2.5, J2_Y - 3.0, J2_X0 + 7.5, J2_Y + 2.5)
    txt("5V IN", J2_X0 + 2.54, J2_Y - 4.0)
    txt("+5V", J2_X0 - 0.5, J2_Y + 3.5)
    txt("GND", J2_X0 + 4.0, J2_Y + 3.5)

    J4_X0, J4_Y = 34.0, 62.0
    j4 = new_fp("J4", "PWR_SW_JST_PH_2pin", J4_X0 + 1.0, J4_Y)
    j4.pad("1", J4_X0, J4_Y, 0.8, 1.6, V5_IN, True)
    j4.pad("2", J4_X0 + 2.0, J4_Y, 0.8, 1.6, V5)
    # No silk_box — pads too close for right edge to pass between without mask clipping
    # Switch symbol
    silk(J4_X0 - .5, J4_Y - 3.8, J4_X0 + 2.5, J4_Y - 3.8)
    silk(J4_X0 - .5, J4_Y - 3.8, J4_X0 + .5, J4_Y - 4.6)
    silk(J4_X0 + 2.5, J4_Y - 3.8, J4_X0 + 1.5, J4_Y - 4.6)
    txt("PWR SW", J4_X0 + 1.0, J4_Y - 5.5)
    txt("IN  OUT", J4_X0 + 1.0, J4_Y + 3.5)

    # ══════════════════════════════════════════════════════
    #  SILKSCREEN — Title & notes
    # ══════════════════════════════════════════════════════
    txt("GATE SENSOR CARRIER v2.3", 42, 4.0, size=1.1)
    txt("75x66mm  2L  1.6mm  HASL", 42, 6.0)

    # Verbose circuit notes on F.Fab (not silk)
    note_x = (HLTC_XR + NANO_XL) / 2
    txt("LOGIC LEVEL: D3->R1(2k2)->R2(3k3)->GND, jct->GPIO47",
        note_x - 10, R1_DIV_Y - 5, layer="F.Fab")
    txt("All boards removable except U2 (RXB6 direct solder)",
        5, BH - 2.0, layer="F.Fab")

    # ── Logo (raccoon) on F.SilkS — rendered from logo-bw.png ──
    import json, os
    logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo_silk.json")
    if os.path.exists(logo_path):
        with open(logo_path) as lf:
            logo = json.load(lf)
        LOGO_DX = 6.0  # shift logo right to clear J4 pad2
        for x1, y1, x2, y2 in logo["lines"]:
            silk(x1 + LOGO_DX, y1, x2 + LOGO_DX, y2, logo["line_width"])

    # Text beside logo (0.7mm to fit without overlapping nearby labels)
    txt("GoTailMe.com", 54.0, 59.5, size=0.7)
    txt("Meshtastic Gate", 54.0, 60.7, size=0.7)
    txt("and Door Sensor", 54.0, 61.9, size=0.7)

    # ══════════════════════════════════════════════════════
    #  ROUTING
    # ══════════════════════════════════════════════════════
    S  = 0.25   # signal trace width
    PW = 0.50   # power trace width
    GW = 0.60   # GND bus width

    GND_BUS_Y = 57.0    # below last Heltec pin (17*P+10=53.18, +pad+margin)
    V5_BUS_Y  = 55.0    # just above GND bus
    V33_BUS_Y = 8.7      # above all pads, 0.575mm from notch edge at Y=8

    # Key pin Y positions (updated for 18-pin Heltec)
    HLTC_5V_Y    = HLTC_Y0 + P        # L2 = 5V = 12.54
    HLTC_RX_Y    = HLTC_Y0 + 12*P     # L13 = GPIO47 = 40.48 (serial RX)
    HLTC_GND_R1_Y = HLTC_Y0           # R1 = GND = 10.0
    NANO_3V3_Y   = NANO_Y0 + P        # L2  = 14.54 (LEFT side)
    NANO_GND_L_Y = NANO_Y0 + 13*P     # L14 = 45.02
    NANO_5V_Y    = NANO_Y0 + 11*P     # L12 = 39.94 (LEFT side)
    NANO_GND_R_Y = NANO_Y0 + 11*P     # R12 = 39.94

    # ── Offset X positions for GND drops ────────────────
    # Through-hole pads have copper on BOTH layers, so B.Cu traces
    # must be offset >=2mm from pad column X to clear 1.8mm pads.
    GND_HLTC_L_X = 4.5    # offset left of Heltec L column (7.0)
    GND_HLTC_R_X = 32.5   # offset right of Heltec R column (29.86)
    GND_NANO_L_X = 52.5   # offset left of Nano L column (55.0)
    GND_NANO_R_X = 68.0   # offset left of Nano R column (70.24), between Nano L and R
    GND_R2_X     = 38.0   # offset right of R2 pad (35.92), clear of HELTEC_RX routing

    # ── GND BUS (F.Cu, spans all connection points) ────────
    trk(GND_HLTC_L_X, GND_BUS_Y, GND_NANO_R_X, GND_BUS_Y, GND, "F.Cu", GW)

    # ── GND DROPS (offset from pad columns, B.Cu vertical) ──
    def gnd_drop_offset(pad_x, pad_y, off_x, w=PW, jog_y=None):
        """Pad → F.Cu jog to offset X → via → B.Cu vertical → via → F.Cu to bus
        If jog_y is set, route via F.Cu L-shape (pad→jog_y, then jog_y→off_x) to dodge traces."""
        if jog_y is not None:
            trk(pad_x, pad_y, pad_x, jog_y, GND, "F.Cu", w)
            trk(pad_x, jog_y, off_x, jog_y, GND, "F.Cu", w)
            via_hole(off_x, jog_y, GND)
            trk(off_x, jog_y, off_x, GND_BUS_Y, GND, "B.Cu", w)
            via_hole(off_x, GND_BUS_Y, GND)
        else:
            trk(pad_x, pad_y, off_x, pad_y, GND, "F.Cu", w)
            via_hole(off_x, pad_y, GND)
            trk(off_x, pad_y, off_x, GND_BUS_Y, GND, "B.Cu", w)
            via_hole(off_x, GND_BUS_Y, GND)

    # Heltec L1 GND (7.0, 10.0) → offset to X=4.5
    gnd_drop_offset(HLTC_XL, HLTC_Y0, GND_HLTC_L_X)
    # Heltec R1 GND (29.86, 10.0) → offset to X=32.5
    gnd_drop_offset(HLTC_XR, HLTC_Y0, GND_HLTC_R_X)
    # Nano L14 GND (55.0, 45.02) → offset to X=52.5
    gnd_drop_offset(NANO_XL, NANO_GND_L_Y, GND_NANO_L_X)
    # Nano R12 GND (70.24, 39.94) → offset to X=68.0
    gnd_drop_offset(NANO_XR, NANO_GND_R_Y, GND_NANO_R_X)

    # RXB6 GND — pin 8 drops to GND bus (offset left of pin column)
    gnd_drop_offset(RXB6_X, RXB6_PIN_Y[7], RXB6_X - 2.5, S)
    # RXB6 GND — pins 2+3 (group 1): bridge vertically, then right to B.Cu drop
    trk(RXB6_X, RXB6_PIN_Y[1], RXB6_X, RXB6_PIN_Y[2], GND, "F.Cu", S)  # pin2→pin3
    trk(RXB6_X, RXB6_PIN_Y[2], RXB6_X + 2.5, RXB6_PIN_Y[2], GND, "F.Cu", S)
    gnd_drop_offset(RXB6_X + 2.5, RXB6_PIN_Y[2], RXB6_X + 2.5, S)
    # Pins 2, 3 also GND — connected via copper pour

    # R2 shunt GND (35.92, 29.78) → offset right to X=38, B.Cu down
    gnd_drop_offset(R2_X, R2_Y2, GND_R2_X, S)

    # J2 pin2 GND (screw terminal, 5.08mm pitch) — direct F.Cu drop to GND bus
    trk(J2_X0 + 5.08, J2_Y, J2_X0 + 5.08, GND_BUS_Y, GND, "F.Cu", PW)

    # ── V5 BUS (F.Cu) ──
    # Heltec L2 (5V) at (7.0, 12.54) → jog left to X=3.0, then down to V5 bus
    trk(HLTC_XL, HLTC_5V_Y, 3.0, HLTC_5V_Y, V5, "F.Cu", PW)
    trk(3.0, HLTC_5V_Y, 3.0, V5_BUS_Y, V5, "F.Cu", PW)
    # V5 bus — straight run (ends at X=50, last tap is RXB6/Nano via at X=50)
    trk(3.0, V5_BUS_Y, 50.0, V5_BUS_Y, V5, "F.Cu", PW)

    # V5 bus feed from J4 pin2 — via at X=40 to avoid GND_R2 B.Cu at X=38
    trk(J4_X0 + 2, J4_Y, 40.0, J4_Y, V5, "F.Cu", PW)
    via_hole(40.0, J4_Y, V5)
    trk(40.0, J4_Y, 40.0, V5_BUS_Y, V5, "B.Cu", PW)
    via_hole(40.0, V5_BUS_Y, V5)
    # Note: V5 bus endpoint at X=73.0, within 75mm board

    # V5 to Nano L12 — tap from existing RXB6 V5 B.Cu column at X=50
    # B.Cu at X=50 already carries V5 from bus (Y=55) to RXB6 pin 4 (Y=19.62)
    via_hole(50.0, NANO_5V_Y, V5)
    trk(50.0, NANO_5V_Y, NANO_XL, NANO_5V_Y, V5, "F.Cu", PW)

    # ── V5_IN (J2 pin1 → J4 pin1, routed below connectors) ──
    trk(J2_X0, J2_Y, J2_X0, J2_Y + 2.5, V5_IN, "F.Cu", PW)
    trk(J2_X0, J2_Y + 2.5, J4_X0, J2_Y + 2.5, V5_IN, "F.Cu", PW)
    trk(J4_X0, J2_Y + 2.5, J4_X0, J4_Y, V5_IN, "F.Cu", PW)

    # ── 3V3 — Heltec R2+R3 are both 3V3 outputs. Bridge them.
    # No external 3V3 routing (Nano/RXB6 use their own power).
    trk(HLTC_XR, HLTC_Y0 + P, HLTC_XR, HLTC_Y0 + 2*P, V33, "F.Cu", S)

    # 5V feed to RXB6 VDD (pins 4+5) — B.Cu at X=50 (between GND drops at 46.5 and 52.5)
    via_hole(50.0, V5_BUS_Y, V5)
    trk(50.0, V5_BUS_Y, 50.0, RXB6_PIN_Y[3], V5, "B.Cu", PW)
    # Pin 5 (Y=45.02): via + F.Cu jog to pin
    via_hole(50.0, RXB6_PIN_Y[4], V5)
    trk(50.0, RXB6_PIN_Y[4], RXB6_X, RXB6_PIN_Y[4], V5, "F.Cu", PW)
    # Pin 4 (Y=19.62): via + F.Cu jog to pin
    via_hole(50.0, RXB6_PIN_Y[3], V5)
    trk(50.0, RXB6_PIN_Y[3], RXB6_X, RXB6_PIN_Y[3], V5, "F.Cu", PW)

    # ── D3 Signal (Nano R10 → R1 pad1) ──────────────────
    # D3 at (70.24, 34.86) → R1 pad1 at (41.0, 24.70)
    # All F.Cu: right to board edge, up above Nano, left, drop at X=36.5
    # (left of C1→RXB6 V5 trace at X=38-44 and GND diagonal at X=40-44)
    D3_NANO_Y = NANO_Y0 + 9*P   # 34.86
    D3_TOP_Y  = 10.0             # above first Nano pad (Y=12)
    D3_DROP_X = 36.5             # left of C1 pad (X=37.2) and V5/GND traces
    D3_JOG_Y  = 23.0             # above R1 pad zone (starts Y=23.9)
    trk(NANO_XR, D3_NANO_Y, 73.0, D3_NANO_Y, D3_NET, "F.Cu", S)
    trk(73.0, D3_NANO_Y, 73.0, D3_TOP_Y, D3_NET, "F.Cu", S)
    trk(73.0, D3_TOP_Y, D3_DROP_X, D3_TOP_Y, D3_NET, "F.Cu", S)
    trk(D3_DROP_X, D3_TOP_Y, D3_DROP_X, D3_JOG_Y, D3_NET, "F.Cu", S)
    trk(D3_DROP_X, D3_JOG_Y, R1_X1, D3_JOG_Y, D3_NET, "F.Cu", S)
    trk(R1_X1, D3_JOG_Y, R1_X1, R1_Y, D3_NET, "F.Cu", S)

    # ── D2/RF Signal (Nano D2/R11 → RXB6 DATA pin 7) ────────
    # D2 is INT0, required for RCSwitch. R11 = NANO_Y0 + 10*P = 37.40
    # All F.Cu: right to board edge, down to RXB6 DATA Y, left to pin
    D2_NANO_Y = NANO_Y0 + 10*P  # 37.40
    trk(NANO_XR, D2_NANO_Y, 73.0, D2_NANO_Y, D2_NET, "F.Cu", S)
    trk(73.0, D2_NANO_Y, 73.0, RXB6_PIN_Y[6], D2_NET, "F.Cu", S)
    trk(73.0, RXB6_PIN_Y[6], RXB6_X, RXB6_PIN_Y[6], D2_NET, "F.Cu", S)

    # ── HELTEC_RX (R1 pad2 → Heltec L5 / GPIO44 at Y=20.16) ─────
    # Route to L13 (GPIO47) at (7.0, 40.48). Go through R12/R13 gap on R column.
    # R12 pad bottom at 37.94+0.9=38.84, R13 pad top at 40.48-0.9=39.58.
    HLTC_RX_GAP_Y = (HLTC_Y0 + 11*P + 0.9 + HLTC_Y0 + 12*P - 0.9) / 2  # 39.21
    trk(R1_X2, R1_Y, 32.0, R1_Y, HLTC_RX, "F.Cu", S)       # jog left from R2 pad
    trk(32.0, R1_Y, 32.0, HLTC_RX_GAP_Y, HLTC_RX, "F.Cu", S)  # down to gap Y
    trk(32.0, HLTC_RX_GAP_Y, 5.5, HLTC_RX_GAP_Y, HLTC_RX, "F.Cu", S)  # left through gap
    trk(5.5, HLTC_RX_GAP_Y, 5.5, HLTC_RX_Y, HLTC_RX, "F.Cu", S)  # down to L13 Y
    trk(5.5, HLTC_RX_Y, HLTC_XL, HLTC_RX_Y, HLTC_RX, "F.Cu", S)  # right to L13 pad

    # ── R5 DE pull-up (R5 pad2 → RXB6 pin 6) ──────────
    trk(R5_X2, R5_Y, RXB6_X, RXB6_PIN_Y[5], DE_NET, "F.Cu", S)
    # R5 pad1 (V5) connects to V5 bus via copper pour or trace
    trk(R5_X1, R5_Y, R5_X1, V5_BUS_Y, V5, "F.Cu", S)

    # ── C1 bypass (V5 to GND near RXB6 VDD) ──────────
    # C1 V5 pad connects to V5 RXB6 feed (runs through pin 4 area)
    trk(C1_X1, C1_Y, C1_X1, RXB6_PIN_Y[3], V5, "F.Cu", S)
    trk(C1_X1, RXB6_PIN_Y[3], RXB6_X, RXB6_PIN_Y[3], V5, "F.Cu", S)
    # C1 GND pad connects to RXB6 GND pin 2 area
    trk(C1_X2, C1_Y, RXB6_X, RXB6_PIN_Y[1], GND, "F.Cu", S)

    # ── C2 bulk cap — V5 jogs right to avoid GND, GND jogs left
    # V5: pad1 (20,58) → right to X=22 → via → B.Cu up to V5 bus → via
    trk(C2_X, C2_Y1, C2_X + 2.0, C2_Y1, V5, "F.Cu", PW)     # jog right
    via_hole(C2_X + 2.0, C2_Y1, V5)
    trk(C2_X + 2.0, C2_Y1, C2_X + 2.0, V5_BUS_Y, V5, "B.Cu", PW)
    via_hole(C2_X + 2.0, V5_BUS_Y, V5)
    # GND: pad2 (20,60) → left to X=18 → up to GND bus
    trk(C2_X, C2_Y2, C2_X - 2.0, C2_Y2, GND, "F.Cu", PW)    # jog left
    trk(C2_X - 2.0, C2_Y2, C2_X - 2.0, GND_BUS_Y, GND, "F.Cu", PW)

    # ══════════════════════════════════════════════════════
    #  GND COPPER POUR (both layers)
    # ══════════════════════════════════════════════════════
    gnd_nid = _nets[GND]
    # Zone polygon follows board outline (with USB-C notch)
    zone_pts = " ".join([f"(xy {f(x)} {f(y)})" for x, y in outline[:-1]])
    for layer in ["F.Cu", "B.Cu"]:
        emit(f'  (zone (net {gnd_nid}) (net_name "GND") (layer "{layer}")\n'
             f'    (name "GND_{layer.replace(".", "")}")\n'
             f'    (hatch edge 0.5080)\n'
             f'    (connect_pads (clearance 0.3000))\n'
             f'    (min_thickness 0.2500)\n'
             f'    (fill yes (thermal_gap 0.5080) (thermal_bridge_width 0.5080))\n'
             f'    (polygon\n'
             f'      (pts\n'
             f'        {zone_pts}\n'
             f'      )\n'
             f'    )\n'
             f'  )')

    # ══════════════════════════════════════════════════════
    #  EMIT FOOTPRINTS & BUILD OUTPUT
    # ══════════════════════════════════════════════════════
    for fp_ in _fps:
        fp_.emit_fp()

    net_lines = ['  (net 0 "")'] + [
        f'  (net {nid} "{name}")'
        for name, nid in sorted(_nets.items(), key=lambda x: x[1]) if nid > 0
    ]

    doc = "\n".join([
        "(kicad_pcb",
        "  (version 20221018)",
        '  (generator "pcbnew")',
        "  (general",
        "    (thickness 1.6000)",
        "    (legacy_teardrops no)",
        "  )",
        '  (paper "A4")',
        "  (layers",
        '    (0 "F.Cu" signal)',
        '    (31 "B.Cu" signal)',
        '    (36 "B.SilkS" user "B.Silkscreen")',
        '    (37 "F.SilkS" user "F.Silkscreen")',
        '    (38 "B.Mask" user)',
        '    (39 "F.Mask" user)',
        '    (44 "Edge.Cuts" user)',
        '    (47 "F.CrtYd" user "F.Courtyard")',
        '    (49 "F.Fab" user "F.Fabrication")',
        "  )",
    ] + net_lines + _body + [")"])

    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        script_dir = os.path.expanduser("~")
    out_path = os.path.join(script_dir, "gate_sensor_v2.kicad_pcb")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(doc)
    print(f"""
Gate Sensor Carrier PCB v2.2  —  generated OK
Output : {out_path}
Board  : {BW} x {BH} mm  2-layer  1.6 mm  HASL
Nets   : {len(_nets)-1} named

v2.2 changes:
  - Board shrunk from 90x75mm to 75x66mm
  - R3/R4 moved below Nano (X≈60, Y≈50)
  - Connectors J2/J3/J4 moved up to Y=62
  - V5/GND buses at Y=55/57
  - All routing updated for compact layout

Includes:
  - GND copper pour on F.Cu and B.Cu (0.3mm clearance, thermal relief)

Next steps:
  1. make pcb-upgrade   (upgrade to KiCad 10 format)
  2. make drc           (design rules check)
  3. make fab           (gerbers + drill for JLCPCB)
""")

_build()
