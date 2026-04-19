#include <Arduino.h>
#include <EEPROM.h>
#include <RCSwitch.h>
#include <SoftwareSerial.h>
#include <string.h>
#include <stdlib.h>
#include "config.h"

RCSwitch rf = RCSwitch();
SoftwareSerial meshSerial(SERIAL_RX, SERIAL_TX);

unsigned long lastStatus = 0;
unsigned long lastRfEvent = 0;
uint16_t bootCount = 0;
uint32_t hitCount = 0;

// Runtime heartbeat config (loaded from EEPROM on boot, mutated by HB_* CMDs)
bool    hbEnabled     = true;
uint8_t hbIntervalMin = DEFAULT_HB_MIN;

// Inbound CMD line buffer
char    cmdBuf[CMD_BUF_SIZE];
uint8_t cmdLen = 0;

void sendMessage(const char* msg) {
    meshSerial.println(msg);
    Serial.println(msg);  // Debug echo
}

void sendGateEvent(const char* state) {
    char buf[64];
    snprintf(buf, sizeof(buf), "%s: %s", SENSOR_NAME, state);
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

void sendHbAck(const char* status) {
    char buf[48];
    snprintf(buf, sizeof(buf), "%s: HB_ACK:%s", SENSOR_NAME, status);
    sendMessage(buf);
}

// True for ALL or the sensor's own name (case-insensitive).
static bool targetMatches(const char* target) {
    if (strcasecmp(target, "ALL") == 0) return true;
    if (strcasecmp(target, SENSOR_NAME) == 0) return true;
    return false;
}

static void handleCommand(const char* target, const char* verb, const char* param) {
    if (!targetMatches(target)) return;

    if (strcasecmp(verb, "STATUS") == 0) {
        sendStatus();
        return;
    }
    if (strcasecmp(verb, "HB_ON") == 0) {
        hbEnabled = true;
        EEPROM.update(EEPROM_ADDR_HB_EN, 1);
        lastStatus = millis();
        sendHbAck("OK");
        return;
    }
    if (strcasecmp(verb, "HB_OFF") == 0) {
        hbEnabled = false;
        EEPROM.update(EEPROM_ADDR_HB_EN, 0);
        sendHbAck("OK");
        return;
    }
    if (strcasecmp(verb, "HB_INTERVAL") == 0) {
        if (param == NULL || *param == '\0') {
            sendHbAck("ERROR");
            return;
        }
        // atoi returns 0 on non-numeric; 0 is out of range anyway.
        int m = atoi(param);
        if (m < HB_MIN_MIN || m > HB_MIN_MAX) {
            sendHbAck("ERROR");
            return;
        }
        hbIntervalMin = (uint8_t)m;
        EEPROM.update(EEPROM_ADDR_HB_MIN, hbIntervalMin);
        lastStatus = millis();  // restart timer from now
        sendHbAck("OK");
        return;
    }
    // Unknown verb — silent ignore (don't flood mesh with NACKs).
}

// Parses "@<target> <verb>[:<param>[:...]]". Mutates line in place.
static void processCmdLine(char* line) {
    if (line[0] != '@') return;
    char* space = strchr(line + 1, ' ');
    if (!space) return;
    *space = '\0';
    const char* target = line + 1;
    char* rest = space + 1;
    while (*rest == ' ') rest++;  // allow extra spaces

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

// Drain meshSerial into cmdBuf, dispatch on newline.
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
            // Overflow — discard the line so we don't misparse a truncation.
            cmdLen = 0;
        }
    }
}

void setup() {
    Serial.begin(115200);
    meshSerial.begin(MESH_BAUD);
    rf.enableReceive(digitalPinToInterrupt(RF_PIN));

    EEPROM.get(EEPROM_ADDR_BOOTCOUNT, bootCount);
    if (bootCount == 0xFFFF) bootCount = 0;  // fresh EEPROM reads as 0xFFFF
    bootCount++;
    EEPROM.put(EEPROM_ADDR_BOOTCOUNT, bootCount);

    // Load heartbeat config. 0xFF == fresh/unwritten cell → fall back to default.
    uint8_t hbEn  = EEPROM.read(EEPROM_ADDR_HB_EN);
    uint8_t hbMin = EEPROM.read(EEPROM_ADDR_HB_MIN);
    hbEnabled = (hbEn == 0xFF) ? true : (hbEn != 0);
    if (hbMin == 0xFF || hbMin < HB_MIN_MIN || hbMin > HB_MIN_MAX) {
        hbIntervalMin = DEFAULT_HB_MIN;
    } else {
        hbIntervalMin = hbMin;
    }

    sendStatus();
    lastStatus = millis();
}

void loop() {
    unsigned long now = millis();

    // RF event handling
    if (rf.available()) {
        unsigned long code = rf.getReceivedValue();
        rf.resetAvailable();

        if (code != 0 && (now - lastRfEvent) > DEBOUNCE_MS) {
            lastRfEvent = now;

            if (code == CODE_OPEN) {
                hitCount++;
                sendGateEvent("TRIGGERED");
            } else if (code == CODE_CLOSED) {
                hitCount++;
                sendGateEvent("CLOSED");
            } else {
                // Unknown code — log for debugging
                char buf[64];
                snprintf(buf, sizeof(buf), "RF unknown: %lu", code);
                Serial.println(buf);
            }
        }
    }

    // Inbound CMD handling (from Heltec GPIO48 -> R6 -> D4)
    pollCmd();

    // Periodic STATUS heartbeat (interval configurable via HB_INTERVAL)
    if (hbEnabled && (now - lastStatus >= (unsigned long)hbIntervalMin * 60000UL)) {
        lastStatus = now;
        sendStatus();
    }
}
