#include <Arduino.h>
#include <SPI.h>
#include <MFRC522.h>

// NodeMCU ESP8266 v3 + RC522 wiring:
// SDA/SS=D8(GPIO15), RST=D2(GPIO4), SCK=D5, MISO=D6, MOSI=D7, 3V3/GND.
constexpr uint8_t SS_PIN = D8;
constexpr uint8_t RST_PIN = D2;
MFRC522 rfid(SS_PIN, RST_PIN);
unsigned long lastDiagnostic = 0;

void diagnostic() {
  byte version = rfid.PCD_ReadRegister(MFRC522::VersionReg);
  Serial.print(F("{\"ok\":"));
  Serial.print(version == 0x91 || version == 0x92 ? F("true") : F("false"));
  Serial.print(F(",\"status\":\""));
  Serial.print(version == 0x91 || version == 0x92 ? F("reader_connected") : F("reader_not_detected"));
  Serial.print(F("\",\"version\":\"0x"));
  if (version < 0x10) Serial.print('0');
  Serial.print(version, HEX);
  Serial.println(F("\"}"));
}

void setup() {
  Serial.begin(115200);
  delay(300);
  SPI.begin();
  rfid.PCD_Init();
  Serial.println(F("{\"ok\":true,\"status\":\"ready\",\"device\":\"esp8266-rc522\"}"));
  diagnostic();
}

void loop() {
  if (millis() - lastDiagnostic >= 5000) {
    lastDiagnostic = millis();
    diagnostic();
  }
  if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) {
    delay(100);
    return;
  }
  Serial.print(F("{\"ok\":true,\"uid\":\""));
  for (byte i = 0; i < rfid.uid.size; i++) {
    if (rfid.uid.uidByte[i] < 0x10) Serial.print('0');
    Serial.print(rfid.uid.uidByte[i], HEX);
  }
  Serial.println(F("\"}"));
  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
  delay(500);
}
