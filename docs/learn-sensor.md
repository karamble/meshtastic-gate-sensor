# Learning a New 433 MHz Door Sensor

The firmware needs the decimal code your 433 MHz door sensor transmits on open events. The `make learn-sensor` target helps you discover it without flashing a separate learning sketch — the production firmware already logs every decoded RF code to USB serial.

## How it works

`firmware/src/main.cpp` routes every RF hit through two paths:

- If the code matches `CODE_OPEN` (from `firmware/include/config.h`) → sends `Gate: TRIGGERED` over mesh **and** echoes the line on USB serial.
- Otherwise → prints `RF unknown: <decimal>` on USB serial only (not forwarded to mesh).

When you swap in a new sensor whose code doesn't match `CODE_OPEN`, every one of its transmissions surfaces as an `RF unknown:` line with the decimal value.

## Procedure

1. Flash the current firmware once: `make upload`.
2. Open the learning monitor: `make learn-sensor`. The target streams the Nano's USB serial at 115200 baud.
3. Trigger the sensor (open/close the door) several times. You'll see bursts like:

        RF unknown: 150910
        RF unknown: 150910
        RF unknown: 150910

   Common 433 MHz EV1527 / PT2260-style sensors retransmit the same code 4–10 times per trigger for reliability, so the same decimal should repeat. Ignore one-off values — those are RF noise or unrelated devices in range (weather stations, car remotes, etc.).

4. Once you've confirmed a stable decimal, copy it into `firmware/include/config.h`:

        #define CODE_OPEN    150910   // your learned value

5. Re-flash: `make upload`. From this point on the sensor fires `Gate: TRIGGERED` on the mesh instead of `RF unknown:` on USB.

## Notes

- **Many sensors emit the same code on open and close** (KERUI D026 does). `CODE_CLOSED` is defined in `config.h` but left at `0` (disabled) for this reason. If yours emits a distinct close code, set `CODE_CLOSED` to that value.
- `DEBOUNCE_MS` (10 s by default) collapses retransmit bursts into a single mesh event. During learning, the debounce doesn't affect USB output — every decoded code is printed.
- Press `Ctrl+C` (or `Ctrl+]` in `pio device monitor`) to exit the learning monitor.
