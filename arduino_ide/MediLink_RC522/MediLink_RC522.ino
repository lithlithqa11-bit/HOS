#include <Arduino.h>
#include <MFRC522.h>
#include <SPI.h>

// NodeMCU ESP8266 v3 + RC522 wiring:
// SDA/SS=D2(GPIO4), RST=D1(GPIO5), SCK=D5, MISO=D6, MOSI=D7, 3V3/GND.
// Match the user's proven RC522 wiring.
constexpr uint8_t SS_PIN = D2;
constexpr uint8_t RST_PIN = D1;
MFRC522 rfid(SS_PIN, RST_PIN);
unsigned long lastDiagnostic = 0;
constexpr byte MARKER[4] = {'M', 'L', 'N', '1'};
char command[72] = {};
size_t commandLength = 0;
char pendingToken[65] = {};
bool writePending = false;
bool readPending = false;
unsigned long writeStarted = 0;
unsigned long readStarted = 0;

void status(const char *name, bool ok = false) {
  Serial.print(F("{\"ok\":"));
  Serial.print(ok ? F("true") : F("false"));
  Serial.print(F(",\"status\":\""));
  Serial.print(name);
  Serial.println(F("\"}"));
}

bool validToken(const char *token) {
  if (strlen(token) != 64)
    return false;
  for (byte i = 0; i < 64; ++i) {
    if (!((token[i] >= '0' && token[i] <= '9') ||
          (token[i] >= 'a' && token[i] <= 'f')))
      return false;
  }
  return true;
}

byte nibble(char value) {
  return value <= '9' ? value - '0' : value - 'a' + 10;
}

void pollCommand() {
  while (Serial.available()) {
    char value = static_cast<char>(Serial.read());
    if (value == '\r')
      continue;
    if (value == '\n') {
      command[commandLength] = '\0';
      if (strncmp(command, "WRITE ", 6) == 0 && validToken(command + 6)) {
        memcpy(pendingToken, command + 6, 65);
        writePending = true;
        readPending = false;
        writeStarted = millis();
        status("write_ready", true);
      } else if (strcmp(command, "READ") == 0) {
        readPending = true;
        writePending = false;
        memset(pendingToken, 0, sizeof(pendingToken));
        readStarted = millis();
        status("read_ready", true);
      } else {
        status("invalid_command");
      }
      memset(command, 0, sizeof(command));
      commandLength = 0;
    } else if (commandLength < sizeof(command) - 1) {
      command[commandLength++] = value;
    } else {
      commandLength = 0;
      status("invalid_command");
    }
  }
}

bool readBlock(byte block, byte *output) {
  byte buffer[18] = {};
  byte length = sizeof(buffer);
  if (rfid.MIFARE_Read(block, buffer, &length) != MFRC522::STATUS_OK ||
      length != 18)
    return false;
  memcpy(output, buffer, 16);
  return true;
}

bool authenticateClassic() {
  MFRC522::MIFARE_Key key = {};
  memset(key.keyByte, 0xFF, MFRC522::MF_KEY_SIZE);
  return rfid.PCD_Authenticate(MFRC522::PICC_CMD_MF_AUTH_KEY_A, 4, &key,
                               &rfid.uid) == MFRC522::STATUS_OK;
}

bool readClassicToken(byte *token) {
  byte data[48] = {};
  for (byte block = 4; block <= 6; ++block) {
    if (!readBlock(block, data + (block - 4) * 16))
      return false;
  }
  if (memcmp(data, MARKER, 4) != 0)
    return false;
  memcpy(token, data + 4, 32);
  return true;
}

bool writeClassicBlock(byte block, byte *data) {
  return rfid.MIFARE_Write(block, data, 16) == MFRC522::STATUS_OK;
}

bool writeClassicToken(const char *token) {
  byte data[48] = {};
  memcpy(data, MARKER, 4);
  for (byte i = 0; i < 32; ++i) {
    data[i + 4] = (nibble(token[i * 2]) << 4) | nibble(token[i * 2 + 1]);
  }
  byte empty[16] = {};
  // Sector 1 data blocks only. Never write the sector trailer (block 7).
  if (!writeClassicBlock(4, empty))
    return false;
  if (!writeClassicBlock(5, data + 16) || !writeClassicBlock(6, data + 32))
    return false;
  if (!writeClassicBlock(4, data))
    return false;
  byte check[32] = {};
  return readClassicToken(check) && memcmp(check, data + 4, 32) == 0;
}

void diagnostic() {
  byte version = rfid.PCD_ReadRegister(MFRC522::VersionReg);
  bool connected =
      version == 0x88 || version == 0x90 || version == 0x91 || version == 0x92;
  Serial.print(F("{\"ok\":"));
  Serial.print(connected ? F("true") : F("false"));
  Serial.print(F(",\"status\":\""));
  Serial.print(connected ? F("reader_connected") : F("reader_not_detected"));
  Serial.print(F("\",\"version\":\"0x"));
  if (version < 0x10)
    Serial.print('0');
  Serial.print(version, HEX);
  Serial.println(F("\"}"));
}

void setup() {
  Serial.begin(115200);
  delay(300);
  SPI.begin();
  rfid.PCD_Init();
  Serial.println(F("{\"ok\":true,\"status\":\"ready\",\"device\":\"esp8266-"
                   "rc522-classic1k\"}"));
  diagnostic();
}

void loop() {
  pollCommand();
  if (writePending && millis() - writeStarted >= 15000) {
    memset(pendingToken, 0, sizeof(pendingToken));
    writePending = false;
    status("write_timeout");
  }
  if (readPending && millis() - readStarted >= 15000) {
    readPending = false;
    status("read_timeout");
  }
  if (millis() - lastDiagnostic >= 5000) {
    lastDiagnostic = millis();
    diagnostic();
  }
  if (!writePending && !readPending) {
    delay(100);
    return;
  }
  byte atqa[2] = {};
  byte atqaLength = sizeof(atqa);
  bool present = rfid.PICC_WakeupA(atqa, &atqaLength) == MFRC522::STATUS_OK;
  if (!present || !rfid.PICC_ReadCardSerial()) {
    delay(100);
    return;
  }
  MFRC522::PICC_Type cardType = rfid.PICC_GetType(rfid.uid.sak);
  bool supported =
      cardType == MFRC522::PICC_TYPE_MIFARE_1K && authenticateClassic();
  if (!supported) {
    Serial.print(F("{\"ok\":false,\"status\":\"unsupported_card_or_auth_"
                   "failed\",\"type\":"));
    Serial.print(static_cast<int>(cardType));
    Serial.println('}');
    memset(pendingToken, 0, sizeof(pendingToken));
    writePending = false;
    readPending = false;
  } else if (writePending) {
    if (writeClassicToken(pendingToken)) {
      Serial.println(F("{\"ok\":true,\"written\":true}"));
    } else {
      status("write_or_verification_failed");
    }
    memset(pendingToken, 0, sizeof(pendingToken));
    writePending = false;
  } else {
    byte token[32] = {};
    if (readClassicToken(token)) {
      static constexpr char HEX_DIGITS[] = "0123456789abcdef";
      Serial.print(F("{\"ok\":true,\"token\":\""));
      for (byte i = 0; i < 32; ++i) {
        Serial.print(HEX_DIGITS[token[i] >> 4]);
        Serial.print(HEX_DIGITS[token[i] & 15]);
      }
      Serial.println(F("\",\"reader\":\"ESP8266 RC522 Classic1K\"}"));
    } else {
      status("card_not_provisioned");
    }
    readPending = false;
  }
  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
  delay(500);
}
