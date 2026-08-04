/*
 * motor_controller.ino — Netra Blind Guide Rover
 * Arduino UNO Q STM32 co-processor firmware
 *
 * Motor Driver: L9110S-4 (4-pin tank drive)
 *   Left motors (1+2)  → D2 (IA), D3 (IB)
 *   Right motors (3+4) → D4 (IA), D5 (IB)
 *
 * GPS: NEO-6M via SoftwareSerial
 *   D12 = RX  (connects to NEO-6M TX)
 *   D13 = TX  (connects to NEO-6M RX — optional, for config)
 *
 * RPC commands (called from Linux via arduino-router):
 *   drive(int cmd)    → 0=stop 1=fwd 2=back 3=left 4=right
 *   gps_nmea()        → returns latest raw NMEA sentence (string)
 *   ping()            → returns 1
 *
 * L9110S logic:
 *   IA=HIGH, IB=LOW  → Forward
 *   IA=LOW,  IB=HIGH → Reverse
 *   IA=LOW,  IB=LOW  → Stop (coast)
 */

#include <Arduino_RouterBridge.h>
#include <SoftwareSerial.h>

// ── Motor pins ────────────────────────────────────────────────────────────────
#define LEFT_IA   2
#define LEFT_IB   3
#define RIGHT_IA  4
#define RIGHT_IB  5

// ── GPS pins (SoftwareSerial) ─────────────────────────────────────────────────
#define GPS_RX_PIN  12   // Arduino D12 ← NEO-6M TX
#define GPS_TX_PIN  13   // Arduino D13 → NEO-6M RX
#define GPS_BAUD    9600

SoftwareSerial gpsSerial(GPS_RX_PIN, GPS_TX_PIN);

// Buffer for latest complete NMEA sentence
static char nmeaBuf[128];
static char nmeaReady[128];
static uint8_t nmeaPos = 0;
static bool nmeaValid = false;

// ── Watchdog ──────────────────────────────────────────────────────────────────
#define WATCHDOG_MS  2000
static unsigned long lastCmd = 0;

// ── Motor helpers ─────────────────────────────────────────────────────────────
inline void leftForward()  { digitalWrite(LEFT_IA, HIGH); digitalWrite(LEFT_IB, LOW);  }
inline void leftReverse()  { digitalWrite(LEFT_IA, LOW);  digitalWrite(LEFT_IB, HIGH); }
inline void leftStop()     { digitalWrite(LEFT_IA, LOW);  digitalWrite(LEFT_IB, LOW);  }
inline void rightForward() { digitalWrite(RIGHT_IA, HIGH); digitalWrite(RIGHT_IB, LOW);  }
inline void rightReverse() { digitalWrite(RIGHT_IA, LOW);  digitalWrite(RIGHT_IB, HIGH); }
inline void rightStop()    { digitalWrite(RIGHT_IA, LOW);  digitalWrite(RIGHT_IB, LOW);  }

void allStop() { leftStop(); rightStop(); }

// ── RPC: drive(cmd) ───────────────────────────────────────────────────────────
int drive(int cmd) {
    lastCmd = millis();
    switch (cmd) {
        case 1: leftForward();  rightForward();  break;  // FORWARD
        case 2: leftReverse();  rightReverse();  break;  // BACK
        case 3: leftReverse();  rightForward();  break;  // LEFT (pivot)
        case 4: leftForward();  rightReverse();  break;  // RIGHT (pivot)
        default: allStop(); break;                        // STOP
    }
    return 1;
}

// ── RPC: gps_nmea() ───────────────────────────────────────────────────────────
// Returns the most recent complete NMEA sentence (e.g. "$GPRMC,...")
// Returns empty string "" if no fix data yet
const char* gps_nmea() {
    if (nmeaValid) {
        return nmeaReady;
    }
    return "";
}

// ── RPC: ping() ───────────────────────────────────────────────────────────────
int ping() { return 1; }

// ── GPS reader — called every loop() ─────────────────────────────────────────
void pollGPS() {
    while (gpsSerial.available()) {
        char c = gpsSerial.read();
        if (c == '$') {
            // Start of new sentence
            nmeaPos = 0;
            nmeaBuf[nmeaPos++] = c;
        } else if (c == '\n' || c == '\r') {
            // End of sentence — copy to ready buffer if valid
            if (nmeaPos > 6 && nmeaBuf[0] == '$') {
                nmeaBuf[nmeaPos] = '\0';
                memcpy(nmeaReady, nmeaBuf, nmeaPos + 1);
                nmeaValid = true;
            }
            nmeaPos = 0;
        } else if (nmeaPos < (sizeof(nmeaBuf) - 1)) {
            nmeaBuf[nmeaPos++] = c;
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
void setup() {
    // Motor pins
    pinMode(LEFT_IA,  OUTPUT); digitalWrite(LEFT_IA,  LOW);
    pinMode(LEFT_IB,  OUTPUT); digitalWrite(LEFT_IB,  LOW);
    pinMode(RIGHT_IA, OUTPUT); digitalWrite(RIGHT_IA, LOW);
    pinMode(RIGHT_IB, OUTPUT); digitalWrite(RIGHT_IB, LOW);

    // GPS serial
    gpsSerial.begin(GPS_BAUD);
    memset(nmeaBuf,   0, sizeof(nmeaBuf));
    memset(nmeaReady, 0, sizeof(nmeaReady));

    // Bridge RPC
    Bridge.begin();
    Bridge.provide("drive",    drive);
    Bridge.provide("gps_nmea", gps_nmea);
    Bridge.provide("ping",     ping);

    lastCmd = millis();
}

void loop() {
    // Read GPS data
    pollGPS();

    // Watchdog: auto-stop motors if no drive command for 2s
    if ((millis() - lastCmd) > WATCHDOG_MS) {
        allStop();
    }
}
