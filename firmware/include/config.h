#ifndef CONFIG_H
#define CONFIG_H

// --- 433 MHz Sensor Codes ---
// Run the learning sketch (Phase 2) to find your sensor's codes.
// Replace these with the decimal values from rc-switch output.
#define CODE_OPEN    150910  // KERUI D026 — transmits same code on open and close
#define CODE_CLOSED  0       // disabled — sensor does not emit reliable close code

// --- Sensor Identity ---
// SENSOR_NAME is the instance prefix used in every outbound mesh frame
// ("Gate: STATUS: ...", "Gate: TRIGGERED"). Mirrors AntiHunter's "AH34:" pattern
// so parsers that expect "<id>:" at the start of a STATUS frame work cleanly.
#define SENSOR_NAME "Gate"

// SENSOR_TYPE is the uppercase sensor-class identifier carried in the STATUS
// frame's Type: field. DigiNode CC uses this (not the prefix) to classify the
// node, so future sensor builds can swap "GATESENSOR" for "MOTION", "DOOR",
// "WINDOW", etc. without touching the dispatcher.
#define SENSOR_TYPE "GATESENSOR"

// --- Pin Assignments ---
#define RF_PIN      2   // RXB6 DATA -> Nano D2 (INT0 for RCSwitch)
#define SERIAL_TX   3   // Nano D3 -> 2.2k/3.3k divider -> Heltec GPIO47
#define SERIAL_RX   4   // Unused (Heltec TX not connected). Placeholder for SoftwareSerial.

// --- Timing (milliseconds) ---
// STATUS frame is emitted on boot and every STATUS_MS afterwards. 30 min keeps
// airtime low while still beating DigiNode CC's 16-min NodeOnlineTimeout.
#define STATUS_MS      1800000UL  // 30 min STATUS heartbeat
#define DEBOUNCE_MS    10000      // 10s — absorb KERUI retransmit bursts, one event per opening

// --- EEPROM Layout ---
// Persistent boot counter so the STATUS frame can report how many times the
// Nano has booted across its lifetime. ATmega328P has 1 KB EEPROM; we use
// bytes 0-1 as a uint16_t.
#define EEPROM_ADDR_BOOTCOUNT 0

// --- UART Baud Rate ---
#define MESH_BAUD 9600  // Meshtastic serial module baud

// --- Meshtastic Serial Config ---
// Heltec V3 serial module must use GPIO47 for RX (not GPIO44, which
// conflicts with CP2102 USB-UART). Set via:
//   meshtastic --set serial.enabled true
//   meshtastic --set serial.rxd 47
//   meshtastic --set serial.baud BAUD_9600
//   meshtastic --set serial.mode TEXTMSG

#endif
