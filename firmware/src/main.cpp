#include <Arduino.h>
#include <RCSwitch.h>
#include <SoftwareSerial.h>
#include "config.h"

RCSwitch rf = RCSwitch();
SoftwareSerial meshSerial(SERIAL_RX, SERIAL_TX);

unsigned long lastHeartbeat = 0;
unsigned long lastRfEvent = 0;

void sendMessage(const char* msg) {
    meshSerial.println(msg);
    Serial.println(msg);  // Debug echo
}

void sendGateEvent(const char* state) {
    char buf[64];
    snprintf(buf, sizeof(buf), "%s: %s", SENSOR_NAME, state);
    sendMessage(buf);
}

void sendHeartbeat() {
    sendMessage("GATE NODE: Online");
}

void setup() {
    Serial.begin(115200);
    meshSerial.begin(MESH_BAUD);
    rf.enableReceive(digitalPinToInterrupt(RF_PIN));

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

            if (code == CODE_OPEN) {
                sendGateEvent("TRIGGERED");
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

    // Periodic heartbeat
    if (now - lastHeartbeat >= HEARTBEAT_MS) {
        lastHeartbeat = now;
        sendHeartbeat();
    }
}
