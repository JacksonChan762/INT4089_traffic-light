#include <Arduino.h>
#include <ESPmDNS.h>
#include <WiFi.h>
#include <WebServer.h>
#include <Preferences.h>
#include <ctype.h>
#include <esp_mac.h>
#include <string.h>

// Assumes a classic ESP32-WROOM-32 development board, not ESP32-C3/S3.
constexpr uint16_t GATEWAY_PORT = 80;
constexpr unsigned GATEWAY_VERSION = 1;
WebServer server(GATEWAY_PORT);
HardwareSerial uno(2);

const char PAGE[] PROGMEM = R"HTML(
<!doctype html><html lang="zh-Hant"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>十字路口紅綠燈</title>
<style>body{font:18px system-ui;max-width:540px;margin:40px auto;padding:20px;background:#f1f5f9;color:#152238}input,button{font:inherit;padding:12px;margin:8px 0;box-sizing:border-box;width:100%}button{background:#155e75;color:white;border:0;border-radius:8px}label{display:block;margin-top:20px}#status{padding:16px;background:white;border-radius:8px}</style>
<h1>十字路口紅綠燈</h1>
<p>輸入兩道等候車量，車多的一道可延長綠燈。</p>
<form id="form"><label>A 道等候車輛（0–99）<input id="ns" type="number" min="0" max="99" step="1" value="0" required></label>
<label>B 道等候車輛（0–99）<input id="ew" type="number" min="0" max="99" step="1" value="0" required></label>
<button>套用車量並持續傳送</button></form>
<button id="auto">恢復固定時間循環</button><p id="status" role="status">尚未傳送指令</p>
<p>綠燈 10–20 秒，黃燈 3 秒，全紅 2 秒。時間在下一次綠燈開始時更新。</p>
<p>請保持此頁在前景。停止傳送 5 秒後，下一次綠燈使用固定 10 秒。</p>
<small>顯示的是 ESP32 接收狀態；此版本未接收 Arduino 燈號回報。相機計數請使用電腦上的瀏覽器控制台。</small>
<script>
const output = document.querySelector('#status');
let counts = null, busy = false, fixedPending = false, revision = 0;
async function heartbeat() {
  if (busy || (!fixedPending && (!counts || document.hidden))) return;
  const currentRevision = revision;
  const pendingCounts = counts;
  const sendFixed = fixedPending;
  fixedPending = false;
  busy = true;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 3000);
  try {
    const response = await fetch(sendFixed ? '/api/auto' : '/api/counts', {
      method: 'POST',
      body: sendFixed ? new URLSearchParams() : new URLSearchParams(pendingCounts),
      signal: controller.signal,
    });
    if (!response.ok) throw Error(await response.text());
    if (currentRevision === revision) output.textContent = sendFixed ? 'ESP32 已接收固定時間模式要求' :
      'ESP32 已接收車量：A 道 ' + pendingCounts.ns + '、B 道 ' + pendingCounts.ew;
  } catch (error) {
    if (currentRevision === revision) output.textContent = '傳送失敗，請檢查 Wi-Fi：' + error.message;
  } finally {
    clearTimeout(timer);
    busy = false;
    if (currentRevision !== revision) void heartbeat();
  }
}
document.querySelector('#form').onsubmit = event => {
  event.preventDefault();
  counts = {ns: document.querySelector('#ns').valueAsNumber, ew: document.querySelector('#ew').valueAsNumber};
  fixedPending = false;
  revision++;
  void heartbeat();
};
document.querySelector('#auto').onclick = () => {
  counts = null;
  fixedPending = true;
  revision++;
  void heartbeat();
};
document.addEventListener('visibilitychange', heartbeat);
setInterval(heartbeat, 1000);
</script></html>)HTML";

bool readCount(const String &s, unsigned &value) {
  if (s.length() == 0 || s.length() > 2) return false;
  value = 0;
  for (unsigned i = 0; i < s.length(); ++i) {
    if (s[i] < '0' || s[i] > '9') return false;
    value = value * 10 + s[i] - '0';
  }
  return value <= 99;
}
constexpr char WIFI_NAMESPACE[] = "traffic-wifi";
constexpr char WIFI_KEY[] = "credentials";
constexpr unsigned long WIFI_RETRY_MS = 30000;
constexpr unsigned long DISCOVERY_RETRY_MS = 10000;

// Keep the stored layout so existing Wi-Fi settings survive a firmware upload.
struct WifiCredentials {
  char ssid[33];
  char password[65];
};

enum class ConsoleStep { Command, Ssid, Password };

