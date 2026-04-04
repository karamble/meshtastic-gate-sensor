#include <Arduino.h>
#include <RCSwitch.h>
#include <SoftwareSerial.h>
#include "config.h"

RCSwitch rf = RCSwitch();
SoftwareSerial meshSerial(SERIAL_RX, SERIAL_TX);

unsigned long lastHeartbeat = 0;
unsigned long lastBatCheck = 0;
unsigned long lastRfEvent = 0;

float batteryVoltage = 0.0;
bool batteryLow = false;
bool batteryCritical = false;
bool batteryRecovered = false;

float readBattery() {
    int raw = analogRead(BAT_PIN);
    // 10k/10k divider: actual voltage = ADC voltage * 2
    // Nano ADC: 5V reference, 1024 steps
    return (raw / 1024.0) * 5.0 * 2.0;
}

const char* batteryStatus(float v) {
    if (v < BAT_CRITICAL) return "CRITICAL";
    if (v < BAT_LOW)      return "LOW";
    return "OK";
}

void sendMessage(const char* msg) {
    meshSerial.println(msg);
    Serial.println(msg);  // Debug echo
}

void sendGateEvent(const char* state) {
    char buf[64];
    snprintf(buf, sizeof(buf), "%s: %s [BATT %s] %.2fV",
             SENSOR_NAME, state, batteryStatus(batteryVoltage), (double)batteryVoltage);
    sendMessage(buf);
}

void sendHeartbeat() {
    char buf[64];
    snprintf(buf, sizeof(buf), "GATE NODE: Online [BATT %s] %.2fV",
             batteryStatus(batteryVoltage), (double)batteryVoltage);
    sendMessage(buf);
}

void checkBattery() {
    float v = readBattery();
    batteryVoltage = v;

    if (v < BAT_CRITICAL && !batteryCritical) {
        batteryCritical = true;
        batteryLow = true;
        char buf[64];
        snprintf(buf, sizeof(buf), "GATE NODE: CRITICAL BATTERY %.2fV -- may go offline!", (double)v);
        sendMessage(buf);
    } else if (v < BAT_LOW && !batteryLow) {
        batteryLow = true;
        char buf[64];
        snprintf(buf, sizeof(buf), "GATE NODE: Low battery %.2fV -- check solar", (double)v);
        sendMessage(buf);
    } else if (v >= BAT_LOW && (batteryLow || batteryCritical)) {
        batteryLow = false;
        batteryCritical = false;
        char buf[64];
        snprintf(buf, sizeof(buf), "GATE NODE: Battery recovered %.2fV", (double)v);
        sendMessage(buf);
    }
}

void setup() {
    Serial.begin(115200);
    meshSerial.begin(MESH_BAUD);
    rf.enableReceive(digitalPinToInterrupt(RF_PIN));

    batteryVoltage = readBattery();
    sendHeartbeat();
}

void loop() {
    unsigned long now = millis();

    // RF event handling
    if (rf.available()) {
        unsigned long code = rf.getReceivedValue();
        rf.resetAvailable();

        if (code != 0 && (now - lastRfEvent) > DEBOUNCE_MS) {
            lastRfEvent = now;
            batteryVoltage = readBattery();

            if (code == CODE_OPEN) {
                sendGateEvent("OPEN");
            } else if (code == CODE_CLOSED) {
                sendGateEvent("CLOSED");
            } else {
                // Unknown code — log for debugging
                char buf[64];
                snprintf(buf, sizeof(buf), "RF unknown: %lu", code);
                Serial.println(buf);
            }
        }
    }

    // Periodic battery check
    if (now - lastBatCheck >= BAT_CHECK_MS) {
        lastBatCheck = now;
        checkBattery();
    }

    // Periodic heartbeat
    if (now - lastHeartbeat >= HEARTBEAT_MS) {
        lastHeartbeat = now;
        batteryVoltage = readBattery();
        sendHeartbeat();
    }
}
