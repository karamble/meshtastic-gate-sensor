#include <Arduino.h>
#include <EEPROM.h>
#include <RCSwitch.h>
#include <SoftwareSerial.h>
#include "config.h"

RCSwitch rf = RCSwitch();
SoftwareSerial meshSerial(SERIAL_RX, SERIAL_TX);

unsigned long lastStatus = 0;
unsigned long lastRfEvent = 0;
uint16_t bootCount = 0;
uint32_t hitCount = 0;

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

void setup() {
    Serial.begin(115200);
    meshSerial.begin(MESH_BAUD);
    rf.enableReceive(digitalPinToInterrupt(RF_PIN));

    EEPROM.get(EEPROM_ADDR_BOOTCOUNT, bootCount);
    if (bootCount == 0xFFFF) bootCount = 0;  // fresh EEPROM reads as 0xFFFF
    bootCount++;
    EEPROM.put(EEPROM_ADDR_BOOTCOUNT, bootCount);

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

    // Periodic STATUS heartbeat
    if (now - lastStatus >= STATUS_MS) {
        lastStatus = now;
        sendStatus();
    }
}
