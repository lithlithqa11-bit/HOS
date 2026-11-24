#include <Adafruit_PN532.h>
#include <Arduino.h>
#include <Wire.h>

// ESP32-S3 + PN532 in I2C mode. These are the pins from the supplied sketch.
constexpr int8_t SDA_PIN = 8;
constexpr int8_t SCL_PIN = 9;
constexpr int8_t BUZZER_PIN = 14;
constexpr int8_t GREEN_LED_PIN = 12;
constexpr int8_t RED_LED_PIN = 13;
constexpr int8_t PN532_IRQ = -1;
constexpr int8_t PN532_RESET = -1;

Adafruit_PN532 nfc(PN532_IRQ, PN532_RESET, &Wire);

constexpr uint8_t MARKER[4] = {'M', 'L', 'N', '1'};
constexpr uint8_t CLASSIC_KEY[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
constexpr uint8_t TOKEN_BYTES = 32;
constexpr uint32_t CARD_WAIT_MS = 15000;
constexpr uint16_t GREEN_FEEDBACK_DELAY_MS = 350;
constexpr uint16_t GREEN_LED_HOLD_MS = 650;
constexpr uint16_t RED_ALERT_MS = 1800;

char command[72] = {};
size_t commandLength = 0;
char pendingToken[65] = {};
bool writePending = false;
bool readPending = false;
unsigned long writeStarted = 0;
unsigned long readStarted = 0;
unsigned long lastDiagnostic = 0;

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
  for (uint8_t i = 0; i < 64; ++i) {
    if (!((token[i] >= '0' && token[i] <= '9') ||
          (token[i] >= 'a' && token[i] <= 'f')))
      return false;
  }
  return true;
}

uint8_t nibble(char value) {
  return value <= '9' ? value - '0' : value - 'a' + 10;
}

void playSuccess() {
  digitalWrite(RED_LED_PIN, LOW);
  digitalWrite(GREEN_LED_PIN, HIGH);
  digitalWrite(BUZZER_PIN, HIGH);
  delay(80);
  digitalWrite(BUZZER_PIN, LOW);
  delay(60);
  digitalWrite(BUZZER_PIN, HIGH);
  delay(80);
  digitalWrite(BUZZER_PIN, LOW);
  delay(GREEN_LED_HOLD_MS);
  digitalWrite(GREEN_LED_PIN, LOW);
}

void playError() {
  digitalWrite(GREEN_LED_PIN, LOW);
  digitalWrite(RED_LED_PIN, HIGH);
  digitalWrite(BUZZER_PIN, HIGH);
  delay(RED_ALERT_MS);
  digitalWrite(BUZZER_PIN, LOW);
  digitalWrite(RED_LED_PIN, LOW);
}

void pollCommand() {
  while (Serial.available()) {
    char value = static_cast<char>(Serial.read());
    if (value == '\r')
      continue;
    if (value == '\n') {
      command[commandLength] = '\0';
      if (strncmp(command, "WRITE ", 6) == 0 && validToken(command + 6)) {
        memcpy(pendingToken, command + 6, sizeof(pendingToken));
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
      } else if (strcmp(command, "FEEDBACK ALLOW") == 0) {
        delay(GREEN_FEEDBACK_DELAY_MS);
        playSuccess();
        status("feedback_applied", true);
      } else if (strcmp(command, "FEEDBACK DENY") == 0) {
        playError();
        status("feedback_applied", true);
      } else {
        status("invalid_command");
      }
      memset(command, 0, sizeof(command));
      commandLength = 0;
    } else if (commandLength < sizeof(command) - 1) {
      command[commandLength++] = value;
    } else {
      commandLength = 0;
      memset(command, 0, sizeof(command));
      status("invalid_command");
    }
  }
}

bool authenticateClassic(uint8_t *uid, uint8_t uidLength) {
  // Block 4 is the first data block in sector 1. Never authenticate/write
  // the sector trailer (block 7).
  return nfc.mifareclassic_AuthenticateBlock(
             uid, uidLength, 4, 0, const_cast<uint8_t *>(CLASSIC_KEY)) != 0;
}

bool readClassicBlock(uint8_t block, uint8_t *output) {
  return nfc.mifareclassic_ReadDataBlock(block, output) != 0;
}

