# Gate Sensor User Handbook

*A wireless door/gate sensor that talks to your Meshtastic network — no WiFi, no cloud, no gateway.*

---

## Table of Contents

1. [What Is This?](#1-what-is-this)
2. [What's in the Box](#2-whats-in-the-box)
3. [First Boot](#3-first-boot)
4. [Out of the Box: The Public Mesh](#4-out-of-the-box-the-public-mesh)
5. [Going Private](#5-going-private)
6. [Pairing Your Sensor](#6-pairing-your-sensor)
7. [Commanding the Sensor Over the Mesh](#7-commanding-the-sensor-over-the-mesh)
8. [What You'll See on the Mesh](#8-what-youll-see-on-the-mesh)
9. [Tuning for Your Environment](#9-tuning-for-your-environment)
10. [Mounting and Power](#10-mounting-and-power)
11. [Region and Regulatory](#11-region-and-regulatory)
12. [Troubleshooting](#12-troubleshooting)
13. [Cheat Sheet](#13-cheat-sheet)
14. [Where to Go Next](#14-where-to-go-next)

---

## 1. What Is This?

The **Gate Sensor** is a small, solar-powered device that turns a cheap 433 MHz door/gate sensor into a message on your Meshtastic LoRa network. When the door opens, the sensor on the door radios a 433 MHz pulse; the gate sensor unit picks it up and broadcasts a short text line into the mesh. Any Meshtastic node — your phone, a tablet, another Heltec on a desk — sees the event arrive within a second or two.

```
KERUI D026 (433 MHz) → gate sensor unit → LoRa mesh → your phone/laptop/other node
```

There is no WiFi, no cloud, no gateway server. The gate sensor talks straight to your Meshtastic devices over LoRa. It runs from a USB-C power supply, from its three 18650 batteries, or — for self-charging outdoor installs — from an optional solar panel.

The device ships ready to use on the **public Meshtastic LongFast channel** — the same default channel every stock Meshtastic node uses out of the box. You can put it to work in five minutes, then switch it to your own private channel whenever you're ready.

![Gate sensor PCB](../newpcb.png)

---

## 2. What's in the Box

A complete kit contains:

- **Gate sensor unit** — Heltec LoRa32 V3 + Arduino Nano + RXB6 433 MHz receiver assembled on a 75 × 66 mm carrier PCB, mounted in a 3D-printed enclosure.
- **KERUI D026 door sensor** — the small magnetic sensor that goes on the door/gate itself. Includes its own coin-cell battery.
- **Waveshare Solar Power Manager D** — a battery board that handles solar charging and provides a stable 5 V to the gate sensor. Holds three 18650 cells.
- **Three 18650 lithium-ion cells** (3000 mAh each) — installed in the Waveshare board. They provide several days of battery autonomy in darkness.
- **Antenna** — 433 MHz whip for the RXB6, plus a LoRa antenna for the Heltec.

If you assembled the unit yourself from the BOM (see [`docs/bom.md`](bom.md)), the same applies — you just sourced the parts separately.

You will also need:

- A **6 V solar panel** (2 W or larger) to keep the batteries charged. **Not included** — source any 6 V panel with a 2 m or longer lead and a connector compatible with your Waveshare board's solar input.
- A second Meshtastic device — typically a phone running the **Meshtastic mobile app** (Android or iOS). Pairing the app over Bluetooth is the easiest way to interact with the gate sensor and also the easiest way to switch to a private channel later.
- A small Phillips screwdriver (J2 power-in screw terminal).

---

## 3. First Boot

1. **Mount the antennas.** Screw the LoRa antenna onto the Heltec's gold SMA jack (the one on top). Connect the 433 MHz antenna to the bulkhead SMA on the case — this one feeds the RXB6 receiver.
2. **Drop the 18650s into the Waveshare board.** Mind the polarity printed on the board.
3. **Power the Waveshare board.** Pick whichever input fits your install:
   - **USB-C** — plug a 5 V USB-C charger into the Waveshare's USB-C port. Easiest for indoor / bench / first-boot use.
   - **Solar** — connect a 6 V solar panel (not included; source separately) to the Waveshare's solar input. Right for outdoor self-charging installs.
   - **Batteries only** — the Waveshare will run from the 18650s alone if you've already charged them; you can power up the gate sensor first and connect USB or solar later.
4. **Wire the Waveshare 5 V output to the gate sensor's J2 screw terminal.** Two wires, marked `5V` and `GND` on the PCB silk. Don't get them backwards — the boards have no reverse-polarity protection.
5. **Flip the power switch on J4.** The Heltec's small OLED screen lights up; you'll see the Meshtastic logo briefly, then the node summary screen.

The first STATUS frame goes out about 8 seconds after power-on. That delay is intentional — it gives the Heltec's Meshtastic firmware time to come up and open its serial module before the Arduino Nano on board starts talking to it.

What you should see arriving in your Meshtastic app within ~10 seconds of power-on:

```
Gate: STATUS: Mode:ARMED Scan:GATE Hits:0 Temp:0.0C Up:00:00:08 Type:GATESENSOR Boot:1
```

If you see that, the gate sensor is alive and on the mesh. The fields are explained in [§8](#8-what-youll-see-on-the-mesh); for now, just confirm the message arrives.

---

## 4. Out of the Box: The Public Mesh

The unit ships joined to the **default Meshtastic public channel**. This channel is called **LongFast**, has the well-known PSK `AQ==`, and uses your region's default LoRa settings (EU_868 unless we sold you a unit configured for a different region).

What this means in practice:

- Pair any stock Meshtastic node — phone with the Meshtastic app, a Heltec on your desk, an existing node you already use — to the **LongFast** channel and the same region as your gate sensor. You will see a node appear in the app called **GateSensor** (short name `GATE`).
- Any STATUS heartbeat or TRIGGERED event the gate sensor emits is visible on that channel.
- You can send commands to the gate sensor (see [§7](#7-commanding-the-sensor-over-the-mesh)) over that channel.

Quick smoke test:

1. Fire up the Meshtastic app on your phone, pair it over Bluetooth to a Meshtastic device tuned to LongFast (or use the gate sensor itself — see "Bluetooth pairing" below).
2. Walk over to the door the KERUI D026 is on and open it.
3. Within ~1 second, a message arrives on the LongFast channel:

   ```
   Gate: TRIGGERED:150910 unnamed
   ```

   `150910` is the factory-calibrated KERUI D026 code. The word `unnamed` is exactly what it looks like: you haven't given the sensor a friendly name yet. We fix that in [§7](#7-commanding-the-sensor-over-the-mesh).

### Bluetooth pairing the gate sensor's Heltec to your phone

Because the unit ships with Bluetooth on, you can pair the gate sensor's Heltec directly to the Meshtastic mobile app:

1. Open the Meshtastic app, tap **+** → **Add a device** → **Bluetooth**.
2. Pick **GateSensor** (or `GATE` short-name) from the list.
3. Confirm the pairing PIN shown on the Heltec's OLED.

You now own the gate sensor's Heltec from the app. From here you can read its status, change channel settings, and — most importantly — generate a private PSK ([§5](#5-going-private)).

> **Heads-up — public-channel privacy.** While you're on the LongFast channel, *anyone* within LoRa range running a stock Meshtastic device on LongFast will see your gate events. That's fine for testing. It is not what you want for the long term. Move to a private PSK as soon as you're comfortable with the device.

---

## 5. Going Private

A private channel is just a public channel with a different PSK (pre-shared key). Every Meshtastic node that knows the same PSK can read messages on that channel; nodes without it see only encrypted noise.

We recommend using the Meshtastic mobile app for this — it's the lowest-friction path.

### From the mobile app (recommended)

1. Pair the gate sensor's Heltec to the app over Bluetooth (see [§4](#4-out-of-the-box-the-public-mesh)).
2. **Channels → Primary**. The primary channel is the default broadcast channel — the one the gate sensor emits its events on.
3. Tap **Generate New** (or **Randomize**) on the PSK field. Confirm. The app sends the new PSK to the gate sensor and reboots its radio.
4. **Share** the same channel — use the app's QR code share. Any other Meshtastic device that scans the QR (or imports the channel URL) joins the same private mesh.
5. Apply the QR/URL to every Meshtastic node you want on this private mesh — your phone, a tablet, another base station.

That's it. The gate sensor still sends `Gate: TRIGGERED:…` exactly as before, but now only nodes carrying your PSK can read the broadcast.

### From a USB-tethered laptop

If you'd rather use the command line:

```bash
# Plug the gate sensor's Heltec USB-C into your laptop. Then:
meshtastic --port /dev/ttyUSB0 --ch-set psk random --ch-index 0 --info
```

The `--info` at the end prints back the new channel config including the new PSK. Copy the channel URL (the line beginning with `https://meshtastic.org/e/#…`) and import it into every other node you own.

### Verifying you're really private

Ask the device for its current channel info:

```bash
meshtastic --port /dev/ttyUSB0 --info
```

Find the `psk:` line. If it reads `AQ==` you are still on the public channel. Anything else is private.

Or in the mobile app: **Channels → Primary** — the PSK field shows a 32-byte base64 string (much longer than `AQ==`).

> **Don't lose your PSK.** If your only copy of the private PSK is on a phone that breaks, you're locked out of your own mesh and will need to USB-flash the gate sensor and every other node. Save the channel URL/QR somewhere safe.

---

## 6. Pairing Your Sensor

The unit ships with the **factory KERUI D026 code** (decimal `150910`) already registered. If your kit included a KERUI D026 from us, no pairing is required — just open the door and the mesh shows `Gate: TRIGGERED:150910 unnamed`.

If you want to:

- **Give the existing sensor a friendly name** — see [§7, "Naming a sensor"](#naming-a-sensor).
- **Add another KERUI D026** (or any other 433 MHz door sensor) as a second sensor — see "Learning a new sensor" below.
- **Use a different 433 MHz sensor entirely** — also "Learning a new sensor."

### Learning a new sensor

The gate sensor unit listens for any 433 MHz code, not just the factory one. To teach it about a new sensor:

1. **Be within ~10–30 m of the gate sensor** with the new sensor in your hand.
2. **Trigger the new sensor 4–5 times** over a few seconds. (For a KERUI D026, that's open-close-open-close-open.)
3. Watch your Meshtastic app — any unknown 433 MHz code at or above the noise floor shows up like this:

   ```
   Gate: TRIGGERED:8675309 unknown
   ```

   The decimal number is your sensor's code. The word `unknown` is the placeholder name the firmware uses for codes it has never seen registered.

4. **Register the code** with a friendly name:

   ```
   @Gate CODE_ADD:8675309:backgate
   ```

   The reply lands on the same mesh channel: `Gate: CODE_ACK:OK`. From now on, triggers from that sensor read `Gate: TRIGGERED:8675309 backgate`.

You can register up to **16 distinct codes**. Names can be 1–15 characters of letters, digits, `_`, or `-`. Spaces, colons, and `@` are not allowed in names.

### Naming a sensor

The factory KERUI ships unnamed because we don't know which door it'll go on:

```
@Gate CODE_ADD:150910:frontdoor
```

Reply: `Gate: CODE_ACK:UPDATED` (since the code was already registered, the gate sensor just updated its name).

You can re-name a sensor later by re-issuing `CODE_ADD` with the same code and a different name.

> **Why some codes don't show up.** Random radio noise on 433 MHz produces stray decoded numbers below 1000. The firmware suppresses those on the mesh (you don't want every microwave oven nearby to flood your mesh) but any code 1000 or higher gets broadcast. If your sensor has a very low code, register it explicitly with `CODE_ADD` from a USB connection and it will start firing — see the technical handbook for that path.

---

## 7. Commanding the Sensor Over the Mesh

You talk to the gate sensor by sending plain-text commands on the **same broadcast channel** the gate sensor reports on. The format is:

```
@Gate VERB[:param[:param2]]
```

The `@Gate` prefix tells the gate sensor "this is for me." (You can use `@ALL` instead — the gate sensor will respond to that too.) The reply arrives a moment later on the same channel:

```
Gate: VERB_ACK:OK
```

> **Important — broadcasts only.** The gate sensor processes commands sent on the **broadcast channel only**. **Direct messages are a structural dead-end** and are silently dropped before the gate sensor's firmware ever sees them. This is a deliberate constraint in the underlying Meshtastic serial-module design — there is no way around it short of a hardware change. Always send commands on the channel, never as a DM.

Both sides — the command you send and the ACK you get back — are visible to anyone else on the channel (which, after [§5](#5-going-private), is just you and your own nodes).

### Sensor codes (the registry)

Adding, removing, listing, and clearing the 433 MHz codes the gate sensor will treat as door events:

| Command | Effect | Reply |
|---|---|---|
| `@Gate CODE_LIST` | Show all registered codes and their names. | `Gate: CODES:150910=frontdoor,8675309=backgate` (or `CODES:NONE` if empty) |
| `@Gate CODE_ADD:<code>:<name>` | Register a new code (max 16 codes). Name is optional but recommended; 1–15 chars of letters/digits/`_`/`-`. | `Gate: CODE_ACK:OK` (added) / `UPDATED` (existing code, name changed) / `EXISTS` (already registered with same name) / `FULL` (all 16 slots used) / `ERROR` (bad code or bad name) |
| `@Gate CODE_REMOVE:<code>` | Unregister a code. | `Gate: CODE_ACK:OK` / `NOT_FOUND` / `ERROR` |
| `@Gate CODE_CLEAR` | Wipe the entire registry. **Destructive.** | `Gate: CODE_ACK:OK` |

All registry changes are persisted to non-volatile EEPROM and survive reboots and power loss.

### Status and runtime tuning

| Command | Effect | Reply |
|---|---|---|
| `@Gate STATUS` | Force an immediate STATUS heartbeat right now. | (the STATUS frame itself — see [§8](#8-what-youll-see-on-the-mesh)) |
| `@Gate HB_ON` | Turn periodic STATUS heartbeats back on. | `Gate: HB_ACK:OK` |
| `@Gate HB_OFF` | Stop periodic STATUS heartbeats. (Boot STATUS and on-demand STATUS still fire.) | `Gate: HB_ACK:OK` |
| `@Gate HB_INTERVAL:<minutes>` | Change the heartbeat interval. Range: 1–60 minutes. Default: 30. | `Gate: HB_ACK:OK` / `ERROR` |
| `@Gate DEBOUNCE_SET:<seconds>` | Change the RF debounce window. Range: 1–60 seconds. Default: 10. | `Gate: DEBOUNCE_ACK:OK` / `ERROR` |
| `@Gate HITS_RESET` | Zero out the lifetime trigger counter shown in STATUS. | `Gate: HITS_RESET_ACK:OK` |
| `@Gate REBOOT` | Watchdog-reboot the gate sensor's Nano. The Heltec is unaffected. New STATUS arrives ~10 seconds later with `Boot:` incremented. | `Gate: REBOOT_ACK:OK` (then a short silence, then a new STATUS) |

All settings are persisted to EEPROM. They survive reboots and battery swaps.

### Examples

```
@Gate STATUS                   → Gate: STATUS: Mode:ARMED Scan:GATE Hits:42 …
@Gate CODE_LIST                → Gate: CODES:150910=frontdoor
@Gate CODE_ADD:8675309:back    → Gate: CODE_ACK:OK
@Gate CODE_ADD:8675309:back    → Gate: CODE_ACK:EXISTS
@Gate CODE_ADD:8675309:rear    → Gate: CODE_ACK:UPDATED
@Gate CODE_REMOVE:8675309      → Gate: CODE_ACK:OK
@Gate CODE_REMOVE:404          → Gate: CODE_ACK:NOT_FOUND
@Gate HB_INTERVAL:5            → Gate: HB_ACK:OK
@Gate DEBOUNCE_SET:30          → Gate: DEBOUNCE_ACK:OK
@Gate HITS_RESET               → Gate: HITS_RESET_ACK:OK
@Gate REBOOT                   → Gate: REBOOT_ACK:OK (then a fresh STATUS)
```

---

## 8. What You'll See on the Mesh

The gate sensor emits three kinds of frames. All three are plain text broadcasts on the channel.

### STATUS heartbeat

```
Gate: STATUS: Mode:ARMED Scan:GATE Hits:42 Temp:0.0C Up:03:17:55 Type:GATESENSOR Boot:7
```

| Field | Meaning |
|---|---|
| `Gate:` | Instance prefix. Always the same; lets you spot the gate sensor's frames in a busy channel. |
| `STATUS:` | Frame type. |
| `Mode:ARMED` | Always `ARMED` in this firmware. Reserved for a future DISARMED state. |
| `Scan:GATE` | What kind of RF traffic this sensor is watching for. |
| `Hits:42` | Lifetime count of door triggers since the last `HITS_RESET` (or since the device was made). |
| `Temp:0.0C` | Placeholder. The gate sensor has no temperature probe; the field exists for compatibility with the Meshtastic node-status format. |
| `Up:03:17:55` | Uptime since the last reboot, as `HH:MM:SS`. |
| `Type:GATESENSOR` | Sensor class. Other devices in the same product family may report `MOTION`, `DOOR`, etc. |
| `Boot:7` | Number of times the gate sensor has booted in its life. Increments on every power-on or `REBOOT`. |

A STATUS arrives:

- **Once at boot**, ~8 seconds after power-on.
- **Periodically** (every 30 minutes by default — adjustable with `HB_INTERVAL`).
- **Whenever you ask** for one with `@Gate STATUS`.

You can suppress periodic STATUS broadcasts entirely with `@Gate HB_OFF`. Boot STATUS and on-demand STATUS still fire.

### TRIGGERED event

```
Gate: TRIGGERED:150910 frontdoor
```

One of these is emitted every time the door is opened (after the debounce window — see [§9](#9-tuning-for-your-environment)). The number is the 433 MHz code; the trailing word is the name you assigned. Three special trailing words:

- A **registered name** you set with `CODE_ADD` (`frontdoor`, `back`, `garage`).
- `unnamed` — the code is registered but you never gave it a name.
- `unknown` — the code is not in the registry but is loud enough to be a real transmitter (≥ 1000), so the firmware reports it anyway. This is your hook for [learning a new sensor](#6-pairing-your-sensor).

### ACKs

A reply to a command, e.g. `Gate: CODE_ACK:OK` or `Gate: HB_ACK:ERROR`. Always follows the form:

```
Gate: <VERB>_ACK:<status>
```

`<status>` is `OK`, `ERROR`, or a verb-specific value (`UPDATED`, `EXISTS`, `FULL`, `NOT_FOUND`). The full table is in [§7](#7-commanding-the-sensor-over-the-mesh).

---

## 9. Tuning for Your Environment

Two settings are worth thinking about. Both are runtime-changeable; both persist across reboots.

### Heartbeat interval (`HB_INTERVAL`)

How often the gate sensor sends a STATUS frame "I'm still alive." Default: 30 minutes.

- **Lower** (1–10 min): you find out faster if the gate sensor goes offline. Trade-off: more LoRa airtime, slightly more power draw.
- **Higher** (30–60 min): less airtime. Trade-off: longer worst-case "is it still up?" gap.

```
@Gate HB_INTERVAL:5     → STATUS every 5 minutes
@Gate HB_INTERVAL:60    → STATUS once an hour
@Gate HB_OFF            → no periodic STATUS (boot + on-demand only)
```

### Debounce window (`DEBOUNCE_SET`)

Cheap 433 MHz door sensors are designed to be loud and unreliable: they retransmit the same code 4–10 times in a quick burst whenever the door opens, in case some of the bursts are lost. The gate sensor's job is to collapse that burst into **one** message on your mesh.

The debounce window says "after I see code X, ignore further copies of X for the next *N* seconds." Default: 10 seconds.

- If you see **multiple TRIGGERED messages for one open**, raise the window: `@Gate DEBOUNCE_SET:30`.
- If you have a sensor that legitimately fires often (e.g. a tripwire that pulses every couple of seconds), lower it: `@Gate DEBOUNCE_SET:1`. You probably want a higher value, not lower, in nearly all real installs.

The debounce is **per-code**, so two different sensors firing at the same time both get reported.

---

## 10. Mounting and Power

### The gate sensor unit

The gate sensor unit lives in a 3D-printed enclosure. **The printed case is not weatherproof — mount the unit indoors.** If you need to install it outdoors, swap the printed case for an IP-rated junction box (a 150 × 100 × 70 mm IP65 box is listed in the BOM as the recommended option).

Place it within **10–30 m line-of-sight of the door sensor**. 433 MHz penetrates plaster and wood reasonably well, but is mediocre through brick, metal, and reinforced concrete. If your gate is on the far side of a brick wall, expect to be on the lower end of that range.

The LoRa antenna (Heltec) and the 433 MHz antenna (RXB6) should both have clear airspace. They do not interfere with each other in normal use.

### The KERUI D026

This goes on the door itself. Two pieces:

1. The transmitter body — usually screwed to the door frame.
2. The magnet — screwed to the door, lined up with the transmitter so the gap is < 15 mm when the door is closed.

When the magnet moves away (door opens), the KERUI fires its 433 MHz code. The same code fires on close — the gate sensor cannot tell open from close on this model. If you need open-vs-close distinction, you would need a sensor whose firmware emits two distinct codes; we don't currently ship one.

### Power: USB-C, batteries, or optional solar

The Waveshare Solar Power Manager D charges and balances the three 18650 cells. Power can come from any of:

- **USB-C** plugged into the Waveshare board — the easiest option for indoor or bench use.
- **The 18650 cells alone** — once charged, they keep the unit running on their own.
- **A 6 V solar panel (optional, not included)** wired into the Waveshare's solar input — for outdoor self-charging installs.

Approximate budget at our default settings:

| Quantity | Value |
|---|---|
| Total system draw | ~105 mA at 5 V |
| Battery capacity | 3× 3000 mAh in parallel = ~9000 mAh @ 3.7 V (~33 Wh) |
| Battery-only runtime in total darkness | ~85 hours |
| Solar input (clear day, panel directly facing sun, midday) | ~330 mA at 6 V (well above draw) |

If you choose to add a solar panel, position it with no shade between ~10:00 and ~14:00 local solar time. South-facing in the Northern Hemisphere, north-facing in the Southern. Even a thin tree branch crossing the panel halves output. In winter at high latitudes, plan for the panel to be aimed steeply, kept clean, and ideally not shaded — or step up to a larger panel.

---

## 11. Region and Regulatory

Your unit ships configured for **EU_868** — the European LoRa band — by default. If we sold you a unit for a different region (US, AS_923, ANZ, …) it'll already be set correctly.

If you need to change region (e.g. you're moving the unit between regions, or you bought a generic unit and need to set region for the first time), the easiest path is the Meshtastic mobile app once you've Bluetooth-paired it: **Radio Configuration → LoRa → Region**. Choose the right region for where the device is *physically located* and tap **Save**. The Heltec reboots and rejoins the mesh with the new region.

> **The two radios use different bands.** The 433 MHz door-sensor side is the 433 MHz ISM band, which is license-free across most of the world for low-power devices and is independent of the LoRa region setting. The LoRa side is what the region setting controls. Don't confuse the two.

If you're outside the EU and want to verify regional compliance for the 433 MHz side, the KERUI D026 is sold worldwide; in nearly all jurisdictions it sits in a license-free ISM allocation.

---

## 12. Troubleshooting

### No STATUS frame after power-on

- Check the OLED on the Heltec. If it's dark, the unit isn't powered: verify J4 (power switch) is on, the polarity on J2 is right (`5V` to `5V`, `GND` to `GND`), and the Waveshare's output LEDs are lit.
- The first STATUS comes ~8 seconds after power-on, not immediately. Wait a full 30 seconds before declaring it broken.
- Make sure the Meshtastic node you're watching from is on the **same channel** (LongFast for fresh units, your private channel afterwards) and the **same region**.

### No TRIGGERED message when I open the door

- Check the door sensor's battery. Most "non-working" KERUIs have a dead battery shipped from the factory.
- Trigger the sensor 5–6 times in a row to make sure you're not just hitting the debounce window.
- Watch the mesh while you trigger. If you see `Gate: TRIGGERED:<somenumber> unknown`, your sensor's code isn't registered — `CODE_ADD` it (see [§6](#6-pairing-your-sensor)). If you see *nothing*, you're either out of 433 MHz range, the antenna is disconnected, or the receiver is dead — see "Range and antennas" below.

### Multiple TRIGGERED messages for one door open

The debounce window is too short. Raise it: `@Gate DEBOUNCE_SET:30`.

### A node I expected to see the gate sensor on doesn't

- Same channel? Same region? Same PSK? After [§5](#5-going-private), every node needs the new PSK.
- Distance: LoRa is good but not magic. Concrete buildings, metal roofs, dense foliage all attenuate the signal. If you're at the edge of range, set the gate sensor's `HB_INTERVAL` to 5 minutes for a while and walk around to find dead spots.

### I changed the PSK and now I can't reach the gate sensor

This usually means one node got the new PSK and the others didn't. Pick the device with the new PSK, share its channel URL/QR to every other node. If you've fully lost contact with the gate sensor, USB-tether its Heltec to a laptop and run:

```bash
meshtastic --port /dev/ttyUSB0 --info
```

— that always works regardless of channel state. From there you can re-set the PSK or factory-reset.

### Range and antennas

Both antennas should be hand-tight on their SMA connectors. If you ever transport the unit, screw them off first — antennas under transport vibration can damage their connectors.

The 433 MHz whip should be roughly vertical. The LoRa antenna also wants to be vertical for omnidirectional coverage. Mount the case so neither antenna is right next to a metal surface.

### "I see numbers in the mesh I don't recognize"

If you see an occasional `Gate: TRIGGERED:<code> unknown` and the door wasn't opened, the gate sensor caught a stray 433 MHz transmission from somewhere — a neighbour's car remote, a weather station, a cheap toy. Ignore it; it'll probably never recur. If it recurs reliably and isn't yours, raise the debounce window so it can't flood you, or live with it as background.

### I want to start over

`@Gate CODE_CLEAR` wipes the 433 MHz code registry. To wipe all settings (including the heartbeat and debounce values), the path is to USB-tether and run a clean re-flash — see the technical handbook for that procedure.

---

## 13. Cheat Sheet

### Most-used commands

```
@Gate STATUS                          force a status frame
@Gate CODE_LIST                       show all registered sensors
@Gate CODE_ADD:<code>:<name>          register a sensor
@Gate CODE_REMOVE:<code>              unregister a sensor
@Gate HB_INTERVAL:<minutes>           change heartbeat (1–60)
@Gate DEBOUNCE_SET:<seconds>          change debounce (1–60)
@Gate HITS_RESET                      zero the trigger counter
@Gate REBOOT                          reboot the Nano (~10 s)
```

### Frame shapes

```
Gate: STATUS: Mode:ARMED Scan:GATE Hits:N Temp:0.0C Up:HH:MM:SS Type:GATESENSOR Boot:K
Gate: TRIGGERED:<code> <name>
Gate: <VERB>_ACK:<status>
```

### Defaults

| Setting | Default |
|---|---|
| Heartbeat interval | 30 min |
| Debounce window | 10 s |
| Max registered codes | 16 |
| Channel (out of the box) | LongFast (public) |
| Region (out of the box) | EU_868 (or as ordered) |
| Owner long name | GateSensor |
| Owner short name | GATE |

### Limits

- Code must be a positive decimal between 1 and 16,777,215 (24-bit).
- Names are 1–15 characters, letters / digits / `_` / `-` only. No spaces, colons, or `@`.
- Up to 16 codes registered at any time.

---

## 14. Where to Go Next

- **[Technical Handbook](TECHNICAL_HANDBOOK.md)** — for builders, modifiers, and the technically curious. Covers the firmware architecture, the PCB, EEPROM layout, the wire format of the CMD protocol, build instructions, and how to extend the firmware (new sensor types, new commands, more codes).
- **[BOM](bom.md)** — full bill of materials and rough costs.
- **[Assembly](assembly.md)** — if you have a kit to solder.

If something in this handbook is wrong, unclear, or out of date, please open an issue on the project repository — the gate sensor is open hardware and open firmware, and patches are welcome.
