#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <Preferences.h>
#include <esp_random.h>
#include <ctype.h>

// Assumes a classic ESP32-WROOM-32 development board, not ESP32-C3/S3.
const char *SSID = "TrafficLight-Lab";
const char *PASSWORD = "traffic123";
WebServer server(80);
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
<p><a href="/wifi">設定電腦 Wi-Fi／熱點</a></p>
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
struct WifiCredentials {
  char ssid[33];
  char password[65];
};
WifiCredentials station = {};
String setupToken;
bool restartPending = false;
unsigned long savedAt = 0;
unsigned long lastStationAttempt = 0;
IPAddress reportedStationIP;

const char WIFI_PAGE[] PROGMEM = R"HTML(
<!doctype html><html lang="zh-Hant"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>設定 ESP32 Wi-Fi</title>
<style>body{font:18px system-ui;max-width:540px;margin:40px auto;padding:20px}input,button{font:inherit;margin:8px 0;padding:10px;display:block;box-sizing:border-box;width:100%}</style>
<h1>設定電腦 Wi-Fi／熱點</h1>
<p>電腦需與 ESP32 位於同一網路。請使用支援 2.4 GHz 的 Wi-Fi 或電腦熱點。</p>
<p>ESP32 在該網路的位址：<strong>STATION_ADDRESS</strong></p>
<form action="/wifi" method="post">
<input type="hidden" name="token" value="SETUP_TOKEN">
<label>網路名稱（SSID）<input name="ssid" maxlength="32" required></label>
<label>Wi-Fi 密碼（開放式網路可留空）<input name="password" type="password" maxlength="64" autocomplete="new-password"></label>
<button>儲存並重新連線</button>
</form><p><a href="/">返回手動控制</a></p></html>
)HTML";

bool onSetupNetwork() {
  return server.client().localIP() == WiFi.softAPIP();
}

bool validStationPassword(const String &password) {
  const size_t length = password.length();
  if (length == 0) return true;
  if (length < 8 || length > 64) return false;
  for (size_t i = 0; i < length; ++i) {
    const unsigned char c = password[i];
    if (c < 32 || c > 126 || (length == 64 && !isxdigit(c))) return false;
  }
  return true;
}

void mountWifiSetup() {
  server.on("/wifi", HTTP_GET, []() {
    if (!onSetupNetwork()) {
      server.send(403, "text/plain; charset=utf-8", "請先連上 TrafficLight-Lab，再開啟 http://192.168.4.1/wifi。");
      return;
    }
    String page(FPSTR(WIFI_PAGE));
    page.replace("SETUP_TOKEN", setupToken);
    page.replace("STATION_ADDRESS", WiFi.status() == WL_CONNECTED ? WiFi.localIP().toString() : String("尚未連線"));
    server.sendHeader("Cache-Control", "no-store");
    server.sendHeader("X-Frame-Options", "DENY");
    server.send(200, "text/html; charset=utf-8", page);
  });
  server.on("/wifi", HTTP_POST, []() {
    if (!onSetupNetwork() || server.arg("token") != setupToken) {
      server.send(403, "text/plain; charset=utf-8", "請透過 TrafficLight-Lab 開啟 Wi-Fi 設定頁。");
      return;
    }
    if (restartPending) {
      server.send(409, "text/plain; charset=utf-8", "ESP32 正在重新啟動。");
      return;
    }
    const String ssid = server.arg("ssid");
    const String password = server.arg("password");
    if (ssid.length() == 0 || ssid.length() > 32 || ssid.length() != strlen(ssid.c_str()) || !validStationPassword(password)) {
      server.send(400, "text/plain; charset=utf-8", "請輸入 1–32 位元組的網路名稱，以及有效的 Wi-Fi 密碼。");
      return;
    }
    WifiCredentials next = {};
    ssid.toCharArray(next.ssid, sizeof(next.ssid));
    password.toCharArray(next.password, sizeof(next.password));
    Preferences preferences;
    const bool saved = preferences.begin(WIFI_NAMESPACE) &&
      preferences.putBytes(WIFI_KEY, &next, sizeof(next)) == sizeof(next);
    preferences.end();
    if (!saved) {
      server.send(500, "text/plain; charset=utf-8", "無法儲存 Wi-Fi 設定，請再試一次。");
      return;
    }
    server.sendHeader("Cache-Control", "no-store");
    server.send(200, "text/html; charset=utf-8", "<!doctype html><meta charset=utf-8><p>設定已儲存。ESP32 會重新啟動。請重新連上 TrafficLight-Lab，再<a href=/wifi>查看分配到的 IP</a>，或查看 USB 序列監視器。</p>");
    restartPending = true;
    savedAt = millis();
  });
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
  WiFi.mode(station.ssid[0] ? WIFI_AP_STA : WIFI_AP);
  if (WiFi.softAP(SSID, PASSWORD)) {
    Serial.print("Setup page: http://");
    Serial.print(WiFi.softAPIP());
    Serial.println("/wifi");
  } else {
    Serial.println("Wi-Fi setup AP failed to start.");
  }
  char token[25];
  snprintf(token, sizeof(token), "%08lx%08lx%08lx", static_cast<unsigned long>(esp_random()),
           static_cast<unsigned long>(esp_random()), static_cast<unsigned long>(esp_random()));
  setupToken = token;
  if (station.ssid[0]) {
    Serial.println("Connecting to the configured Wi-Fi network...");
    WiFi.setAutoReconnect(true);
    WiFi.begin(station.ssid, station.password);
    lastStationAttempt = millis();
  }
}

void setup() {
  Serial.begin(115200);
  uno.begin(9600, SERIAL_8N1, 16, 17); // RX unused; TX GPIO17 -> Uno D10.
  startWifi();
  mountWifiSetup();
  server.on("/", HTTP_GET, []() { server.send_P(200, "text/html; charset=utf-8", PAGE); });
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
  server.begin();
}
void loop() {
  server.handleClient();
  const unsigned long now = millis();
  if (restartPending && now - savedAt >= 900) ESP.restart();
  if (!station.ssid[0]) return;
  const bool connected = WiFi.status() == WL_CONNECTED;
  const IPAddress address = connected ? WiFi.localIP() : IPAddress();
  if (address != reportedStationIP) {
    reportedStationIP = address;
    if (connected) {
      Serial.print("Gateway on computer Wi-Fi: http://");
      Serial.println(address);
    } else {
      Serial.println("Gateway Wi-Fi disconnected; setup AP remains available.");
    }
  }
  if (!connected && now - lastStationAttempt >= 30000) {
    WiFi.reconnect();
    lastStationAttempt = now;
  }
}
