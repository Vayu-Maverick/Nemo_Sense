/*
 * DEPRECATED — DO NOT USE WITH main.py
 *
 * This sketch was a simple L298N test using single-char commands (f/b/r/l/s)
 * and a WRONG pin map. The Python brain sends MOTOR:left,right which this
 * sketch does not understand — that is why motors did not move.
 *
 * USE INSTEAD:
 *   arduino/motor_controller/motor_controller.ino  (Quarky bridge or L298N)
 *
 * For Quarky chassis: set USE_QUARKY_BRIDGE = 1 in motor_controller.ino
 * Upload guidesense_quarky_receiver.py to Quarky via PictoBlox.
 *
 * See docs/quarky_bridge.md for full wiring instructions.
 */

// Original test sketch kept for reference only.
// ------------ Pin definitions ------------
const int ENA = 5;
const int IN1 = 9;
const int IN2 = 10;
const int ENB = 6;
const int IN3 = 4;
const int IN4 = 7;

void setup() {
  pinMode(ENA, OUTPUT);
  pinMode(ENB, OUTPUT);
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(IN3, OUTPUT);
  pinMode(IN4, OUTPUT);
  stopMotor();
  Serial.begin(115200);
  Serial.println(F("DEPRECATED — flash motor_controller.ino instead"));
}

void loop() {
  if (Serial.available() > 0) {
    char cmd = Serial.read();
    switch (cmd) {
      case 'f': forward(); break;
      case 'b': backward(); break;
      case 'r': turnRight(); break;
      case 'l': turnLeft(); break;
      case 's': stopMotor(); break;
    }
  }
}

void forward() {
  analogWrite(ENA, 200); analogWrite(ENB, 200);
  digitalWrite(IN1, HIGH); digitalWrite(IN2, LOW);
  digitalWrite(IN3, HIGH); digitalWrite(IN4, LOW);
}
void backward() {
  analogWrite(ENA, 200); analogWrite(ENB, 200);
  digitalWrite(IN1, LOW); digitalWrite(IN2, HIGH);
  digitalWrite(IN3, LOW); digitalWrite(IN4, HIGH);
}
void turnRight() {
  analogWrite(ENA, 200); analogWrite(ENB, 200);
  digitalWrite(IN1, HIGH); digitalWrite(IN2, LOW);
  digitalWrite(IN3, LOW); digitalWrite(IN4, HIGH);
}
void turnLeft() {
  analogWrite(ENA, 200); analogWrite(ENB, 200);
  digitalWrite(IN1, LOW); digitalWrite(IN2, HIGH);
  digitalWrite(IN3, HIGH); digitalWrite(IN4, LOW);
}
void stopMotor() {
  analogWrite(ENA, 0); analogWrite(ENB, 0);
  digitalWrite(IN1, LOW); digitalWrite(IN2, LOW);
  digitalWrite(IN3, LOW); digitalWrite(IN4, LOW);
}
