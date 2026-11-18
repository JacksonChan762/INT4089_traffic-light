#include <Arduino.h>
#include <SoftwareSerial.h>
#include "TrafficController.h"

// Two one-way roads: A (NS) R,Y,G then B (EW) R,Y,G.
// Exactly six active-high LEDs, one per output pin.
const uint8_t NS_R = 2, NS_Y = 3, NS_G = 4;
const uint8_t EW_R = 5, EW_Y = 6, EW_G = 7;
SoftwareSerial gateway(10, 11); // RX, TX through the UART level shifter.
TrafficController controller;
char line[20];
uint8_t used = 0;
bool overflowed = false;

void showLights() {
  // Remove permissive signals before applying the next phase.
  digitalWrite(NS_G, LOW); digitalWrite(EW_G, LOW);
  digitalWrite(NS_Y, LOW); digitalWrite(EW_Y, LOW);
  digitalWrite(NS_R, HIGH); digitalWrite(EW_R, HIGH);
  switch (controller.phase) {
    case TrafficController::NS_GREEN: digitalWrite(NS_R, LOW); digitalWrite(NS_G, HIGH); break;
    case TrafficController::NS_YELLOW: digitalWrite(NS_R, LOW); digitalWrite(NS_Y, HIGH); break;
    case TrafficController::EW_GREEN: digitalWrite(EW_R, LOW); digitalWrite(EW_G, HIGH); break;
    case TrafficController::EW_YELLOW: digitalWrite(EW_R, LOW); digitalWrite(EW_Y, HIGH); break;
    default: break;
  }
  Serial.print(F("Phase=")); Serial.print(int(controller.phase));
  Serial.print(F(" duration_ms=")); Serial.println(controller.duration);
}

void sendState(uint32_t now) {
  const uint32_t elapsed = now - controller.started;
  const uint32_t remaining = elapsed < controller.duration ? controller.duration - elapsed : 0;
  gateway.print(F("S,"));
  gateway.print(int(controller.phase));
  gateway.print(',');
  gateway.print(controller.duration);
  gateway.print(',');
  gateway.print(remaining);
  gateway.print(',');
  gateway.print(controller.fresh(now) ? 1 : 0);
  gateway.print(',');
  gateway.print(controller.ns);
  gateway.print(',');
  gateway.println(controller.ew);
}

void setup() {
  for (uint8_t pin = 2; pin <= 7; ++pin) pinMode(pin, OUTPUT);
  Serial.begin(115200);
  gateway.begin(9600);
  digitalWrite(10, LOW); // Disable the RX 5V pull-up for the direct ESP32 connection.
  controller.started = millis();
  showLights();
}
void loop() {
  bool stateRequested = false;
  // Bound the read work so input cannot starve the light controller.
  for (uint8_t i = 0; i < 32 && gateway.available(); ++i) {
    char ch = gateway.read();
    if (ch == '\n') {
      line[used] = '\0';
      if (!overflowed) {
        if (line[0] == 'S' && line[1] == '\0') stateRequested = true;
        else applyCommand(line, controller, millis());
      }
      used = 0; overflowed = false;
    } else if (ch != '\r') {
      if (ch < 32 || ch > 126 || used >= sizeof(line) - 1) overflowed = true;
      else if (!overflowed) line[used++] = ch;
    }
  }
  const uint32_t now = millis();
  if (controller.tick(now)) showLights();
  // Reply only on request so SoftwareSerial stays ready for count updates.
  if (stateRequested) sendState(now);
}
