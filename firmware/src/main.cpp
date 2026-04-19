#include <Arduino.h>
#include <EEPROM.h>
#include <RCSwitch.h>
#include <SoftwareSerial.h>
#include <avr/wdt.h>
#include <string.h>
#include <stdlib.h>
#include "config.h"

RCSwitch rf = RCSwitch();
SoftwareSerial meshSerial(SERIAL_RX, SERIAL_TX);

unsigned long lastStatus = 0;
unsigned long lastRfEvent = 0;
uint16_t bootCount = 0;
uint32_t hitCount = 0;                    // persisted in EEPROM

// Runtime config (loaded from EEPROM on boot, mutated by CMDs)
bool    hbEnabled     = true;
uint8_t hbIntervalMin = DEFAULT_HB_MIN;
uint8_t debounceSec   = DEFAULT_DEBOUNCE_SEC;

// Dynamic 433 MHz code list. Empty slot sentinel = 0xFFFFFFFF (fresh EEPROM).
uint32_t codes[MAX_CODES];
uint8_t  codesCount = 0;
#define CODE_EMPTY 0xFFFFFFFFUL

// Inbound CMD line buffer
char    cmdBuf[CMD_BUF_SIZE];
uint8_t cmdLen = 0;

void sendMessage(const char* msg) {
    meshSerial.println(msg);
    Serial.println(msg);  // Debug echo
}

void sendEvent(const char* state, uint32_t code) {
    char buf[64];
    snprintf(buf, sizeof(buf), "%s: %s:%lu", SENSOR_NAME, state, (unsigned long)code);
    sendMessage(buf);
}

void sendStatus() {
    unsigned long upSec = millis() / 1000UL;
    unsigned int h = (unsigned int)(upSec / 3600UL);
    unsigned int m = (unsigned int)((upSec / 60UL) % 60UL);
    unsigned int s = (unsigned int)(upSec % 60UL);

    char buf[128];
    snprintf(buf, sizeof(buf),
        "%s: STATUS: Mode:ARMED Scan:GATE Hits:%lu Temp:0.0C "
        "Up:%02u:%02u:%02u Type:%s Boot:%u",
        SENSOR_NAME,
        (unsigned long)hitCount,
        h, m, s,
        SENSOR_TYPE,
        (unsigned)bootCount);
    sendMessage(buf);
}

// Uniform ACK emitter: "<SENSOR_NAME>: <VERB>_ACK:<status>"
void sendAck(const char* verb, const char* status) {
    char buf[64];
    snprintf(buf, sizeof(buf), "%s: %s_ACK:%s", SENSOR_NAME, verb, status);
    sendMessage(buf);
}

// ── EEPROM helpers ─────────────────────────────────────

void saveHitCount() {
    EEPROM.put(EEPROM_ADDR_HITS, hitCount);
}

void saveCodes() {
    for (uint8_t i = 0; i < MAX_CODES; i++) {
        EEPROM.put(EEPROM_ADDR_CODES + i * 4, codes[i]);
    }
}

void loadCodes() {
    codesCount = 0;
    for (uint8_t i = 0; i < MAX_CODES; i++) {
        EEPROM.get(EEPROM_ADDR_CODES + i * 4, codes[i]);
        if (codes[i] != CODE_EMPTY) codesCount++;
    }
    // Seed fresh chip with the factory-calibrated code so out-of-the-box
    // installs still work without a CODE_ADD from the operator.
    if (codesCount == 0 && DEFAULT_CODE_OPEN != 0) {
        codes[0] = DEFAULT_CODE_OPEN;
        codesCount = 1;
        saveCodes();
    }
}

// ── Code-list operations ──────────────────────────────

bool codeKnown(uint32_t c) {
    for (uint8_t i = 0; i < MAX_CODES; i++) {
        if (codes[i] == c) return true;
    }
    return false;
}

enum CodeAddResult { CODE_ADDED, CODE_EXISTS, CODE_FULL };

CodeAddResult codeAddSlot(uint32_t c) {
    if (codeKnown(c)) return CODE_EXISTS;
    for (uint8_t i = 0; i < MAX_CODES; i++) {
        if (codes[i] == CODE_EMPTY) {
            codes[i] = c;
            codesCount++;
            saveCodes();
            return CODE_ADDED;
        }
    }
    return CODE_FULL;
}

bool codeRemove(uint32_t c) {
    for (uint8_t i = 0; i < MAX_CODES; i++) {
        if (codes[i] == c) {
            codes[i] = CODE_EMPTY;
            if (codesCount > 0) codesCount--;
            saveCodes();
            return true;
        }
    }
    return false;
}

void codeClearAll() {
    for (uint8_t i = 0; i < MAX_CODES; i++) codes[i] = CODE_EMPTY;
    codesCount = 0;
    saveCodes();
}

