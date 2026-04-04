#ifndef CONFIG_H
#define CONFIG_H

// --- 433 MHz Sensor Codes ---
// Run the learning sketch (Phase 2) to find your sensor's codes.
// Replace these with the decimal values from rc-switch output.
#define CODE_OPEN    0  // TODO: replace with learned OPEN code
#define CODE_CLOSED  0  // TODO: replace with learned CLOSED code

// --- Sensor Identity ---
#define SENSOR_NAME "Gate"

// --- Pin Assignments ---
#define RF_PIN      2   // RXB6 DATA -> Nano D2 (INT0 for RCSwitch)
#define SERIAL_TX   3   // Nano D3 -> 2.2k/3.3k divider -> Heltec GPIO47
#define SERIAL_RX   4   // Unused (Heltec TX not connected). Placeholder for SoftwareSerial.

// --- Timing (milliseconds) ---
#define HEARTBEAT_MS   300000  // 5 min heartbeat
#define DEBOUNCE_MS    200     // RF retransmission debounce

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
