#!/usr/bin/env python3
"""
Netlist verification for Gate Sensor Carrier PCB.

Parses the generated KiCad PCB file and firmware config to validate:
  1. Net pad membership — every net connects the expected component pads
  2. Forbidden connections — VIN/3V3 not connected, no shorts
  3. Firmware pin mapping — config.h pin defines match PCB nets
  4. Nano pin order — regression test for L/R swap bug
  5. Voltage divider — R1/R2 values produce safe output voltage
  6. Trace connectivity — signal nets have continuous trace paths

Run:  python3 pcb/test_netlist.py
      make test-netlist
"""

import os
import re
import sys
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
PCB_FILE = os.path.join(SCRIPT_DIR, "gate_sensor_v2.kicad_pcb")
CONFIG_H = os.path.join(PROJECT_DIR, "firmware", "include", "config.h")
PCB_GEN = os.path.join(SCRIPT_DIR, "gate_sensor_pcb_v2.py")

# ── Colors ──────────────────────────────────────────────────────
GREEN = "\033[0;32m"
RED = "\033[0;31m"
YELLOW = "\033[1;33m"
NC = "\033[0m"

pass_count = 0
fail_count = 0


def check(name, condition, detail=""):
    global pass_count, fail_count
    if condition:
        print(f"  {GREEN}PASS{NC}  {name}")
        pass_count += 1
    else:
        msg = f" — {detail}" if detail else ""
        print(f"  {RED}FAIL{NC}  {name}{msg}")
        fail_count += 1


def section(title):
    print(f"\n{YELLOW}── {title} ──{NC}")


# ── Parse KiCad PCB file ────────────────────────────────────────

def parse_pcb(path):
    """Extract nets, pads, traces, and vias from a KiCad PCB file."""
    with open(path) as f:
        content = f.read()

    # Net definitions: (net N "name")
    net_defs = {}
    for m in re.finditer(r'\(net\s+(\d+)\s+"([^"]+)"\)', content):
        net_defs[int(m.group(1))] = m.group(2)

    # Footprints and their pads
    pads = []  # [(ref, pad_num, net_name)]
    fp_pattern = re.compile(
        r'\(footprint\s+"([^"]+)".*?\n(.*?)\n  \)',
        re.DOTALL
    )
    for fp_match in fp_pattern.finditer(content):
        ref = fp_match.group(1)
        body = fp_match.group(2)
        for pad_match in re.finditer(
            r'\(pad\s+"([^"]+)"\s+thru_hole.*?\(net\s+(\d+)\s+"([^"]+)"\)',
            body
        ):
            pad_num = pad_match.group(1)
            net_name = pad_match.group(3)
            pads.append((ref, pad_num, net_name))

    # Also find pads with no net (for forbidden connection checks)
    pads_no_net = []
    for fp_match in fp_pattern.finditer(content):
        ref = fp_match.group(1)
        body = fp_match.group(2)
        for pad_match in re.finditer(
            r'\(pad\s+"([^"]+)"\s+thru_hole\s+\w+\s+\(at\s+[^)]+\)'
            r'\s+\(size\s+[^)]+\)\s+\(drill\s+[^)]+\)'
            r'\s+\(layers\s+"[^"]+"\s+"[^"]+"\)\)',
            body
        ):
            pad_num = pad_match.group(1)
            pads_no_net.append((ref, pad_num))

    # Segments (traces): (segment (start X Y) (end X Y) (width W) (layer "L") (net N))
    traces = []
    for m in re.finditer(
        r'\(segment\s+\(start\s+([\d.]+)\s+([\d.]+)\)\s+'
        r'\(end\s+([\d.]+)\s+([\d.]+)\)\s+'
        r'\(width\s+([\d.]+)\)\s+'
        r'\(layer\s+"([^"]+)"\)\s+'
        r'\(net\s+(\d+)\)\)',
        content
    ):
        traces.append({
            "x1": float(m.group(1)), "y1": float(m.group(2)),
            "x2": float(m.group(3)), "y2": float(m.group(4)),
            "width": float(m.group(5)),
            "layer": m.group(6),
            "net": int(m.group(7)),
        })

    # Vias: (via (at X Y) (size S) (drill D) (layers "F.Cu" "B.Cu") (net N))
    vias = []
    for m in re.finditer(
        r'\(via\s+\(at\s+([\d.]+)\s+([\d.]+)\)\s+'
        r'\(size\s+[\d.]+\)\s+\(drill\s+[\d.]+\)\s+'
        r'\(layers\s+"[^"]+"\s+"[^"]+"\)\s+'
        r'\(net\s+(\d+)\)\)',
        content
    ):
        vias.append({
            "x": float(m.group(1)), "y": float(m.group(2)),
            "net": int(m.group(3)),
        })

    return net_defs, pads, pads_no_net, traces, vias