void sendCodeList() {
    // 16 codes × 8 digits max + 15 commas + "Gate: CODES:" prefix < 180 bytes
    char buf[192];
    int off = snprintf(buf, sizeof(buf), "%s: CODES:", SENSOR_NAME);
    if (codesCount == 0) {
        snprintf(buf + off, sizeof(buf) - off, "NONE");
    } else {
        bool first = true;
        for (uint8_t i = 0; i < MAX_CODES; i++) {
            if (codes[i] == CODE_EMPTY) continue;
            if (off >= (int)(sizeof(buf) - 12)) break;  // leave tail margin
            off += snprintf(buf + off, sizeof(buf) - off, "%s%lu",
                            first ? "" : ",", (unsigned long)codes[i]);
            first = false;
        }
    }
    sendMessage(buf);
}

// ── REBOOT via watchdog ───────────────────────────────

static void doReboot() {
    sendAck("REBOOT", "OK");
    meshSerial.flush();
    Serial.flush();
    delay(100);                 // let UART bytes clear
    wdt_enable(WDTO_15MS);
    while (1) {}
}

// ── CMD parser ────────────────────────────────────────

static bool targetMatches(const char* target) {
    if (strcasecmp(target, "ALL") == 0) return true;
    if (strcasecmp(target, SENSOR_NAME) == 0) return true;
    return false;
}

static void handleCommand(const char* target, const char* verb, const char* param) {
    if (!targetMatches(target)) return;

    // STATUS: no ACK, the STATUS frame itself is the reply.
    if (strcasecmp(verb, "STATUS") == 0) {
        sendStatus();
        return;
    }

    // Heartbeat control
    if (strcasecmp(verb, "HB_ON") == 0) {
        hbEnabled = true;
        EEPROM.update(EEPROM_ADDR_HB_EN, 1);
        lastStatus = millis();
        sendAck("HB", "OK");
        return;
    }
    if (strcasecmp(verb, "HB_OFF") == 0) {
        hbEnabled = false;
        EEPROM.update(EEPROM_ADDR_HB_EN, 0);
        sendAck("HB", "OK");
        return;
    }
    if (strcasecmp(verb, "HB_INTERVAL") == 0) {
        if (param == NULL || *param == '\0') { sendAck("HB", "ERROR"); return; }
        int m = atoi(param);
        if (m < HB_MIN_MIN || m > HB_MIN_MAX) { sendAck("HB", "ERROR"); return; }
        hbIntervalMin = (uint8_t)m;
        EEPROM.update(EEPROM_ADDR_HB_MIN, hbIntervalMin);
        lastStatus = millis();
        sendAck("HB", "OK");
        return;
    }

    // System control
    if (strcasecmp(verb, "REBOOT") == 0) {
        doReboot();  // does not return
        return;
    }

    // Gate-specific
    if (strcasecmp(verb, "HITS_RESET") == 0) {
        hitCount = 0;
        saveHitCount();
        sendAck("HITS_RESET", "OK");
        return;
    }
    if (strcasecmp(verb, "DEBOUNCE_SET") == 0) {
        if (param == NULL || *param == '\0') { sendAck("DEBOUNCE", "ERROR"); return; }
        int s = atoi(param);
        if (s < DEBOUNCE_MIN_SEC || s > DEBOUNCE_MAX_SEC) { sendAck("DEBOUNCE", "ERROR"); return; }
        debounceSec = (uint8_t)s;
        EEPROM.update(EEPROM_ADDR_DEBOUNCE, debounceSec);
        sendAck("DEBOUNCE", "OK");
        return;
    }

    // RF code registry
    if (strcasecmp(verb, "CODE_ADD") == 0) {
        if (param == NULL || *param == '\0') { sendAck("CODE", "ERROR"); return; }
        unsigned long c = strtoul(param, NULL, 10);
        if (c == 0UL || c > 0xFFFFFFUL) { sendAck("CODE", "ERROR"); return; }
        switch (codeAddSlot((uint32_t)c)) {
            case CODE_ADDED:  sendAck("CODE", "OK");     break;
            case CODE_EXISTS: sendAck("CODE", "EXISTS"); break;
            case CODE_FULL:   sendAck("CODE", "FULL");   break;
        }
        return;
    }
    if (strcasecmp(verb, "CODE_REMOVE") == 0) {
        if (param == NULL || *param == '\0') { sendAck("CODE", "ERROR"); return; }
        unsigned long c = strtoul(param, NULL, 10);
        sendAck("CODE", codeRemove((uint32_t)c) ? "OK" : "NOT_FOUND");
        return;
    }
    if (strcasecmp(verb, "CODE_LIST") == 0) {
        sendCodeList();
        return;
    }
    if (strcasecmp(verb, "CODE_CLEAR") == 0) {
        codeClearAll();
        sendAck("CODE", "OK");
        return;
    }
    // Unknown verb — silent ignore.
}

