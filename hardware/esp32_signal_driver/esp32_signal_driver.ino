/*
 * Smart Traffic — ESP32 signal-head driver.
 *
 * Polls the backend's /api/signals/status endpoint over WiFi and mirrors the
 * light of each approach on three GPIO pins. The control logic stays in the
 * backend; this board only shows the result.
 *
 * Failsafe: if the backend cannot be reached three times in a row, every
 * approach blinks yellow ("signal out of service") instead of holding the
 * last state.
 *
 * Board: "ESP32 Dev Module". No extra libraries needed.
 * Wiring: LED anode -> 220 ohm resistor -> GPIO pin, cathode -> GND.
 */

#include <HTTPClient.h>
#include <WiFi.h>

// ---------------------------------------------------------------- settings
const char *WIFI_SSID = "YOUR_WIFI_NAME";
const char *WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char *BACKEND_HOST = "192.168.1.5";  // laptop / Pi running the backend
const uint16_t BACKEND_PORT = 8000;

const uint32_t POLL_INTERVAL_MS = 200;   // 5 Hz
const uint32_t REQUEST_TIMEOUT_MS = 2000;
const uint8_t FAILS_BEFORE_FAILSAFE = 3;
const uint32_t BLINK_INTERVAL_MS = 500;

struct Road {
  const char *name;
  uint8_t redPin;
  uint8_t yellowPin;
  uint8_t greenPin;
};

// Same pin map as the Raspberry Pi driver (hardware/gpio_driver.py).
Road ROADS[] = {
    {"north", 17, 27, 22},
    {"south", 5, 6, 13},
    {"east", 19, 26, 21},
    {"west", 20, 16, 12},
};
const uint8_t ROAD_COUNT = sizeof(ROADS) / sizeof(ROADS[0]);

// ------------------------------------------------------------------ helpers
void showLight(const Road &road, const String &state) {
  digitalWrite(road.redPin, state == "red" ? HIGH : LOW);
  digitalWrite(road.yellowPin, state == "yellow" ? HIGH : LOW);
  digitalWrite(road.greenPin, state == "green" ? HIGH : LOW);
}

/*
 * Pulls one road's light out of the JSON payload without a JSON library.
 * The payload looks like:
 *   {"active_phase":"NS_GREEN","roads":{"north":{"light":"green",...},...}}
 * so we find "<road>" and then the first "light":"..." after it.
 */
String lightFor(const String &payload, const char *roadName) {
  String key = String("\"") + roadName + "\"";
  int roadAt = payload.indexOf(key);
  if (roadAt < 0) return "";

  int lightAt = payload.indexOf("\"light\":\"", roadAt);
  if (lightAt < 0) return "";
  lightAt += 9;  // skip past "light":"

  int end = payload.indexOf('"', lightAt);
  if (end < 0) return "";
  return payload.substring(lightAt, end);
}

bool fetchStatus(String &payload) {
  if (WiFi.status() != WL_CONNECTED) return false;

  HTTPClient http;
  String url = String("http://") + BACKEND_HOST + ":" + BACKEND_PORT + "/api/signals/status";
  http.setTimeout(REQUEST_TIMEOUT_MS);
  if (!http.begin(url)) return false;

  int code = http.GET();
  bool ok = (code == HTTP_CODE_OK);
  if (ok) payload = http.getString();
  http.end();
  return ok;
}

void failsafeBlink() {
  bool on = (millis() / BLINK_INTERVAL_MS) % 2 == 0;
  for (uint8_t i = 0; i < ROAD_COUNT; i++) {
    showLight(ROADS[i], on ? "yellow" : "off");
  }
}

// -------------------------------------------------------------------- setup
void setup() {
  Serial.begin(115200);
  for (uint8_t i = 0; i < ROAD_COUNT; i++) {
    pinMode(ROADS[i].redPin, OUTPUT);
    pinMode(ROADS[i].yellowPin, OUTPUT);
    pinMode(ROADS[i].greenPin, OUTPUT);
    showLight(ROADS[i], "off");
  }

  // Power-on self test: every LED in turn, so wiring mistakes show up at once.
  const char *colours[] = {"red", "yellow", "green"};
  for (uint8_t c = 0; c < 3; c++) {
    for (uint8_t i = 0; i < ROAD_COUNT; i++) showLight(ROADS[i], colours[c]);
    delay(400);
  }
  for (uint8_t i = 0; i < ROAD_COUNT; i++) showLight(ROADS[i], "off");

  Serial.printf("Connecting to WiFi %s", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    failsafeBlink();
    delay(200);
    Serial.print(".");
  }
  Serial.printf("\nConnected. ESP32 IP: %s\n", WiFi.localIP().toString().c_str());
}

// --------------------------------------------------------------------- loop
void loop() {
  static uint8_t fails = 0;
  static bool offline = false;

  String payload;
  if (fetchStatus(payload)) {
    if (offline) {
      Serial.println("backend back online");
      offline = false;
    }
    fails = 0;
    for (uint8_t i = 0; i < ROAD_COUNT; i++) {
      String state = lightFor(payload, ROADS[i].name);
      showLight(ROADS[i], state.length() ? state : "red");
    }
  } else if (++fails >= FAILS_BEFORE_FAILSAFE) {
    if (!offline) {
      Serial.println("backend unreachable — blinking yellow");
      offline = true;
    }
    failsafeBlink();
  }

  delay(POLL_INTERVAL_MS);
}
