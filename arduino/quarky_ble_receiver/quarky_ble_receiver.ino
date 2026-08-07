/*
 * quarky_ble_receiver.ino
 * ===========================
 * Receives motor commands from the NEMO_SENSE laptop AI dashboard over
 * Bluetooth Low Energy (BLE) and drives two DC motors.
 *
 * Compatible with ESP32-based boards (like Quarky).
 *
 * BLE Protocol:
 *   Service UUID:        "19B10000-E8F2-537E-4F6C-D104768A1214"
 *   Characteristic UUID: "19B10001-E8F2-537E-4F6C-D104768A1214" (Write)
 *
 *   Message format: String "M:LEFT,RIGHT\n" where LEFT and RIGHT are -255 to 255.
 */

#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEServer.h>

// -- Motor pins (change to match your wiring) --
const int L_EN  = 10;
const int L_IN1 = 8;
const int L_IN2 = 9;
const int R_EN  = 5;
const int R_IN1 = 6;
const int R_IN2 = 7;

#define SERVICE_UUID        "19B10000-E8F2-537E-4F6C-D104768A1214"
#define CHARACTERISTIC_UUID "19B10001-E8F2-537E-4F6C-D104768A1214"

const unsigned long TIMEOUT_MS = 500;

int leftPWM  = 0;
int rightPWM = 0;
unsigned long lastCmd = 0;
bool deviceConnected = false;

// -- Motor driver ------------------------------------------------------------
void setMotors(int l, int r) {
  leftPWM  = l;
  rightPWM = r;
  digitalWrite(L_IN1, l > 0 ? HIGH : LOW);
  digitalWrite(L_IN2, LOW);
  analogWrite(L_EN, abs(l));
  digitalWrite(R_IN1, r > 0 ? HIGH : LOW);
  digitalWrite(R_IN2, LOW);
  analogWrite(R_EN, abs(r));
}

class ServerCallbacks: public BLEServerCallbacks {
    void onConnect(BLEServer* pServer) {
      deviceConnected = true;
      Serial.println("BLE Client Connected");
    }
    void onDisconnect(BLEServer* pServer) {
      deviceConnected = false;
      Serial.println("BLE Client Disconnected");
      setMotors(0, 0);
      BLEDevice::startAdvertising(); // restart advertising
    }
};

class CharCallbacks: public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic *pCharacteristic) {
      std::string value = pCharacteristic->getValue();
      if (value.length() > 0) {
        String line = String(value.c_str());
        line.trim();
        if (line.startsWith("M:")) {
          String body = line.substring(2);
          int comma = body.indexOf(',');
          if (comma > 0) {
            int l = constrain(body.substring(0, comma).toInt(), -255, 255);
            int r = constrain(body.substring(comma + 1).toInt(), -255, 255);
            setMotors(l, r);
            lastCmd = millis();
            Serial.printf("OK: %d, %d\n", l, r);
          }
        }
      }
    }
};

void setup() {
  Serial.begin(115200);
  pinMode(L_EN,  OUTPUT); pinMode(L_IN1, OUTPUT); pinMode(L_IN2, OUTPUT);
  pinMode(R_EN,  OUTPUT); pinMode(R_IN1, OUTPUT); pinMode(R_IN2, OUTPUT);
  setMotors(0, 0);

  Serial.println("Starting BLE Server...");
  BLEDevice::init("Quarky_Nemo");
  BLEServer *pServer = BLEDevice::createServer();
  pServer->setCallbacks(new ServerCallbacks());

  BLEService *pService = pServer->createService(SERVICE_UUID);
  BLECharacteristic *pCharacteristic = pService->createCharacteristic(
                                         CHARACTERISTIC_UUID,
                                         BLECharacteristic::PROPERTY_WRITE | 
                                         BLECharacteristic::PROPERTY_WRITE_NR
                                       );
  pCharacteristic->setCallbacks(new CharCallbacks());
  pService->start();

  BLEAdvertising *pAdvertising = BLEDevice::getAdvertising();
  pAdvertising->addServiceUUID(SERVICE_UUID);
  pAdvertising->setScanResponse(true);
  pAdvertising->setMinPreferred(0x06);
  BLEDevice::startAdvertising();
  Serial.println("Advertising Quarky_Nemo...");
}

void loop() {
  if (deviceConnected && (millis() - lastCmd > TIMEOUT_MS)) {
    if (leftPWM != 0 || rightPWM != 0) {
      setMotors(0, 0);
      Serial.println("Watchdog: Motors stopped");
    }
  }
  delay(10);
}