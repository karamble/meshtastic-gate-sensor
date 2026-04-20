#include <Arduino.h>
#include <EEPROM.h>
#include <RCSwitch.h>
#include <SoftwareSerial.h>
#include <avr/wdt.h>
#include <ctype.h>
#include <string.h>
#include <stdlib.h>
#include "config.h"

RCSwitch rf = RCSwitch();
SoftwareSerial meshSerial(SERIAL_RX, SERIAL_TX);

unsigned long lastStatus = 0;
unsigned long lastUnknownEvent = 0;       // global rate-limit for unknown-code chatter
uint16_t bootCount = 0;
uint32_t hitCount = 0;                    // persisted in EEPROM

// Runtime config (loaded from EEPROM on boot, mutated by CMDs)
bool    hbEnabled     = true;
uint8_t hbIntervalMin = DEFAULT_HB_MIN;
uint8_t debounceSec   = DEFAULT_DEBOUNCE_SEC;

// Dynamic 433 MHz code list. Empty slot sentinel = 0xFFFFFFFF (fresh EEPROM).
uint32_t      codes[MAX_CODES];
char          codeNames[MAX_CODES][CODE_NAME_LEN];   // parallel; empty string = unnamed
unsigned long codeLastEvent[MAX_CODES];              // parallel; per-code debounce (RAM only)
uint8_t       codesCount = 0;
#define CODE_EMPTY 0xFFFFFFFFUL

// Inbound CMD line buffer
char    cmdBuf[CMD_BUF_SIZE];
uint8_t cmdLen = 0;

void sendMessage(const char* msg) {
    meshSerial.println(msg);
    Serial.println(msg);  // Debug echo
}