bool readClassicToken(uint8_t *token) {
  uint8_t data[48] = {};
  for (uint8_t block = 4; block <= 6; ++block) {
    if (!readClassicBlock(block, data + (block - 4) * 16))
      return false;
  }
  if (memcmp(data, MARKER, sizeof(MARKER)) != 0)
    return false;
  memcpy(token, data + sizeof(MARKER), TOKEN_BYTES);
  return true;
}

bool writeClassicBlock(uint8_t block, uint8_t *data) {
  return nfc.mifareclassic_WriteDataBlock(block, data) != 0;
}

bool writeClassicToken(const char *token) {
  uint8_t data[48] = {};
  memcpy(data, MARKER, sizeof(MARKER));
  for (uint8_t i = 0; i < TOKEN_BYTES; ++i)
    data[i + sizeof(MARKER)] =
        (nibble(token[i * 2]) << 4) | nibble(token[i * 2 + 1]);

  uint8_t empty[16] = {};
  // Invalidate the marker first, write the payload, then restore the marker.
  if (!writeClassicBlock(4, empty))
    return false;
  if (!writeClassicBlock(5, data + 16) || !writeClassicBlock(6, data + 32))
    return false;
  if (!writeClassicBlock(4, data))
    return false;

  uint8_t check[TOKEN_BYTES] = {};
  return readClassicToken(check) &&
         memcmp(check, data + sizeof(MARKER), TOKEN_BYTES) == 0;
}

void diagnostic() {
  uint32_t version = nfc.getFirmwareVersion();
  if (version != 0) {
    status("reader_connected", true);
  } else {
    status("reader_not_detected");
  }
}

void finishOperation() {
  memset(pendingToken, 0, sizeof(pendingToken));
  writePending = false;
  readPending = false;
  delay(250);
}

void setup() {
  Serial.begin(115200);
  delay(300);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(GREEN_LED_PIN, OUTPUT);
  pinMode(RED_LED_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);
  digitalWrite(GREEN_LED_PIN, LOW);
  digitalWrite(RED_LED_PIN, LOW);
  Wire.begin(SDA_PIN, SCL_PIN);
  nfc.begin();
  Serial.println(F("{\"ok\":true,\"status\":\"ready\",\"device\":\"esp32s3-"
                   "pn532-classic1k\"}"));
  uint32_t firmwareVersion = nfc.getFirmwareVersion();
  if (firmwareVersion != 0) {
    nfc.SAMConfig();
    status("reader_connected", true);
  } else {
    playError();
    status("reader_not_detected");
  }
  lastDiagnostic = millis();
}

void loop() {
  pollCommand();

  unsigned long now = millis();
  if (writePending && now - writeStarted >= CARD_WAIT_MS) {
    finishOperation();
    playError();
    status("write_timeout");
  }
  if (readPending && now - readStarted >= CARD_WAIT_MS) {
    finishOperation();
    playError();
    status("read_timeout");
  }
  if (now - lastDiagnostic >= 5000) {
    lastDiagnostic = now;
    diagnostic();
  }
  if (!writePending && !readPending)
    return;

  uint8_t uid[7] = {};
  uint8_t uidLength = 0;
  if (!nfc.readPassiveTargetID(PN532_MIFARE_ISO14443A, uid, &uidLength, 100))
    return;

  if (!authenticateClassic(uid, uidLength)) {
    playError();
    status("unsupported_card_or_auth_failed");
    finishOperation();
    return;
  }

  if (writePending) {
    if (writeClassicToken(pendingToken)) {
      Serial.println(F("{\"ok\":true,\"written\":true}"));
      playSuccess();
    } else {
      playError();
      status("write_or_verification_failed");
    }
    finishOperation();
    return;
  }

  uint8_t token[TOKEN_BYTES] = {};
  if (readClassicToken(token)) {
    static constexpr char HEX_DIGITS[] = "0123456789abcdef";
    Serial.print(F("{\"ok\":true,\"token\":\""));
    for (uint8_t i = 0; i < TOKEN_BYTES; ++i) {
      Serial.print(HEX_DIGITS[token[i] >> 4]);
      Serial.print(HEX_DIGITS[token[i] & 0x0F]);
    }
    Serial.println(F("\",\"reader\":\"ESP32-S3 PN532 Classic1K\"}"));
    // The desktop checks this token against the database before granting access.
    // It sends FEEDBACK ALLOW or FEEDBACK DENY after that decision.
  } else {
    playError();
    status("card_not_provisioned");
  }
  finishOperation();
}