WifiCredentials station = {};
WifiCredentials pending = {};
ConsoleStep consoleStep = ConsoleStep::Command;
unsigned long lastStationAttempt = 0;
IPAddress reportedStationIP;
char gatewayId[13] = {};
char gatewayHostname[sizeof("traffic-light-xxxxxx")] = {};
bool discoveryStarted = false;
unsigned long lastDiscoveryAttempt = 0;

void initializeGatewayIdentity() {
  uint8_t mac[6];
  if (esp_efuse_mac_get_default(mac) != ESP_OK) {
    Serial.println("Could not read the ESP32 identity. Automatic discovery is unavailable.");
    return;
  }
  for (size_t i = 0; i < sizeof(mac); ++i) {
    snprintf(gatewayId + i * 2, 3, "%02x", static_cast<unsigned>(mac[i]));
  }
  snprintf(gatewayHostname, sizeof(gatewayHostname), "traffic-light-%s", gatewayId + 6);
}

void startGatewayDiscovery() {
  if (!gatewayId[0]) return;
  // ESPmDNS exposes the checked addServiceTxt overload for mutable C strings.
  char service[] = "traffic-light";
  char protocol[] = "tcp";
  char idKey[] = "id";
  char versionKey[] = "v";
  char version[11];
  snprintf(version, sizeof(version), "%u", GATEWAY_VERSION);
  discoveryStarted = MDNS.begin(gatewayHostname) &&
    MDNS.addService(service, protocol, GATEWAY_PORT) &&
    MDNS.addServiceTxt(service, protocol, idKey, gatewayId) &&
    MDNS.addServiceTxt(service, protocol, versionKey, version);
  lastDiscoveryAttempt = millis();
  if (!discoveryStarted) {
    MDNS.end();
    Serial.println("Could not start gateway discovery. Retrying shortly.");
  }
}

void stopGatewayDiscovery() {
  if (!discoveryStarted) return;
  MDNS.end();
  discoveryStarted = false;
}

IPAddress stationAddress() {
  return WiFi.status() == WL_CONNECTED ? WiFi.localIP() : IPAddress();
}

void printGatewayAddress(const IPAddress &address) {
  Serial.print("Gateway on computer Wi-Fi: http://");
  Serial.println(address);
}

void printWifiStatus() {
  const IPAddress address = stationAddress();
  if (address != IPAddress()) {
    printGatewayAddress(address);
  } else if (station.ssid[0]) {
    Serial.println("Waiting for Wi-Fi. Check the hotspot/router or type wifi to reconfigure.");
  } else {
    Serial.println("Wi-Fi setup required. Type wifi to configure the computer's network.");
  }
}

bool validStationPassword(const char *password, size_t length) {
  if (length == 0) return true; // Open network.
  if (length < 8 || length > 64) return false;
  for (size_t i = 0; i < length; ++i) {
    const unsigned char c = password[i];
    if (c < 32 || c > 126 || (length == 64 && !isxdigit(c))) return false;
  }
  return true;
}

bool saveWifiCredentials(const WifiCredentials &credentials) {
  Preferences preferences;
  if (!preferences.begin(WIFI_NAMESPACE)) return false;
  const bool saved = preferences.putBytes(WIFI_KEY, &credentials, sizeof(credentials)) == sizeof(credentials);
  preferences.end();
  return saved;
}

void handleConsoleLine(const char *line, size_t length) {
  switch (consoleStep) {
    case ConsoleStep::Command:
      if (strcmp(line, "wifi") == 0) {
        pending = {};
        consoleStep = ConsoleStep::Ssid;
        Serial.println("Enter the 2.4 GHz Wi-Fi name (SSID), then press Enter.");
      } else if (strcmp(line, "status") == 0) {
        printWifiStatus();
      } else if (length) {
        Serial.println("USB console commands: wifi, status.");
      }
      return;

    case ConsoleStep::Ssid:
      if (length == 0 || length >= sizeof(pending.ssid)) {
        Serial.println("SSID must be 1-32 bytes. Enter the Wi-Fi name again.");
        return;
      }
      memcpy(pending.ssid, line, length + 1);
      consoleStep = ConsoleStep::Password;
      Serial.println("Enter the Wi-Fi password (empty for an open network), then press Enter.");
      return;

    case ConsoleStep::Password:
      if (!validStationPassword(line, length)) {
        Serial.println("Use an 8-63 character password or a 64-digit hexadecimal key. Try again.");
        return;
      }
      memcpy(pending.password, line, length + 1);
      const bool saved = saveWifiCredentials(pending);
      pending = {};
      consoleStep = ConsoleStep::Command;
      if (saved) {
        Serial.println("Wi-Fi settings saved. Restarting.");
        Serial.flush();
        ESP.restart();
      } else {
        Serial.println("Could not save Wi-Fi settings. Type wifi to retry.");
      }
      return;
  }
}