// Emits "Gate: TRIGGERED:<code> <name>". `name` may be NULL or ""; both render
// as "unnamed" so downstream parsers always see a two-token payload.
void sendTriggered(uint32_t code, const char* name) {
    char buf[96];
    snprintf(buf, sizeof(buf), "%s: TRIGGERED:%lu %s",
             SENSOR_NAME, (unsigned long)code,
             (name && name[0]) ? name : "unnamed");
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

// Writes only one name slot — callers changing a single name avoid rewriting
// the whole 256 B table, preserving EEPROM write cycles.
void saveNameSlot(uint8_t idx) {
    int base = EEPROM_ADDR_NAMES + (int)idx * CODE_NAME_LEN;
    for (uint8_t j = 0; j < CODE_NAME_LEN; j++) {
        EEPROM.update(base + j, (uint8_t)codeNames[idx][j]);
    }
}

void saveNames() {
    for (uint8_t i = 0; i < MAX_CODES; i++) saveNameSlot(i);
}

void loadCodes() {
    codesCount = 0;
    for (uint8_t i = 0; i < MAX_CODES; i++) {
        EEPROM.get(EEPROM_ADDR_CODES + i * 4, codes[i]);
        if (codes[i] != CODE_EMPTY) codesCount++;

        // Read the parallel name slot. Fresh EEPROM is 0xFF, which is neither
        // a valid ASCII char nor a NUL — detect that and normalise to "".
        int base = EEPROM_ADDR_NAMES + (int)i * CODE_NAME_LEN;
        uint8_t first = EEPROM.read(base);
        if (first == 0xFF || first == 0x00) {
            codeNames[i][0] = '\0';
        } else {
            for (uint8_t j = 0; j < CODE_NAME_LEN; j++) {
                codeNames[i][j] = (char)EEPROM.read(base + j);
            }
            codeNames[i][CODE_NAME_LEN - 1] = '\0';  // force-terminate
        }
    }
    // Seed fresh chip with the factory-calibrated code so out-of-the-box
    // installs still work without a CODE_ADD from the operator.
    if (codesCount == 0 && DEFAULT_CODE_OPEN != 0) {
        codes[0] = DEFAULT_CODE_OPEN;
        codeNames[0][0] = '\0';
        codesCount = 1;
        saveCodes();
        saveNameSlot(0);
    }
}

// ── Code-list operations ──────────────────────────────

// Returns slot index of `c`, or -1 if not in the registry.
int8_t codeIndexOf(uint32_t c) {
    for (uint8_t i = 0; i < MAX_CODES; i++) {
        if (codes[i] == c) return (int8_t)i;
    }
    return -1;
}

bool codeKnown(uint32_t c) {
    return codeIndexOf(c) >= 0;
}

const char* codeNameFor(uint32_t c) {
    int8_t i = codeIndexOf(c);
    return (i >= 0) ? codeNames[i] : "";
}

// Valid name: NULL / "" (unnamed), or ≤15 chars of [A-Za-z0-9_-].
// Reject ':', space, '@' because those are CMD-format delimiters.
static bool nameValid(const char* s) {
    if (!s) return true;
    size_t n = strlen(s);
    if (n == 0) return true;
    if (n >= CODE_NAME_LEN) return false;
    for (size_t i = 0; i < n; i++) {
        char ch = s[i];
        if (!(isalnum((unsigned char)ch) || ch == '_' || ch == '-')) return false;
    }
    return true;
}

enum CodeAddResult { CODE_ADDED, CODE_UPDATED, CODE_EXISTS, CODE_FULL };

// Add `c` with `name` (NULL or "" means unnamed). If `c` already exists and
// a non-empty `name` differs from the stored name, overwrite → CODE_UPDATED.
// Same name (or no name supplied) on an existing code → CODE_EXISTS.
CodeAddResult codeAddOrUpdate(uint32_t c, const char* name) {
    for (uint8_t i = 0; i < MAX_CODES; i++) {
        if (codes[i] == c) {
            if (name && name[0] && strncmp(codeNames[i], name, CODE_NAME_LEN) != 0) {
                strncpy(codeNames[i], name, CODE_NAME_LEN - 1);
                codeNames[i][CODE_NAME_LEN - 1] = '\0';
                saveNameSlot(i);
                return CODE_UPDATED;
            }
            return CODE_EXISTS;
        }
    }
    for (uint8_t i = 0; i < MAX_CODES; i++) {
        if (codes[i] == CODE_EMPTY) {
            codes[i] = c;
            if (name && name[0]) {
                strncpy(codeNames[i], name, CODE_NAME_LEN - 1);
                codeNames[i][CODE_NAME_LEN - 1] = '\0';
            } else {
                codeNames[i][0] = '\0';
            }
            codeLastEvent[i] = 0;  // fresh slot fires on first RF match
            codesCount++;
            saveCodes();
            saveNameSlot(i);
            return CODE_ADDED;
        }
    }
    return CODE_FULL;
}

bool codeRemove(uint32_t c) {
    for (uint8_t i = 0; i < MAX_CODES; i++) {
        if (codes[i] == c) {
            codes[i] = CODE_EMPTY;
            codeNames[i][0] = '\0';
            codeLastEvent[i] = 0;
            if (codesCount > 0) codesCount--;
            saveCodes();
            saveNameSlot(i);
            return true;
        }
    }
    return false;
}

void codeClearAll() {
    for (uint8_t i = 0; i < MAX_CODES; i++) {
        codes[i] = CODE_EMPTY;
        codeNames[i][0] = '\0';
        codeLastEvent[i] = 0;
    }
    codesCount = 0;
    saveCodes();
    saveNames();
}

void sendCodeList() {
    // 16 slots × (8-digit code + '=' + 15-char name) + 15 commas + prefix ≈ 420 B.
    // Budget 256 to stay well under a LoRa payload; truncate with tail margin.
    char buf[256];
    int off = snprintf(buf, sizeof(buf), "%s: CODES:", SENSOR_NAME);
    if (codesCount == 0) {
        snprintf(buf + off, sizeof(buf) - off, "NONE");
    } else {
        bool first = true;
        for (uint8_t i = 0; i < MAX_CODES; i++) {
            if (codes[i] == CODE_EMPTY) continue;
            if (off >= (int)(sizeof(buf) - (CODE_NAME_LEN + 16))) break;  // tail margin
            const char* nm = codeNames[i][0] ? codeNames[i] : "unnamed";
            off += snprintf(buf + off, sizeof(buf) - off, "%s%lu=%s",
                            first ? "" : ",", (unsigned long)codes[i], nm);
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
    // Format: CODE_ADD:<code>[:<name>]
    // Re-issuing with a different name on an existing code updates the name.
    if (strcasecmp(verb, "CODE_ADD") == 0) {
        if (param == NULL || *param == '\0') { sendAck("CODE", "ERROR"); return; }
        char* endp = NULL;
        unsigned long c = strtoul(param, &endp, 10);
        if (c == 0UL || c > 0xFFFFFFUL) { sendAck("CODE", "ERROR"); return; }
        const char* name = NULL;
        if (endp && *endp == ':') {
            name = endp + 1;
            if (*name == '\0') name = NULL;   // trailing colon = no name
        } else if (endp && *endp != '\0') {
            sendAck("CODE", "ERROR");          // garbage after the number
            return;
        }
        if (!nameValid(name)) { sendAck("CODE", "ERROR"); return; }
        switch (codeAddOrUpdate((uint32_t)c, name)) {
            case CODE_ADDED:   sendAck("CODE", "OK");      break;
            case CODE_UPDATED: sendAck("CODE", "UPDATED"); break;
            case CODE_EXISTS:  sendAck("CODE", "EXISTS");  break;
            case CODE_FULL:    sendAck("CODE", "FULL");    break;
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

    // RF event handling — debounce is per-code, so two different codes fired
    // back-to-back both get reported. Unknown codes share one global window
    // to keep 433 MHz noise from flooding the mesh.
    if (rf.available()) {
        unsigned long code = rf.getReceivedValue();
        rf.resetAvailable();

        unsigned long debounceMs = (unsigned long)debounceSec * 1000UL;
        if (code != 0) {
            int8_t idx = codeIndexOf((uint32_t)code);
            if (idx >= 0) {
                if ((now - codeLastEvent[idx]) > debounceMs) {
                    codeLastEvent[idx] = now;
                    hitCount++;
                    saveHitCount();
                    sendTriggered((uint32_t)code, codeNames[idx]);
                }
            } else if ((now - lastUnknownEvent) > debounceMs) {
                lastUnknownEvent = now;
                // Unknown code — always log on USB for `make learn-sensor`.
                char buf[64];
                snprintf(buf, sizeof(buf), "RF unknown: %lu", code);
                Serial.println(buf);
                // Broadcast only if above the noise floor (short bursts at
                // 1-3 digits are 433 MHz chatter, not a real transmitter).
                if (code >= UNKNOWN_MIN_CODE) {
                    sendTriggered((uint32_t)code, "unknown");
                }
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
