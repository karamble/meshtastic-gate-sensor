#ifndef CONFIG_H
#define CONFIG_H

// --- 433 MHz Sensor Codes ---
// Codes are a runtime-mutable list (up to MAX_CODES entries) stored in
// EEPROM and managed via CODE_ADD / CODE_REMOVE / CODE_LIST / CODE_CLEAR.
// On a fresh chip (all EEPROM slots 0xFFFFFFFF), the firmware seeds the
// list with DEFAULT_CODE_OPEN so out-of-the-box installs still detect the
// factory-calibrated sensor without any CMDs.
#define DEFAULT_CODE_OPEN 150910   // KERUI D026 open/close code (factory seed; 0 disables seeding)
#define MAX_CODES         16       // number of code slots (each 4 B in EEPROM)

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
#define SERIAL_RX   4   // Nano D4 <- R6 (4k7) <- Heltec GPIO48 (Meshtastic TX)

// --- Timing (milliseconds) ---
// STATUS frame is emitted on boot and every (hbIntervalMin * 60000) ms after.
// 30 min default keeps airtime low while still beating DigiNode CC's 16-min
// NodeOnlineTimeout. The interval is runtime-configurable via HB_INTERVAL
// (see CMD handlers in main.cpp) and persisted in EEPROM.
#define DEFAULT_HB_MIN       30   // default heartbeat interval (minutes)
#define HB_MIN_MIN            1   // minimum HB_INTERVAL value
#define HB_MIN_MAX           60   // maximum HB_INTERVAL value
#define DEFAULT_DEBOUNCE_SEC 10   // default RF debounce window (seconds)
#define DEBOUNCE_MIN_SEC      1   // minimum DEBOUNCE_SET value
#define DEBOUNCE_MAX_SEC     60   // maximum DEBOUNCE_SET value

// --- EEPROM Layout ---
// ATmega328P has 1 KB EEPROM. EEPROM reads as 0xFF when empty.
#define EEPROM_ADDR_BOOTCOUNT 0    // uint16_t (2 B)
#define EEPROM_ADDR_HB_EN     2    // uint8_t: 0=off, 1=on, 0xFF=default(on)
#define EEPROM_ADDR_HB_MIN    3    // uint8_t: heartbeat interval in minutes
#define EEPROM_ADDR_DEBOUNCE  4    // uint8_t: RF debounce seconds
// 5 reserved
#define EEPROM_ADDR_HITS      6    // uint32_t (4 B): cumulative hit counter, persisted
// 10-11 reserved
#define EEPROM_ADDR_CODES     12   // 16 × uint32_t (64 B): code list, 0xFFFFFFFF = empty slot

// --- CMD line parser ---
// CMDs arrive on SoftwareSerial RX (D4) from the Heltec's Meshtastic serial
// module. Format: @<target> <verb>[:<param>[:<param2>...]]
// target is ALL, Gate, or the SENSOR_NAME (case-insensitive).
#define CMD_BUF_SIZE          80  // max line length before forced reset

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