// Parses "@<target> <verb>[:<param>[:...]]". Mutates line in place.
// Meshtastic's Serial module in TEXTMSG mode prefixes received broadcasts with
// "<sender-shortname>: " (e.g. "1e44: @GATE HB_OFF"). Skip past an optional
// "<anything>: " prefix before looking for the '@' addressing token.
static void processCmdLine(char* line) {
    char* at = strchr(line, '@');
    if (!at) return;
    line = at;
    char* space = strchr(line + 1, ' ');
    if (!space) return;
    *space = '\0';
    const char* target = line + 1;
    char* rest = space + 1;
    while (*rest == ' ') rest++;

    char* colon = strchr(rest, ':');
    const char* param = NULL;
    if (colon) {
        *colon = '\0';
        param = colon + 1;
    }
    const char* verb = rest;
    if (*verb == '\0') return;
    handleCommand(target, verb, param);
}

void pollCmd() {
    while (meshSerial.available()) {
        int c = meshSerial.read();
        if (c < 0) break;
        if (c == '\r') continue;
        if (c == '\n') {
            if (cmdLen > 0) {
                cmdBuf[cmdLen] = '\0';
                processCmdLine(cmdBuf);
                cmdLen = 0;
            }
            continue;
        }
        if (cmdLen < CMD_BUF_SIZE - 1) {
            cmdBuf[cmdLen++] = (char)c;
        } else {
            cmdLen = 0;  // overflow — discard to avoid misparsing a truncation
        }
    }
}

// ── setup / loop ──────────────────────────────────────

void setup() {
    // Optiboot leaves the WDT enabled with its last value after a watchdog
    // reset, which would cause an immediate second reset if not cleared.
    wdt_disable();

    Serial.begin(115200);
    meshSerial.begin(MESH_BAUD);
    rf.enableReceive(digitalPinToInterrupt(RF_PIN));

    EEPROM.get(EEPROM_ADDR_BOOTCOUNT, bootCount);
    if (bootCount == 0xFFFF) bootCount = 0;
    bootCount++;
    EEPROM.put(EEPROM_ADDR_BOOTCOUNT, bootCount);

    // Heartbeat config
    uint8_t hbEn  = EEPROM.read(EEPROM_ADDR_HB_EN);
    uint8_t hbMin = EEPROM.read(EEPROM_ADDR_HB_MIN);
    hbEnabled = (hbEn == 0xFF) ? true : (hbEn != 0);
    if (hbMin == 0xFF || hbMin < HB_MIN_MIN || hbMin > HB_MIN_MAX) {
        hbIntervalMin = DEFAULT_HB_MIN;
    } else {
        hbIntervalMin = hbMin;
    }

    // Debounce config
    uint8_t dbs = EEPROM.read(EEPROM_ADDR_DEBOUNCE);
    if (dbs == 0xFF || dbs < DEBOUNCE_MIN_SEC || dbs > DEBOUNCE_MAX_SEC) {
        debounceSec = DEFAULT_DEBOUNCE_SEC;
    } else {
        debounceSec = dbs;
    }

    // Hit counter (fresh chip reads 0xFFFFFFFF → treat as 0)
    EEPROM.get(EEPROM_ADDR_HITS, hitCount);
    if (hitCount == 0xFFFFFFFFUL) hitCount = 0;

    // Code registry
    loadCodes();

    // Heltec ESP32 + Meshtastic needs several seconds to boot and open its
    // Serial module; sending STATUS earlier drops the frame into a dead UART.
    delay(8000);

    sendStatus();
    lastStatus = millis();
}

void loop() {
    unsigned long now = millis();

    // RF event handling
    if (rf.available()) {
        unsigned long code = rf.getReceivedValue();
        rf.resetAvailable();

        unsigned long debounceMs = (unsigned long)debounceSec * 1000UL;
        if (code != 0 && (now - lastRfEvent) > debounceMs) {
            lastRfEvent = now;

            if (codeKnown((uint32_t)code)) {
                hitCount++;
                saveHitCount();
                sendEvent("TRIGGERED", (uint32_t)code);
            } else {
                // Unknown code — log on USB serial for `make learn-sensor`.
                char buf[64];
                snprintf(buf, sizeof(buf), "RF unknown: %lu", code);
                Serial.println(buf);
            }
        }
    }

    // Inbound CMD handling (Heltec GPIO48 → R6 → D4)
    pollCmd();

    // Periodic STATUS heartbeat (interval configurable via HB_INTERVAL)
    if (hbEnabled && (now - lastStatus >= (unsigned long)hbIntervalMin * 60000UL)) {
        lastStatus = now;
        sendStatus();
    }
}
