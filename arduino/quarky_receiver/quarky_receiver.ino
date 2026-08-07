/*
 * quarky_receiver.ino
 * ===========================
 * Upload this to any Arduino-compatible board connected to Quarky (or
 * directly to the Quarky board if it runs Arduino firmware).
 *
 * Receives motor commands from the NEMO_SENSE laptop AI dashboard over
 * USB serial and drives two DC motors via L298N (or L293D / TB6612).
 *
 * Serial protocol (115200 baud):
 *   M:LEFT,RIGHT\n   -- set motors (values 0-255 each)
 *   M:0,0\n          -- stop
 *
 * Wiring (L298N):
 *   ENA  -> pin 10 (left motor PWM)
 *   IN1  -> pin 8
 *   IN2  -> pin 9
 *   ENB  -> pin 5  (right motor PWM)
 *   IN3  -> pin 6
 *   IN4  -> pin 7
 *   GND  -> common ground with laptop (when powered by battery)
 */

// -- Motor pins (change to match your wiring) --
const int L_EN  = 10;   // Left PWM
const int L_IN1 =  8;
const int L_IN2 =  9;
const int R_EN  =  5;   // Right PWM
const int R_IN1 =  6;
const int R_IN2 =  7;

const int BAUD = 115200;
const unsigned long TIMEOUT_MS = 500;  // stop if no command for 500 ms

int    leftPWM  = 0;
int    rightPWM = 0;
unsigned long lastCmd = 0;

// -- Setup -------------------------------------------------------------------
void setup() {
  pinMode(L_EN,  OUTPUT);
  pinMode(L_IN1, OUTPUT);
  pinMode(L_IN2, OUTPUT);
  pinMode(R_EN,  OUTPUT);
  pinMode(R_IN1, OUTPUT);
  pinMode(R_IN2, OUTPUT);

  Serial.begin(BAUD);
  Serial.println("NEMO_SENSE quarky_receiver ready");
  setMotors(0, 0);
}

// -- Loop --------------------------------------------------------------------
void loop() {
  // Watchdog: stop if no command received recently
  if (millis() - lastCmd > TIMEOUT_MS) {
    setMotors(0, 0);
  }

  if (!Serial.available()) return;

  String line = Serial.readStringUntil('\n');
  line.trim();

  if (line.startsWith("M:")) {
    // Parse M:LEFT,RIGHT
    String body = line.substring(2);
    int comma = body.indexOf(',');
    if (comma > 0) {
      int l = constrain(body.substring(0, comma).toInt(), 0, 255);
      int r = constrain(body.substring(comma + 1).toInt(), 0, 255);
      setMotors(l, r);
      lastCmd = millis();
      // Echo back for debugging
      Serial.print("OK:"); Serial.print(l); Serial.print(","); Serial.println(r);
    }
  }
}

// -- Motor driver ------------------------------------------------------------
void setMotors(int l, int r) {
  leftPWM  = l;
  rightPWM = r;

  // Left motor: forward
  digitalWrite(L_IN1, l > 0 ? HIGH : LOW);
  digitalWrite(L_IN2, LOW);
  analogWrite(L_EN, l);

  // Right motor: forward
  digitalWrite(R_IN1, r > 0 ? HIGH : LOW);
  digitalWrite(R_IN2, LOW);
  analogWrite(R_EN, r);
}