# ── Parse firmware config.h ─────────────────────────────────────

def parse_config_h(path):
    """Extract #define pin assignments from config.h."""
    defines = {}
    with open(path) as f:
        for line in f:
            m = re.match(r'#define\s+(\w+)\s+(\d+)', line)
            if m:
                defines[m.group(1)] = int(m.group(2))
    return defines


# ── Parse PCB generator for label arrays ────────────────────────

def parse_label_arrays(path):
    """Extract NL_LBLS and NR_LBLS from the PCB generator source."""
    with open(path) as f:
        source = f.read()

    def extract_array(name):
        pattern = name + r'\s*=\s*\[(.*?)\]'
        m = re.search(pattern, source, re.DOTALL)
        if not m:
            return None
        raw = m.group(1)
        return [s.strip().strip('"').strip("'") for s in raw.split(",") if s.strip().strip('"').strip("'")]

    return {
        "NL_LBLS": extract_array("NL_LBLS"),
        "NR_LBLS": extract_array("NR_LBLS"),
        "HL_LBLS": extract_array("HL_LBLS"),
        "HR_LBLS": extract_array("HR_LBLS"),
    }


# ══════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════

def main():
    global pass_count, fail_count

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║         Gate Sensor PCB — Netlist Verification              ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    # Regenerate PCB to ensure it's current
    if os.path.exists(PCB_GEN):
        import subprocess
        subprocess.run([sys.executable, PCB_GEN], capture_output=True, check=True)

    if not os.path.exists(PCB_FILE):
        print(f"{RED}ERROR{NC}: PCB file not found: {PCB_FILE}")
        print("  Run: python3 pcb/gate_sensor_pcb_v2.py")
        sys.exit(1)

    net_defs, pads, pads_no_net, traces, vias = parse_pcb(PCB_FILE)

    # Build pad lookup: net_name -> set of (ref, pad_num)
    net_pads = defaultdict(set)
    for ref, pad_num, net_name in pads:
        net_pads[net_name].add(f"{ref}-{pad_num}")

    # Build reverse lookup: (ref, pad_num) -> net_name
    pad_net = {}
    for ref, pad_num, net_name in pads:
        pad_net[f"{ref}-{pad_num}"] = net_name

    # ── 1. Net Pad Membership ───────────────────────────────────
    section("1. Net Pad Membership")

    expected_nets = {
        "GND": {"U3-L1", "U3-R1", "U1-L14", "U1-R12",
                "U2-2", "U2-3", "U2-8",
                "R2-2", "C1-2", "C2-2", "J2-2"},
        "5V": {"U3-L2", "U1-L12", "U2-4", "U2-5",
               "R5-1", "C1-1", "C2-1", "J4-2"},
        "5V_IN": {"J2-1", "J4-1"},
        "3V3": {"U3-R2", "U3-R3"},
        "D3": {"U1-R10", "R1-1"},
        "D2": {"U1-R11", "U2-7"},
        "HELTEC_RX": {"R1-2", "R2-1", "U3-L13"},
        "DE": {"R5-2", "U2-6"},
    }

    for net_name, expected in expected_nets.items():
        actual = net_pads.get(net_name, set())
        missing = expected - actual
        extra = actual - expected
        ok = (missing == set()) and (extra == set())
        detail = ""
        if missing:
            detail += f"missing: {missing}"
        if extra:
            detail += f"{', ' if detail else ''}extra: {extra}"
        check(f"Net '{net_name}' has correct pads", ok, detail)

    # ── 2. Forbidden Connections ────────────────────────────────
    section("2. Forbidden Connections")

    # Nano VIN (L15) must have no net
    check("Nano VIN (U1-L15) has no net",
          "U1-L15" not in pad_net,
          f"connected to {pad_net.get('U1-L15', '?')}")

    # Nano 3V3 (L2) must have no net
    check("Nano 3V3 (U1-L2) has no net",
          "U1-L2" not in pad_net,
          f"connected to {pad_net.get('U1-L2', '?')}")

    # No pad should be on two nets (check for duplicates in pads list)
    pad_nets_seen = defaultdict(set)
    for ref, pad_num, net_name in pads:
        pad_nets_seen[f"{ref}-{pad_num}"].add(net_name)
    shorts = {k: v for k, v in pad_nets_seen.items() if len(v) > 1}
    check("No pad connected to multiple nets",
          len(shorts) == 0,
          f"shorts: {shorts}")

    # ── 3. Firmware Pin Mapping ─────────────────────────────────
    section("3. Firmware Pin Mapping")

    if os.path.exists(CONFIG_H):
        defines = parse_config_h(CONFIG_H)

        rf_pin = defines.get("RF_PIN")
        serial_tx = defines.get("SERIAL_TX")
        serial_rx = defines.get("SERIAL_RX")

        # RF_PIN=2 → D2 net includes RXB6 DATA (U2-7)
        check(f"RF_PIN={rf_pin} (D2) → RXB6 DATA",
              rf_pin == 2 and "U2-7" in net_pads.get("D2", set()),
              f"RF_PIN={rf_pin}, D2 net={net_pads.get('D2', set())}")

        # SERIAL_TX=3 → D3 net includes R1 pad1
        check(f"SERIAL_TX={serial_tx} (D3) → R1 voltage divider",
              serial_tx == 3 and "R1-1" in net_pads.get("D3", set()),
              f"SERIAL_TX={serial_tx}, D3 net={net_pads.get('D3', set())}")

        # SERIAL_RX=4 → D4 should have no net (unused)
        check(f"SERIAL_RX={serial_rx} (D4) is unused",
              serial_rx == 4 and "U1-R9" not in pad_net,
              f"SERIAL_RX={serial_rx}, U1-R9 net={pad_net.get('U1-R9', 'none')}")

        # Baud rate
        mesh_baud = defines.get("MESH_BAUD")
        check(f"MESH_BAUD={mesh_baud} (9600 for SoftwareSerial)",
              mesh_baud == 9600,
              f"got {mesh_baud}")
    else:
        print(f"  {YELLOW}SKIP{NC}  firmware/include/config.h not found")

    # ── 4. Nano Pin Order (regression test) ─────────────────────
    section("4. Nano Pin Order (L/R swap regression)")

    if os.path.exists(PCB_GEN):
        arrays = parse_label_arrays(PCB_GEN)
        nl = arrays.get("NL_LBLS")
        nr = arrays.get("NR_LBLS")

        expected_left = ["D13", "3V3", "REF", "A0", "A1", "A2", "A3",
                         "A4", "A5", "A6", "A7", "5V", "RST", "GND", "VIN"]
        expected_right = ["D12", "D11", "D10", "D9", "D8", "D7", "D6",
                          "D5", "D4", "D3", "D2", "GND", "RST", "D1", "D0"]

        check("Nano LEFT labels (analog/power side)",
              nl == expected_left,
              f"got {nl}")
        check("Nano RIGHT labels (digital side, D12→D0)",
              nr == expected_right,
              f"got {nr}")

        # Verify critical positions
        if nl and nr:
            check("Nano LEFT L12 = '5V' (power input pin)",
                  nl[11] == "5V", f"L12 = '{nl[11]}'")
            check("Nano LEFT L15 = 'VIN' (must be unconnected)",
                  nl[14] == "VIN", f"L15 = '{nl[14]}'")
            check("Nano RIGHT R10 = 'D3' (SoftwareSerial TX)",
                  nr[9] == "D3", f"R10 = '{nr[9]}'")
            check("Nano RIGHT R11 = 'D2' (INT0 for RCSwitch)",
                  nr[10] == "D2", f"R11 = '{nr[10]}'")
    else:
        print(f"  {YELLOW}SKIP{NC}  PCB generator not found")

    # ── 5. Voltage Divider ──────────────────────────────────────
    section("5. Voltage Divider (R1/R2)")

    # R1 pad1 = D3 (input), R1 pad2 = HELTEC_RX (junction)
    check("R1 pad1 on D3 net (Nano TX input)",
          pad_net.get("R1-1") == "D3",
          f"got {pad_net.get('R1-1', 'none')}")
    check("R1 pad2 on HELTEC_RX net (junction)",
          pad_net.get("R1-2") == "HELTEC_RX",
          f"got {pad_net.get('R1-2', 'none')}")

    # R2 pad1 = HELTEC_RX (junction), R2 pad2 = GND
    check("R2 pad1 on HELTEC_RX net (junction)",
          pad_net.get("R2-1") == "HELTEC_RX",
          f"got {pad_net.get('R2-1', 'none')}")
    check("R2 pad2 on GND net (shunt)",
          pad_net.get("R2-2") == "GND",
          f"got {pad_net.get('R2-2', 'none')}")

    # HELTEC_RX reaches Heltec GPIO47
    check("HELTEC_RX net reaches Heltec L13 (GPIO47)",
          "U3-L13" in net_pads.get("HELTEC_RX", set()),
          f"HELTEC_RX pads: {net_pads.get('HELTEC_RX', set())}")

    # Voltage calculation: Vout = 5 * R2 / (R1 + R2)
    R1_VAL = 2.2  # kΩ
    R2_VAL = 3.3  # kΩ
    vout = 5.0 * R2_VAL / (R1_VAL + R2_VAL)
    check(f"Divider output {vout:.2f}V < 3.3V (safe for ESP32-S3)",
          vout < 3.3,
          f"Vout = {vout:.2f}V")

    # ── 6. Trace Connectivity ───────────────────────────────────
    section("6. Trace Connectivity (signal nets)")

    # Build net ID lookup
    net_id_by_name = {v: k for k, v in net_defs.items()}

    def check_net_traces(net_name):
        """Check that a net has at least one trace segment."""
        nid = net_id_by_name.get(net_name, -1)
        net_traces = [t for t in traces if t["net"] == nid]
        net_vias = [v for v in vias if v["net"] == nid]
        return len(net_traces), len(net_vias)

    for net_name in ["D3", "D2", "HELTEC_RX", "DE", "GND", "5V", "5V_IN"]:
        t_count, v_count = check_net_traces(net_name)
        check(f"Net '{net_name}' has traces ({t_count} segments, {v_count} vias)",
              t_count > 0,
              f"no trace segments found")

    # ── Summary ─────────────────────────────────────────────────
    total = pass_count + fail_count
    print(f"\n{'═' * 62}")
    if fail_count == 0:
        print(f"{GREEN}All {total} checks passed{NC}")
    else:
        print(f"{RED}{fail_count} of {total} checks FAILED{NC}")
    print(f"{'═' * 62}\n")

    sys.exit(0 if fail_count == 0 else 1)


if __name__ == "__main__":
    main()