void readConsole() {
  static char line[sizeof(pending.password)] = {};
  static size_t length = 0;
  static bool invalid = false;
  static bool afterCR = false;

  // Limit work per loop so USB input cannot starve the HTTP server.
  for (unsigned remaining = 64; remaining && Serial.available(); --remaining) {
    const int input = Serial.read();
    if (input < 0) break;
    const char c = static_cast<char>(input);
    const bool trailingLF = afterCR && c == '\n';
    afterCR = c == '\r';
    if (trailingLF) continue;
    if (c == '\r' || c == '\n') {
      if (invalid) {
        Serial.println("Invalid input line. Enter the requested value again.");
      } else {
        line[length] = '\0';
        handleConsoleLine(line, length);
      }
      memset(line, 0, sizeof(line));
      length = 0;
      invalid = false;
    } else if (invalid) {
      continue;
    } else if (c == '\b' || c == '\x7f') {
      if (length) --length;
    } else if (input < 32 || length == sizeof(line) - 1) {
      invalid = true;
    } else {
      line[length++] = c;
    }
  }
}

void startWifi() {
  Preferences preferences;
  if (preferences.begin(WIFI_NAMESPACE, true)) {
    if (preferences.getBytesLength(WIFI_KEY) == sizeof(station)) {
      preferences.getBytes(WIFI_KEY, &station, sizeof(station));
    }
    preferences.end();
  }
  station.ssid[sizeof(station.ssid) - 1] = '\0';
  station.password[sizeof(station.password) - 1] = '\0';
  WiFi.persistent(false);
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  Serial.println("USB console commands: wifi, status.");
  if (station.ssid[0]) {
    Serial.println("Connecting to the configured Wi-Fi network...");
    WiFi.begin(station.ssid, station.password);
    lastStationAttempt = millis();
  } else {
    printWifiStatus();
  }
}

void setup() {
  Serial.begin(115200);
  uno.begin(9600, SERIAL_8N1, 16, 17); // RX unused; TX GPIO17 -> Uno D10.
  initializeGatewayIdentity();
  server.on("/", HTTP_GET, []() { server.send_P(200, "text/html; charset=utf-8", PAGE); });
  server.on("/api/gateway", HTTP_GET, []() {
    server.sendHeader("Cache-Control", "no-store");
    if (!gatewayId[0]) {
      server.send(503, "text/plain", "Gateway identity unavailable");
      return;
    }
    char body[96];
    snprintf(body, sizeof(body), "{\"id\":\"%s\",\"service\":\"int4089-traffic-light\",\"version\":%u}",
             gatewayId, GATEWAY_VERSION);
    server.send(200, "application/json", body);
  });
  server.on("/api/counts", HTTP_POST, []() {
    unsigned ns, ew;
    if (!readCount(server.arg("ns"), ns) || !readCount(server.arg("ew"), ew)) {
      server.send(400, "text/plain", "ns and ew must be integers from 0 to 99"); return;
    }
    uno.printf("C,%u,%u\n", ns, ew);
    server.send(200, "text/plain", "Accepted by ESP32");
  });
  server.on("/api/auto", HTTP_POST, []() {
    uno.print("A\n"); server.send(200, "text/plain", "Accepted by ESP32");
  });
  server.onNotFound([]() { server.send(404, "text/plain", "Not found"); });
  startWifi();
}
void loop() {
  readConsole();
  const IPAddress address = stationAddress();
  if (address != reportedStationIP) {
    stopGatewayDiscovery();
    if (address == IPAddress()) {
      server.stop();
      Serial.println("Gateway Wi-Fi disconnected. Check the computer's network.");
    } else {
      if (reportedStationIP == IPAddress()) server.begin();
      printGatewayAddress(address);
      startGatewayDiscovery();
    }
    reportedStationIP = address;
  }
  if (address != IPAddress()) {
    if (gatewayId[0] && !discoveryStarted && millis() - lastDiscoveryAttempt >= DISCOVERY_RETRY_MS) {
      startGatewayDiscovery();
    }
    server.handleClient();
    return;
  }
  if (station.ssid[0] && millis() - lastStationAttempt >= WIFI_RETRY_MS) {
    WiFi.reconnect();
    lastStationAttempt = millis();
  }
  delay(1);
}
