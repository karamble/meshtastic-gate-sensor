# Gate Sensor Technical Handbook

*A reference for builders, modifiers, and the technically curious.*

---

## Table of Contents

1. [System Architecture](#1-system-architecture)
2. [Carrier PCB v2.5](#2-carrier-pcb-v25)
3. [Pin Map](#3-pin-map)
4. [Power](#4-power)
5. [Firmware Architecture](#5-firmware-architecture)
6. [EEPROM Layout](#6-eeprom-layout)
7. [CMD Protocol Wire Reference](#7-cmd-protocol-wire-reference)
8. [Build, Flash, Monitor](#8-build-flash-monitor)
9. [Heltec Flash: Standalone vs Developer Modes](#9-heltec-flash-standalone-vs-developer-modes)
10. [PCB Fabrication and Self-Test](#10-pcb-fabrication-and-self-test)
11. [Modifying the Design](#11-modifying-the-design)
12. [Known Issues and Wishlist](#12-known-issues-and-wishlist)
13. [References](#13-references)

---

## 1. System Architecture

```
KERUI D026          RXB6 433 MHz       Arduino Nano             Heltec LoRa32 V3
door sensor         receiver           (ATmega328P, 5V)         (ESP32-S3 + SX1262)
                                                                running stock Meshtastic
+-----------+       +----------+       +----------------+       +----------------+
| 433 MHz   |~~~~~> | DATA  ---|------>| D2 (INT0)      |       |                |
| open/close|       | DE <-R5- |--+    |                |       |                |
+-----------+       | VDD  5V  |  |    | D3 (TX)  ------|---->| GPIO47 (RX)    |
                    +----------+  |    |                | R1/R2 |                |
                                  |    |                | divider                |
                                  |    | D4 (RX) <------|<------| GPIO48 (TX)    |
                                  |    |   5V     5V/GND|       |  5V / GND      |
                                  |    +----------------+       +----------------+
                                  |                                     |
                              5V bus (J2/J4 fed from Waveshare)         |
                                                                        v
                                                                  LoRa mesh (any region)
```

Everything hangs off a single 5 V rail. The gate sensor's two MCUs talk to each other over a UART that is **bidirectional from PCB v2.5 onwards** — the Nano sends gate events to the Heltec for forwarding to the mesh, and the Heltec's Meshtastic serial module relays inbound `@Gate` commands back to the Nano on GPIO48 → Nano D4. The Heltec runs **stock** Meshtastic firmware; nothing custom is built or flashed on the ESP32-S3 side. The serial module's `TEXTMSG` mode is the integration glue.

The Nano's USB-UART (115200 baud, hardware UART) is independent of the Heltec UART and is used purely for build/upload, debug serial, and 433 MHz sensor learning (`make learn-sensor`).

---

## 2. Carrier PCB v2.5

A 75 × 66 mm two-layer FR-4 board, 1.6 mm thick, 1 oz copper, lead-free HASL. Generated programmatically by `pcb/gate_sensor_pcb_v2.py` — the script writes KiCad S-expressions directly without depending on `pcbnew` or SWIG, so it runs anywhere Python 3 runs. The KiCad file (`pcb/gate_sensor_v2.kicad_pcb`) is the output, not the source.

| Parameter | Value |
|---|---|
| Dimensions | 75 × 66 mm with USB-C notch (X = 10–29, 8 mm deep) |
| Layers | F.Cu / B.Cu |
| Min trace / space | 0.25 mm signal, 0.50 mm power / 0.30 mm |
| Min drill | 0.8 mm |
| Vias | 1.4 mm pad / 0.8 mm drill (22 total) |
| DRC status | 0 violations, 0 unconnected nets |

### Layout summary

```
         10    29
    ┌─────┘    └──────────────────────────┐
    │     USB-C notch (Heltec connector)  │
    │                                     │
    │  U3 Heltec    U2 RXB6   U1 Nano    │  66 mm
    │                                     │
    │  C2   J4-sw              J2-PWR    │
    └─────────────────────────────────────┘
                     75 mm
```

Top half holds the three "modules":

| Ref | Component | Footprint | Notes |
|---|---|---|---|
| **U3** | Heltec LoRa32 V3 | 2×18 socket, 22.86 mm row pitch | Socketed, removable |
| **U1** | Arduino Nano | 2×15 socket, 15.24 mm (600 mil) row pitch | Socketed, removable |
| **U2** | RXB6 433 MHz receiver | 8-pin SIP, 2 groups of 4 with 25.4 mm gap | Direct-soldered, **not** socketed |

Passives sit between the Nano and RXB6:

| Ref | Value | Role |
|---|---|---|
| R1 | 2.2 kΩ | Logic-divider series (Nano D3 → Heltec GPIO47) |
| R2 | 3.3 kΩ | Logic-divider shunt to GND |
| R5 | 10 kΩ | DE pull-up for RXB6 pin 6 (do-not-populate by default; see "BOM" → R5 note) |
| C1 | 100 nF ceramic | RXB6 VDD bypass |
| C2 | 100 µF electrolytic | 5 V bus bulk decoupling |

Connectors at the bottom edge:

| Ref | Type | Role |
|---|---|---|
| J2 | 2-pin 5.08 mm screw terminal | Power in (5 V from Waveshare + GND) |
| J4 | JST-PH 2 mm 2-pin | Power switch in-line with the 5 V bus |

### Logic-level divider

The Nano runs at 5 V; the Heltec's GPIO47 expects 3.3 V logic. A passive divider produces 3.0 V at the Heltec input, well above its V_IH:

```
Nano D3 (5 V) ──── R1 (2.2 kΩ) ────┬──── Heltec GPIO47
                                    │
                                R2 (3.3 kΩ)
                                    │
                                   GND

V_out = 5 V × 3.3 / (2.2 + 3.3) = 3.0 V
```

The **return path** (Heltec GPIO48 → Nano D4) does **not** need a divider — the Heltec drives 3.3 V which the ATmega328P at 5 V VCC happily reads as logic high (V_IH ≥ 3 V at 5 V VCC). PCB v2.4 included a 4.7 kΩ series resistor R6 here as ESD/back-feed protection, but bring-up showed it attenuated the signal below V_IH and dropped received bytes; **v2.5 removed R6** and routes Heltec GPIO48 directly to Nano D4. (See `pcb.md` for the full version history.)

### Routing strategy

- **F.Cu (top):** all signal traces, plus most of the 5 V and GND distribution as 0.50 mm power traces along Y = 56 (V5) / Y = 58 (GND).
- **B.Cu (bottom):** GND drops from each module's GND pin via offset vias, plus the few traces that have to cross F.Cu (notably the V5 feed from J4 that needs to cross the GND bus, and the D2/RF-DATA trace that has to cross D3).
- **GND pours** on both layers, following the board outline including the USB-C notch.

The `pcb/test_netlist.py` self-test checks 34 specific net invariants (no V5/GND short, no VIN-to-5V leakage, R1/R2 divider math is correct, every firmware pin in `config.h` matches the PCB net, etc.) and catches accidental regressions in the Python generator.

### Board renders

- `pcb/output/board.svg` — vector render of all four printable layers
- `pcb/output/board.pdf` — PDF version
- `newpcb.png` — high-resolution photo of an assembled board (top of repo)
- 3D model preview: `make assembly` then `make open-assembly` (requires the KiCad AppImage).

![Carrier PCB](../newpcb.png)

---

## 3. Pin Map

Authoritative source for pin assignments: `firmware/include/config.h` for the Nano side; `scripts/flash-heltec-meshtastic.sh` (`serial.rxd`, `serial.txd`) for the Heltec side. The PCB nets are checked against both at build time by `pcb/test_netlist.py`.

### Arduino Nano (U1) — 2 × 15 pins, 15.24 mm row spacing

| Nano pin | Net | Role | Where else it goes |
|---|---|---|---|
| D2 (L5) | `D2` | RF DATA in (INT0 for RCSwitch) | RXB6 pin 7 |
| D3 (L6) | `D3` | SoftwareSerial TX → Heltec | R1 pad 1 (divider input) |
| D4 (L7) | `HELTEC_TX` | SoftwareSerial RX ← Heltec | Heltec GPIO48 (direct, v2.5) |
| 5V (R12) | `5V` | Power in (5 V bus, **not** VIN) | Heltec L2, RXB6 pins 4/5, J4 pin 2 |
| GND (L4, R14) | `GND` | Ground | All module GNDs |
| VIN (R15) | — | **Not connected** — VIN routes to the Nano's onboard regulator and connecting it to the 5 V bus would short the regulator output back to its input |

### Heltec LoRa32 V3 (U3) — 2 × 18 pins

| Heltec pin | Net | Role |
|---|---|---|
| L1 / R1 | `GND` | Ground |
| L2 | `5V` | 5 V power input — Heltec's onboard regulator steps down to 3V3 |
| L13 (GPIO47) | `HELTEC_RX` | Meshtastic serial module RX, fed by Nano D3 through R1/R2 divider |
| L14 (GPIO48) | `HELTEC_TX` | Meshtastic serial module TX, direct to Nano D4 (v2.5) |
| R2 / R3 | `3V3` | Heltec's 3.3 V output (bridged on the carrier; **not** distributed to other modules) |

The Heltec V3 has GPIO44 wired to its CP2102 USB-UART. Using GPIO44 for the Meshtastic serial module would conflict with USB; **GPIO47 is the correct choice**. Likewise `serial.txd` must be set to a usable GPIO that is *not* a strap pin — the flash script uses `48`. **Setting `serial.txd=0` silently kills RX as well**, because GPIO0 is an ESP32-S3 boot strap and the UART driver init fails.

### RXB6 433 MHz receiver (U2)

8-pin SIP, two 4-pin groups with a 25.4 mm gap, body extends right.

| Pin | Label | Net | Role |
|---|---|---|---|
| 1 | ANT | — | 17.3 cm whip or SMA pigtail to bulkhead |
| 2 / 3 / 8 | GND | `GND` | Ground |
| 4 / 5 | VDD | `5V` | Power. **Run on 5 V**, not 3.3 V — better sensitivity, and the DATA output is still 5 V-logic-compatible with Nano D2. |
| 6 | DE | `DE` | Data enable — held high via R5 (10 kΩ pull-up to 5 V). Many RXB6 batches have an internal bias and float high without R5; ours is do-not-populate by default. Populate if your unit doesn't decode without it. |
| 7 | DATA | `D2` | Decoded RF data → Nano D2 (INT0) |

---

## 4. Power

```
USB-C ───┐                                       J4 (toggle switch)
         ↓                                        +-----+
Waveshare Solar Power Mgr D              J2       |     |
  +---------------------+                          |     |
  | USB-C in            |                          |     |
  | Solar in (optional) +─── 5V_IN ───── pin1 ────| IN  |
  | 3 × 18650 cells     +─── GND ──────────────|  | OUT +─── 5V bus
  | 5 V boost converter |                       |  +-----+
  +---------------------+                       |     │
                                               (J4 pin 2 is the bus
                                                feed; everything
                                                downstream is on
                                                switched 5 V)
```

The Waveshare Solar Power Manager D has three input paths to its boost converter / charger, any of which can keep the system running:

- **USB-C** — the default for indoor / bench / development use.
- **18650 cells** — three in parallel, 3000 mAh each. Charged from either USB-C or solar; discharged to power the system when neither is supplying current.
- **Solar panel (optional)** — a 6 V panel into the Waveshare's solar input keeps the batteries topped up for outdoor installs. Not part of the kit; source any 6 V panel with a compatible connector.

| Quantity | Value |
|---|---|
| Total system draw | ~105 mA at 5 V (Heltec dominates) |
| Battery capacity | 3 × 18650 3000 mAh ≈ 9 Ah @ 3.7 V ≈ 33 Wh |
| Battery-only runtime (no USB / no solar) | ~85 hours |
| Solar input on a clear midday (typical 6 V 2 W panel) | ~330 mA at 6 V |

No charging circuitry on the carrier board; everything is offloaded to the Waveshare. C2 (100 µF) on the carrier smooths inrush at switch-on; C1 (100 nF) bypasses the RXB6 VDD specifically.

The 5 V bus is **switched by J4** — flip the toggle and everything downstream loses power instantly. There is no soft-shutdown sequence; the Nano's EEPROM writes are atomic at the byte level so this is safe in practice.

---

## 5. Firmware Architecture

The Nano firmware lives in `firmware/`. Build system: PlatformIO (`firmware/platformio.ini`):

```ini
[env:nano]
platform = atmelavr
board = nanoatmega328new        # optiboot bootloader, 115200 baud — clone Nanos
framework = arduino
monitor_speed = 115200
lib_deps =
    sui77/rc-switch@^2.6.4
```

Source map:

| File | Role |
|---|---|
| `firmware/src/main.cpp` | Everything: setup/loop, RF, EEPROM, CMD parser, ACK emission |
| `firmware/include/config.h` | Compile-time constants (pin assignments, defaults, EEPROM addresses) |

### Boot sequence (`setup()`)

1. **Disable the watchdog** (`wdt_disable()`). Optiboot leaves WDT enabled with its last value after a watchdog reset; not clearing it would re-trigger an immediate reset.
2. Bring up USB serial at 115200 (debug echo) and SoftwareSerial at 9600 (Meshtastic).
3. `rf.enableReceive(digitalPinToInterrupt(RF_PIN))` — RCSwitch hooks INT0 on D2.
4. **Bootcount**: read 16-bit counter from EEPROM, treat `0xFFFF` (fresh chip) as 0, increment, write back.
5. **Heartbeat config**: read `hbEnabled` (byte) and `hbIntervalMin` (byte). Out-of-range or `0xFF` → defaults (`true`, 30 min).
6. **Debounce config**: same pattern, defaults to 10 s.
7. **Hit counter**: read 32-bit value; `0xFFFFFFFF` → 0.
8. **Code registry**: load 16 × 4 B codes and the parallel 16 × 16 B name table from EEPROM. Empty slot sentinel `0xFFFFFFFF`. **If the registry is completely empty**, seed slot 0 with `DEFAULT_CODE_OPEN` (= `150910`, KERUI D026 factory code) so out-of-the-box installs work without a `CODE_ADD`.
9. `delay(8000)` — give the Heltec time to boot and open its Meshtastic serial module before sending the first byte. Sending earlier drops bytes into a closed UART.
10. Emit the boot STATUS frame.

### Main loop (`loop()`)

Three responsibilities, run round-robin every iteration:

#### RF event handling

```c
if (rf.available()) {
    unsigned long code = rf.getReceivedValue();
    rf.resetAvailable();

    unsigned long debounceMs = (unsigned long)debounceSec * 1000UL;
    if (code != 0) {
        int8_t idx = codeIndexOf((uint32_t)code);
        if (idx >= 0) {
            // Known code — per-code debounce
            if ((now - codeLastEvent[idx]) > debounceMs) {
                codeLastEvent[idx] = now;
                hitCount++;
                saveHitCount();
                sendTriggered((uint32_t)code, codeNames[idx]);
            }
        } else if ((now - lastUnknownEvent) > debounceMs) {
            // Unknown code — single global debounce
            lastUnknownEvent = now;
            char buf[64];
            snprintf(buf, sizeof(buf), "RF unknown: %lu", code);
            Serial.println(buf);                                // USB only
            if (code >= UNKNOWN_MIN_CODE) {
                sendTriggered((uint32_t)code, "unknown");        // mesh
            }
        }
    }
}
```

Two key design choices:

- **Per-code debounce**: each registered code has its own `codeLastEvent[]` slot. Two physically separate sensors (e.g. front gate + back gate) firing within the same 10 s window both get reported. Without per-code debounce, a back-gate event right after a front-gate event would be silently swallowed.
- **Unknown codes share a single global debounce window** to keep 433 MHz noise from flooding the mesh. A code below `UNKNOWN_MIN_CODE` (= 1000) is logged on USB only — those are essentially noise from cheap remotes, weather stations, etc. Above 1000, it is broadcast as `Gate: TRIGGERED:<code> unknown` for the operator's `CODE_ADD`.

#### Inbound CMD handling — `pollCmd()`

Drains SoftwareSerial RX into `cmdBuf[]` byte-by-byte. On `\n` (line terminator), the line is dispatched to `processCmdLine()`. Buffer overflow (line longer than `CMD_BUF_SIZE` = 80 B) discards the partial line to avoid mis-parsing a truncation.

`processCmdLine()` does the unusual heavy lifting that the gate sensor inherits from Meshtastic's serial-module behaviour: when a remote node broadcasts text, the Heltec's serial module emits it on GPIO48 prefixed with the **sender's short name** and `: `, e.g. `1e44: @Gate STATUS`. The parser skips past any `<anything>: ` prefix, then looks for the `@` addressing token.

```c
static void processCmdLine(char* line) {
    char* at = strchr(line, '@');
    if (!at) return;                      // not addressed at us
    line = at;
    char* space = strchr(line + 1, ' ');
    if (!space) return;                   // no verb
    *space = '\0';
    const char* target = line + 1;        // "Gate" / "ALL" / "Other"
    char* rest = space + 1;
    while (*rest == ' ') rest++;

    char* colon = strchr(rest, ':');
    const char* param = NULL;
    if (colon) { *colon = '\0'; param = colon + 1; }
    const char* verb = rest;
    if (*verb == '\0') return;
    handleCommand(target, verb, param);
}
```

`handleCommand()` then case-insensitively matches `target` against `ALL` and `SENSOR_NAME` (= `"Gate"`), and dispatches the verb. Unknown verbs are silently ignored (no NACK spam on the mesh).

#### Periodic STATUS heartbeat

```c
if (hbEnabled && (now - lastStatus >= (unsigned long)hbIntervalMin * 60000UL)) {
    lastStatus = now;
    sendStatus();
}
```

Default 30 minutes. Resets on `HB_INTERVAL` change so the next STATUS comes `<minutes>` from the command, not from when the previous interval would have fired.

### Outbound message helpers

| Helper | Format |
|---|---|
| `sendStatus()` | `Gate: STATUS: Mode:ARMED Scan:GATE Hits:%lu Temp:0.0C Up:%02u:%02u:%02u Type:GATESENSOR Boot:%u` |
| `sendTriggered(code, name)` | `Gate: TRIGGERED:%lu %s` (`%s` is `name`, `"unnamed"` if null/empty, or `"unknown"` for unregistered codes) |
| `sendAck(verb, status)` | `Gate: %s_ACK:%s` |
| `sendCodeList()` | `Gate: CODES:<code>=<name>,…` or `Gate: CODES:NONE` |
| `sendMessage(buf)` | echoes `buf` to **both** SoftwareSerial (mesh) and USB serial (debug) |

### Why this firmware can't ever support DMs

Meshtastic 2.5+ encrypts direct messages end-to-end with PKI. The Heltec's SerialModule in `TEXTMSG` mode is the only path to GPIO48 the Nano can listen on, and that path is broadcast-only by design — DMs never reach the UART. There is no firmware change on the Nano that recovers them; the bytes have already been discarded by the SerialModule.

To support DMs you'd need to switch the Heltec to `PROTO` mode (binary protobuf payloads) and replace the Nano with a chip big enough to host the [Meshtastic-arduino](https://github.com/meshtastic/Meshtastic-arduino) library — the ATmega328P's 2 KB SRAM is too tight. An XIAO ESP32-S3 (or the Heltec's own ESP32 if you just merge the two MCUs) would be a comfortable fit. We have not done this and have no near-term plans to.

---

## 6. EEPROM Layout

ATmega328P has 1 kB EEPROM. Layout below; everything not listed is reserved (read as `0xFF` from a virgin chip).

| Address | Size | Field | Notes |
|---|---|---|---|
| 0–1 | 2 B (`uint16_t`) | `bootCount` | Increments once per `setup()`. Fresh `0xFFFF` → 0. |
| 2 | 1 B (`uint8_t`) | `hbEnabled` | `0xFF`/`1` = on, `0` = off. Mutated by `HB_ON` / `HB_OFF`. |
| 3 | 1 B | `hbIntervalMin` | Minutes (1–60). `0xFF` or out-of-range → `DEFAULT_HB_MIN` = 30. Mutated by `HB_INTERVAL`. |
| 4 | 1 B | `debounceSec` | Seconds (1–60). `0xFF` or out-of-range → `DEFAULT_DEBOUNCE_SEC` = 10. Mutated by `DEBOUNCE_SET`. |
| 5 | 1 B | reserved | |
| 6–9 | 4 B (`uint32_t`) | `hitCount` | Cumulative trigger count. `0xFFFFFFFF` → 0. Mutated on every TRIGGERED event and by `HITS_RESET`. |
| 10–11 | 2 B | reserved | |
| 12–75 | 64 B | `codes[16]` × `uint32_t` | Registered RF codes. `0xFFFFFFFF` = empty slot. Mutated by `CODE_ADD` / `CODE_REMOVE` / `CODE_CLEAR`. |
| 76–331 | 256 B | `codeNames[16]` × 16 B | Parallel name table. First byte `0xFF` or `0x00` = unnamed. |

Writes use `EEPROM.put` and `EEPROM.update`, both of which skip cells whose value already matches — unchanged bytes don't burn write cycles. ATmega328P EEPROM is rated for 100 k writes per cell. The hit counter is the most-written cell at one write per trigger; at ~10 triggers/day, the cell will outlast the rest of the hardware.

`saveNameSlot(idx)` rewrites only one of the 16 name slots so a `CODE_ADD` doesn't churn the entire 256 B name table.

---

## 7. CMD Protocol Wire Reference

### Wire format

```
@<target> <verb>[:<param1>[:<param2>...]]\n
```

- `<target>`: case-insensitive match against `ALL` or `SENSOR_NAME` (default `"Gate"`).
- `<verb>`: uppercase. Unknown verbs are silently dropped.
- `<params>`: colon-delimited.
- `\n` terminates a line. The parser strips an optional leading `<anything>: ` prefix (which the Meshtastic SerialModule prepends in `TEXTMSG` mode with the sender's short name).

The reply, when there is one, takes the form:

```
Gate: <VERB>_ACK:<status>\n
```

…except for `STATUS` (the STATUS frame itself is the reply) and `CODE_LIST` (a single-line `Gate: CODES:…` frame).

### Verb table

| Verb | Param | EEPROM addr touched | ACK / reply | Notes |
|---|---|---|---|---|
| `STATUS` | — | none | (`STATUS` frame) | On-demand heartbeat |
| `HB_ON` | — | 2 | `HB_ACK:OK` | Re-enable periodic STATUS |
| `HB_OFF` | — | 2 | `HB_ACK:OK` | Suspend periodic STATUS (boot + on-demand still fire) |
| `HB_INTERVAL` | `<1-60>` | 3 | `HB_ACK:OK` / `HB_ACK:ERROR` | Restarts the timer |
| `REBOOT` | — | none | `REBOOT_ACK:OK`, then watchdog reset | New STATUS arrives ~10 s later, `Boot:` incremented |
| `HITS_RESET` | — | 6 | `HITS_RESET_ACK:OK` | Zero the persistent counter |
| `DEBOUNCE_SET` | `<1-60>` | 4 | `DEBOUNCE_ACK:OK` / `DEBOUNCE_ACK:ERROR` | Per-code and global windows both use this |
| `CODE_ADD` | `<code>[:<name>]` | 12-75, 76-331 | `CODE_ACK:OK` / `UPDATED` / `EXISTS` / `FULL` / `ERROR` | Code in `[1, 16777215]` (24-bit). Name 1–15 chars `[A-Za-z0-9_-]`. |
| `CODE_REMOVE` | `<code>` | 12-75, 76-331 | `CODE_ACK:OK` / `NOT_FOUND` / `ERROR` | |
| `CODE_LIST` | — | none | `CODES:<c>=<n>,…` or `CODES:NONE` | Single text frame, not an ACK |
| `CODE_CLEAR` | — | 12-75, 76-331 | `CODE_ACK:OK` | Wipes registry |

### CODE_ADD result semantics

```c
enum CodeAddResult { CODE_ADDED, CODE_UPDATED, CODE_EXISTS, CODE_FULL };

CodeAddResult codeAddOrUpdate(uint32_t c, const char* name);
```

| Result | Wire ACK | When |
|---|---|---|
| `CODE_ADDED` | `OK` | New code, new slot |
| `CODE_UPDATED` | `UPDATED` | Code already registered, but the supplied name differs from the stored one — the name is overwritten |
| `CODE_EXISTS` | `EXISTS` | Code already registered, no name change needed (caller passed no name, or the same name) |
| `CODE_FULL` | `FULL` | All 16 slots taken |

`ERROR` is emitted before `codeAddOrUpdate()` is called, when the code is out of range or the name fails `nameValid()` (only `[A-Za-z0-9_-]`, 1–15 chars).

### Identity invariant

The target-matching code assumes the Heltec's Meshtastic owner short-name matches the Nano's `SENSOR_NAME`. The flash script sets `--set-owner-short "GATE"`; if you ever change `SENSOR_NAME` you must re-flash the Heltec with the matching owner. TEXTMSG mode strips envelope metadata so the Nano cannot discover the Heltec's short-name at runtime.

---

## 8. Build, Flash, Monitor

```bash
make build           # PlatformIO compile
make upload          # Flash the Nano (auto-detect FTDI port by VID:PID)
make monitor         # USB serial at 115200 baud
make learn-sensor    # Same monitor, with a banner explaining how to read it
make clean           # PlatformIO clean
```

### Nano port auto-detection

The Makefile resolves the Nano's USB port by FTDI VID:PID through the `/dev/serial/by-id/` symlinks:

```make
NANO_PORT = $(shell \
  ports=$$(ls /dev/serial/by-id/usb-FTDI_FT232R_USB_UART_*-if00-port0 2>/dev/null); \
  count=$$(echo "$$ports" | grep -c .); \
  if [ "$$count" -eq 0 ]; then echo "NANO_NOT_FOUND"; \
  elif [ "$$count" -gt 1 ]; then echo "MULTIPLE_NANOS"; \
  else echo "$$ports"; fi)
```

This **avoids ever flashing the wrong device** when both the Nano (FTDI FT232R) and the Heltec (Silicon Labs CP2102) are plugged into the same host. If two FTDI Nanos are co-plugged, the upload bails with `MULTIPLE_NANOS` and asks you to set `upload_port` manually.

### Bootloader gotcha

Modern clone Nanos ship with **optiboot** at 115200 baud, not the legacy bootloader at 57600. `platformio.ini` MUST be:

```ini
board = nanoatmega328new      # optiboot, 115200
```

…not `nanoatmega328` (legacy, 57600). Using the wrong one produces "stk500_recv: programmer is not responding" on every upload.

### Debug serial

`make monitor` opens the Nano's USB UART at 115200. The firmware echoes every mesh-bound message there too, and prints `RF unknown: <decimal>` for any 433 MHz code that wasn't already registered. This is the same stream `make learn-sensor` uses.

---

## 9. Heltec Flash: Standalone vs Developer Modes

The Heltec runs **stock** Meshtastic. `scripts/flash-heltec-meshtastic.sh` automates flash + post-flash configuration, downloads the latest stock release via `gh`, and verifies every setting before exiting.

The script has two modes that differ only in PSK and Bluetooth handling:

| Setting | Default mode (developer) | `--standalone` (retail) |
|---|---|---|
| Channel PSK | private 256-bit from `.env`'s `MESH_PSK` | factory default LongFast `AQ==` |
| Bluetooth | disabled | enabled (default) |
| LoRa region | EU_868 (or `-r`) | EU_868 (or `-r`) |
| GPS | NOT_PRESENT | NOT_PRESENT |
| Serial module | GPIO47 RX / GPIO48 TX, 9600 baud, TEXTMSG | same |
| Owner long / short | GateSensor / GATE | same |
| `.env` `MESH_PSK` required | yes | no |
| Verification step | asserts PSK ≠ `AQ==`, BLE = false | asserts PSK = `AQ==`, BLE = true |

### Running it

```bash
# Connect Heltec via USB-C, put in boot mode (hold BOOT, press+release RST, release BOOT)

./scripts/flash-heltec-meshtastic.sh                    # developer / private mesh (needs .env)
./scripts/flash-heltec-meshtastic.sh --standalone       # retail / public LongFast

# Common flags (work in both modes)
./scripts/flash-heltec-meshtastic.sh -r US              # different region
./scripts/flash-heltec-meshtastic.sh -p /dev/ttyUSB1    # specific port
./scripts/flash-heltec-meshtastic.sh -v v2.7.15.567b8ea # specific Meshtastic release
./scripts/flash-heltec-meshtastic.sh --flash-only       # firmware only, no config
./scripts/flash-heltec-meshtastic.sh --config-only      # config only, skip firmware
./scripts/flash-heltec-meshtastic.sh --confirm-config   # read back & verify; no writes
```

Or via Make:

```bash
make flash-heltec-standalone
```

### What the config step actually does

For each setting, the script invokes `meshtastic --port <port> --set <key> <value>`:

- `lora.region`
- (`--standalone` skipped) `--ch-set psk "$MESH_PSK" --ch-index 0`
- `position.gps_mode NOT_PRESENT`
- `telemetry.device_update_interval 1800`
- `serial.enabled true`, `serial.echo false`, `serial.rxd 47`, `serial.txd 48`, `serial.baud BAUD_9600`, `serial.timeout 0`, `serial.mode TEXTMSG`
- `--set-owner GateSensor --set-owner-short GATE`
- (`--standalone` skipped) `bluetooth.enabled false`

The `serial.txd 48` is **load-bearing** — see the comment block at line 482 of the script. `txd 0` would silently kill RX too, because GPIO0 is an ESP32-S3 boot strap pin and the UART driver init fails when handed it. GPIO48 is unused on the carrier and safe.

### Why two modes exist

- **Developer/private**: when you're testing a unit on your bench mesh, or assembling for a customer who wants their unit pre-tied to their existing private mesh, you want a 256-bit PSK already loaded and BLE off (BLE has measurable idle current and you don't need it for USB-attached config).
- **Standalone/retail**: a unit going to a first-time buyer should ship on the public LongFast channel so the buyer can see it on any stock Meshtastic node out of the box, and BLE should be **on** so the buyer can pair with the Meshtastic mobile app and migrate to a private PSK themselves. The user handbook is written for this state.

---

## 10. PCB Fabrication and Self-Test

### Self-test before fab

```bash
make test-netlist
```

Runs `pcb/test_netlist.py`, which checks 34 invariants on the generated `.kicad_pcb` file directly:

- Net membership: every pad is on the right net
- Forbidden connections: no V5 / GND short, no VIN / 5V short
- Firmware ↔ PCB consistency: every `RF_PIN` / `SERIAL_TX` / `SERIAL_RX` constant in `config.h` resolves to the right Nano pad
- Voltage divider math: R1 = 2.2k, R2 = 3.3k, divider output is 3.0 V
- Trace continuity: no orphan stubs

A regression in the Python generator that, say, swaps two pads, fails this test before you ever upload Gerbers to a fab. CI should run `make drc && make test-netlist` on every PR that touches `pcb/`.

### Generate fabrication files

```bash
make drc        # runs KiCad's DRC; pcb/output/drc_report.json must show 0 violations
make fab        # gerbers + drill -> pcb/output/
```

Behind the scenes:

```bash
docker run --rm -v $(pwd):/work kicad/kicad:10.0 kicad-cli pcb export gerbers ...
```

…using the official KiCad 10 Docker image, no host KiCad install required.

Zip the contents of `pcb/output/` and upload to JLCPCB. The full ordering walkthrough — recommended JLCPCB option settings, when to use lead-free HASL, how to suppress the JLCJLCJLC mark — is in `docs/ordering.md`.

### Other PCB targets

| Target | Output |
|---|---|
| `make svg` | `pcb/output/board.svg` (vector) |
| `make pdf` | `pcb/output/board.pdf` |
| `make pcb-stats` | board statistics report |
| `make assembly` | `pcb/gate_sensor_v2_assembly.kicad_pcb` with 3D models loaded |
| `make assembly-step` | `pcb/output/assembly_3d.step` (3D STEP for mechanical / case design) |
| `make open` | open the bare PCB in KiCad's GUI (requires the AppImage) |
| `make open-assembly` | open the assembly view with 3D models in KiCad's GUI |

---

## 11. Modifying the Design

### Adding a new sensor type

`SENSOR_NAME` and `SENSOR_TYPE` in `config.h` are the only knobs that need to change to spin a different sensor (motion, window, generic door, …) off the same hardware:

```c
#define SENSOR_NAME "MotionHall"     // mesh prefix, also the @target token
#define SENSOR_TYPE "MOTION"          // STATUS frame's Type: field
```

Downstream parsers that classify nodes by sensor type read **`SENSOR_TYPE`**, not the prefix — so adding `WINDOW`, `GARAGE`, `MAIL`, or any other type doesn't require dispatcher changes anywhere else.

If you change `SENSOR_NAME`, **also update the Heltec's owner short name** to match, otherwise CMD targeting will not work — `flash-heltec-meshtastic.sh` line 491 (`--set-owner-short "GATE"`) is the place. The user handbook walks the buyer through this implicitly by saying "the gate sensor is named `GateSensor`/`GATE` on the mesh"; if you've rebranded, update that text too.

### Adding a new CMD verb

The dispatch is a flat `if (strcasecmp(verb, "X") == 0)` chain in `handleCommand()` (`firmware/src/main.cpp:265-363`). Add a branch:

```c
if (strcasecmp(verb, "MY_VERB") == 0) {
    // ... do thing ...
    sendAck("MY_VERB", "OK");
    return;
}
```

Update `docs/firmware.md` and the user/technical handbooks. For verbs that mutate state, persist to EEPROM (use `EEPROM.update` so unchanged bytes don't burn cycles) and reserve an address in [§6](#6-eeprom-layout).

### Bumping `MAX_CODES`

`MAX_CODES` is currently 16. Each registered code costs 4 B in EEPROM (`codes`) + 16 B in `codeNames` + 4 B in RAM (`codeLastEvent`). Going to 32 codes:

- +16 × 4 B = 64 B in EEPROM `codes` (still well within 1 kB)
- +16 × 16 B = 256 B more in EEPROM `codeNames` — pushes the table past byte 587, still fine
- +16 × 4 B = 64 B more RAM (`codeLastEvent` is `unsigned long[]`)

ATmega328P has 2 kB SRAM. Watch the linker map (`.pio/build/nano/firmware.elf.size`) — once you're above ~1.6 kB of statics you'll start getting stack-overflow miscompiles in the snprintf hot paths. The current build sits at ~470 B static + 410 B globals.

### Regenerating the PCB after a footprint change

The PCB is fully generated:

```bash
cd pcb
python3 gate_sensor_pcb_v2.py    # rewrites gate_sensor_v2.kicad_pcb
cd ..
make drc                          # confirm 0 violations
make test-netlist                 # confirm 34/34 checks pass
make fab                          # if you're going to fab
```

`pcb/test_netlist.py` will catch a footprint regression that breaks a net before DRC will. Treat both as required.

### Switching to a different RF receiver

The RXB6 footprint is 8-pin SIP, two 4-pin groups, 25.4 mm gap. If you swap to a different module (e.g. an SRX882 or a CC1101 module), you'll likely need:

1. New footprint in the Python generator
2. Verify pin 4/5 are 5V-tolerant on the new module (or move it onto 3V3 — the Nano's D2 input still reads a 3.3 V high as logic high)
3. If the new module needs SPI rather than a single DATA line, the firmware needs new RX library code; RCSwitch is OOK-only

For OOK 433 MHz alternatives (which most cheap remotes use), a drop-in module that exposes a DATA pin will work with the existing RCSwitch code; only the footprint changes.

---

## 12. Known Issues and Wishlist

- **DM dead-end** (commit `924fb3d`). DMs are PKI-encrypted by Meshtastic 2.5+ and never reach GPIO48; the gate sensor cannot respond to a DM. The user handbook calls this out; any downstream tool that wants to send commands programmatically must rewrite DMs into broadcasts with the `@Gate` prefix prepended before sending.
- **No real temperature**. The STATUS frame's `Temp:0.0C` is a placeholder kept for STATUS-frame format compatibility. ATmega328P's internal temperature sensor is not accurate enough to be worth wiring up; if we ever want a real temperature, an external sensor (DS18B20 on a free Nano pin) is the right path. Currently no plans.
- **Unknown-code threshold is build-time only.** `UNKNOWN_MIN_CODE` (= 1000) is `#define`d in `config.h`. A `THRESHOLD_SET:<n>` verb would be cheap to add and would let operators tune the noise floor at runtime; the only reason it isn't there is that no one has needed it yet.
- **Per-code debounce vs. global**. The current per-code design is correct for "two physical gates triggered close together" but means a single sensor that retransmits its code 4–10 times *and* has a sister-sensor on the same code would re-fire. We have not seen this in practice.
- **Watchdog rollover**. `millis()` rolls over after ~49.7 days; the firmware uses `(now - last) > window` which is correctly wrap-safe via unsigned arithmetic, but no integration test confirms this. If you see exactly-49-day weirdness, this is the suspect.
- **Public-LongFast retail flow vs the developer-PSK flow**. The user handbook describes a unit shipped via `--standalone`; the developer flow flashes a private PSK + BLE-off. We expect the manufacturing line to default to `--standalone` once we have first sales — the only thing standing in the way is sourcing a sane MESH_PSK story for builders who *do* want a private mesh.

---

## 13. References

### Inside this repo

- [`README.md`](../README.md) — project overview and quick start
- [`docs/USER_HANDBOOK.md`](USER_HANDBOOK.md) — buyer-facing handbook
- [`docs/bom.md`](bom.md) — bill of materials and cost
- [`docs/pcb.md`](pcb.md) — PCB design reference (longer-form than [§2](#2-carrier-pcb-v25))
- [`docs/schematic.md`](schematic.md) — full netlist and pin assignments
- [`docs/firmware.md`](firmware.md) — full firmware reference
- [`docs/assembly.md`](assembly.md) — soldering, post-solder checks, bench/field test
- [`docs/learn-sensor.md`](learn-sensor.md) — discovering a new 433 MHz sensor's code over USB
- [`docs/ordering.md`](ordering.md) — JLCPCB order form walkthrough
- [`firmware/src/main.cpp`](../firmware/src/main.cpp) — the firmware itself
- [`firmware/include/config.h`](../firmware/include/config.h) — compile-time constants
- [`scripts/flash-heltec-meshtastic.sh`](../scripts/flash-heltec-meshtastic.sh) — Heltec automation
- [`pcb/gate_sensor_pcb_v2.py`](../pcb/gate_sensor_pcb_v2.py) — PCB generator
- [`pcb/test_netlist.py`](../pcb/test_netlist.py) — 34-check self-test
- [`Makefile`](../Makefile) — top-level build/flash/test targets

### External

- Meshtastic firmware: <https://github.com/meshtastic/firmware>
- Meshtastic CLI: <https://meshtastic.org/docs/software/python/cli/>
- rc-switch library: <https://github.com/sui77/rc-switch>
- KERUI D026 product page: search "KERUI D026 433MHz door sensor"
- Heltec WiFi LoRa 32 V3: <https://heltec.org/project/wifi-lora-32-v3/>
- Waveshare Solar Power Manager D: <https://www.waveshare.com/solar-power-manager-d.htm>
