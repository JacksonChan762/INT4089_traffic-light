#include <Arduino.h>
#include <ESPmDNS.h>
#include <WiFi.h>
#include <WebServer.h>
#include <Preferences.h>
#include <ctype.h>
#include <esp_mac.h>
#include <limits.h>
#include <string.h>

// Assumes a classic ESP32-WROOM-32 development board, not ESP32-C3/S3.
constexpr uint16_t GATEWAY_PORT = 80;
constexpr unsigned GATEWAY_VERSION = 1;
WebServer server(GATEWAY_PORT);
HardwareSerial uno(2);

const char PAGE[] PROGMEM = R"HTML(
<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Traffic Light Control</title>
<style>
*{box-sizing:border-box}
body{font:16px/1.5 system-ui,sans-serif;max-width:620px;margin:0 auto;padding:clamp(16px,5vw,36px);background:#f1f5f9;color:#152238}
h1,h2{line-height:1.2;margin:0 0 12px}h2{font-size:1.25rem}
section{margin:16px 0;padding:clamp(14px,4vw,24px);background:white;border:1px solid #d7e1e9;border-radius:12px}
.counts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
label{display:block;font-weight:600}
input,button{display:block;width:100%;font:inherit;padding:10px 12px;border-radius:7px;min-height:44px}
input{border:1px solid #a6b6c3;color:inherit;margin-top:4px}
button{margin-top:10px;background:#155e75;color:white;border:1px solid transparent;cursor:pointer}
button.secondary{background:#edf4f7;color:#16445a;border-color:#cbdde6}
button:focus-visible,input:focus-visible{outline:2px solid #006bae;outline-offset:2px}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:8px 4px;border-bottom:1px solid #d7e1e9}
td,thead th:not(:first-child){text-align:right;white-space:nowrap}
#status{margin-bottom:0;padding:10px 12px;background:#edf4f7;border-radius:7px}
.note{color:#46596a;font-size:.92rem;margin-bottom:0}
dl{margin-bottom:0;font-variant-numeric:tabular-nums}
dl div{display:flex;flex-wrap:wrap;justify-content:space-between;gap:4px 12px;padding:7px 0;border-top:1px solid #d7e1e9}
dd{margin:0;font-weight:600}
</style></head><body>
<main>
<h1>Traffic Light Control</h1>
<section aria-labelledby="counts-heading">
<h2 id="counts-heading">Waiting cars</h2>
<form id="form">
  <div class="counts">
    <label>Road A<input id="ns" type="number" min="0" max="99" step="1" value="0" required></label>
    <label>Road B<input id="ew" type="number" min="0" max="99" step="1" value="0" required></label>
  </div>
  <button type="submit">Apply and keep sending</button>
</form>
<button id="auto" type="button" class="secondary">Restore fixed timing</button>
<p id="status" role="status">No command sent yet.</p>
<p class="note">Keep this page in the foreground. After 5 seconds without counts, the Uno uses a 10-second duration from the next green phase.</p>
</section>
<section aria-labelledby="uno-heading">
<h2 id="uno-heading">Uno State</h2>
<button id="check-uno" type="button" class="secondary">Check Uno state</button>
<p id="uno-status" role="status">Check the Uno for its current signal phase.</p>
<dl id="uno-details" hidden>
  <div><dt>Current phase</dt><dd id="uno-phase"></dd></div>
  <div><dt>Phase duration</dt><dd id="uno-duration"></dd></div>
  <div><dt>Time remaining</dt><dd id="uno-remaining"></dd></div>
  <div><dt>Next green</dt><dd id="uno-counts"></dd></div>
</dl>
</section>
<section aria-labelledby="timing-heading">
<h2 id="timing-heading">Planned signal timing</h2>
<p id="plan-source">Based on the entered counts.</p>
<table>
  <thead><tr><th scope="col">Road</th><th scope="col">Green</th><th scope="col">Yellow</th><th scope="col">Red</th></tr></thead>
  <tbody>
    <tr><th scope="row">A</th><td id="green-a">10 s</td><td id="yellow-a">3 s</td><td id="red-a">17 s</td></tr>
    <tr><th scope="row">B</th><td id="green-b">10 s</td><td id="yellow-b">3 s</td><td id="red-b">17 s</td></tr>
  </tbody>
</table>
<p class="note">Both roads are red for 2 seconds after each yellow. The Uno sets each green duration when that phase begins.</p>
<p class="note">Check the Uno State above for actual phase times.</p>
</section>
</main>
<script>
const form = document.getElementById('form');
const roadA = document.getElementById('ns');
const roadB = document.getElementById('ew');
const output = document.getElementById('status');
const planSource = document.getElementById('plan-source');
const checkUno = document.getElementById('check-uno');
const unoStatus = document.getElementById('uno-status');
const unoDetails = document.getElementById('uno-details');
const phases = ['All red before Road A', 'Road A green', 'Road A yellow',
  'All red before Road B', 'Road B green', 'Road B yellow'];
const yellowSeconds = 3;
const allRedSeconds = 2;
let counts = null, busy = false, fixedPending = false, revision = 0;
let monitoringUno = false, unoRequest = null;

function selectedCounts() {
  if (!roadA.validity.valid || !roadB.validity.valid) return null;
  return {ns: roadA.valueAsNumber, ew: roadB.valueAsNumber};
}

function greenSeconds(ownCount, otherCount) {
  return 10 + 2 * Math.min(5, Math.max(0, ownCount - otherCount));
}

function showPlan(selection, fixed = false) {
  const greenA = selection ? greenSeconds(selection.ns, selection.ew) : null;
  const greenB = selection ? greenSeconds(selection.ew, selection.ns) : null;
  const redOffset = yellowSeconds + 2 * allRedSeconds;
  const duration = {
    'green-a': greenA, 'green-b': greenB,
    'yellow-a': yellowSeconds, 'yellow-b': yellowSeconds,
    'red-a': selection ? greenB + redOffset : null,
    'red-b': selection ? greenA + redOffset : null,
  };
  for (const [id, seconds] of Object.entries(duration)) {
    document.getElementById(id).textContent = seconds === null ? '—' : seconds + ' s';
  }
  planSource.textContent = fixed ? 'Fixed timing preview.' : selection ? 'Based on the entered counts.' :
    'Enter a whole number from 0 to 99 for each road to preview timing.';
}

async function heartbeat() {
  if (busy || unoRequest || (!fixedPending && (!counts || document.hidden))) return;
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
    if (currentRevision === revision) output.textContent = sendFixed ? 'ESP32 received the fixed timing request.' :
      'ESP32 received the counts. Road A: ' + pendingCounts.ns + ', Road B: ' + pendingCounts.ew + '.';
  } catch (error) {
    if (currentRevision === revision) output.textContent = 'Could not send the command. Check the Wi-Fi connection. ' + error.message;
  } finally {
    clearTimeout(timer);
    busy = false;
    if (currentRevision !== revision) void heartbeat();
  }
}

function showUnoStatus(message, available = false) {
  if (unoStatus.textContent !== message) unoStatus.textContent = message;
  unoDetails.hidden = !available;
}

async function refreshUnoState() {
  if (!monitoringUno || document.hidden || busy || unoRequest) return;
  const currentRevision = revision;
  const controller = new AbortController();
  unoRequest = controller;
  const timer = setTimeout(() => controller.abort(), 1000);
  try {
    const response = await fetch('/api/state', {cache: 'no-store', signal: controller.signal});
    if (!response.ok) throw Error();
    const state = await response.json();
    if (!state.available || !phases[state.phase]) throw Error();
    if (!monitoringUno || document.hidden || controller.signal.aborted) return;
    document.getElementById('uno-phase').textContent = phases[state.phase];
    document.getElementById('uno-duration').textContent = state.duration_ms / 1000 + ' s';
    document.getElementById('uno-remaining').textContent = (Math.ceil(state.remaining_ms / 100) / 10).toFixed(1) + ' s';
    document.getElementById('uno-counts').textContent = state.counts_fresh ?
      'Road A: ' + state.ns + ', Road B: ' + state.ew : 'Fixed timing';
    showUnoStatus('Live from the Uno.', true);
  } catch (error) {
    if (monitoringUno && !document.hidden) showUnoStatus('Uno state unavailable. Check the serial connection to the Uno.');
  } finally {
    clearTimeout(timer);
    unoRequest = null;
    if (currentRevision !== revision) void heartbeat();
  }
}

async function tick() {
  await heartbeat();
  await refreshUnoState();
}

form.addEventListener('input', () => showPlan(selectedCounts()));
form.onsubmit = event => {
  event.preventDefault();
  const selection = selectedCounts();
  if (!selection) return;
  counts = selection;
  showPlan(counts);
  fixedPending = false;
  revision++;
  void heartbeat();
};
document.getElementById('auto').onclick = () => {
  counts = null;
  showPlan({ns: 0, ew: 0}, true);
  fixedPending = true;
  revision++;
  void heartbeat();
};
checkUno.onclick = () => {
  monitoringUno = !monitoringUno;
  checkUno.textContent = monitoringUno ? 'Stop checking Uno state' : 'Check Uno state';
  if (monitoringUno) {
    showUnoStatus('Checking Uno state…');
    void refreshUnoState();
  } else {
    unoRequest?.abort();
    showUnoStatus('Uno state check stopped.');
  }
};
document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    unoRequest?.abort();
  } else if (monitoringUno) {
    showUnoStatus('Checking Uno state…');
  }
  void tick();
});
setInterval(tick, 1000);
showPlan(selectedCounts());
</script></body></html>)HTML";

bool readCount(const String &s, unsigned &value) {
  if (s.length() == 0 || s.length() > 2) return false;
  value = 0;
  for (unsigned i = 0; i < s.length(); ++i) {
    if (s[i] < '0' || s[i] > '9') return false;
    value = value * 10 + s[i] - '0';
  }
  return value <= 99;
}

struct UnoState {
  unsigned phase;
  unsigned durationMs;
  unsigned remainingMs;
  unsigned countsFresh;
  unsigned ns;
  unsigned ew;
};

bool readStateField(const char *&cursor, unsigned maximum, unsigned &value) {
  if (*cursor++ != ',' || *cursor < '0' || *cursor > '9') return false;
  value = 0;
  do {
    const unsigned digit = *cursor++ - '0';
    if (value > maximum / 10 || (value == maximum / 10 && digit > maximum % 10)) return false;
    value = value * 10 + digit;
  } while (*cursor >= '0' && *cursor <= '9');
  return true;
}

bool parseUnoState(const char *line, UnoState &state) {
  const char *cursor = line + 1;
  return line[0] == 'S' && readStateField(cursor, 5, state.phase) &&
    readStateField(cursor, UINT_MAX, state.durationMs) && state.durationMs > 0 &&
    readStateField(cursor, state.durationMs, state.remainingMs) &&
    readStateField(cursor, 1, state.countsFresh) && readStateField(cursor, 99, state.ns) &&
    readStateField(cursor, 99, state.ew) && *cursor == '\0';
}

bool requestUnoState(UnoState &state) {
  constexpr size_t MAX_STALE_BYTES = 256;
  constexpr unsigned long REPLY_TIMEOUT_MS = 220;
  for (size_t skipped = 0; skipped < MAX_STALE_BYTES && uno.available(); ++skipped) {
    uno.read();
  }
  if (uno.available() || uno.print("S\n") != 2) return false;

  char line[48];
  size_t used = 0;
  bool invalid = false;
  const unsigned long started = millis();
  while (millis() - started < REPLY_TIMEOUT_MS) {
    const int input = uno.read();
    if (input < 0) {
      delay(1);
    } else if (input == '\n') {
      if (!invalid) {
        if (used > 0 && line[used - 1] == '\r') --used;
        line[used] = '\0';
        if (parseUnoState(line, state)) return true;
      }
      used = 0;
      invalid = false;
    } else if (!invalid) {
      if (used == sizeof(line) - 1 || (input < 32 && input != '\r') || input > 126) {
        invalid = true;
      } else {
        line[used++] = static_cast<char>(input);
      }
    }
  }
  return false;
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
  // RX GPIO16 from Uno D11 through level shifter; TX GPIO17 to Uno D10.
  uno.begin(9600, SERIAL_8N1, 16, 17);
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
  server.on("/api/state", HTTP_GET, []() {
    server.sendHeader("Cache-Control", "no-store");
    UnoState state{};
    if (!requestUnoState(state)) {
      server.send(503, "application/json", "{\"available\":false}");
      return;
    }
    char body[160];
    snprintf(body, sizeof(body), "{\"available\":true,\"phase\":%u,\"duration_ms\":%u,\"remaining_ms\":%u,"
      "\"counts_fresh\":%s,\"ns\":%u,\"ew\":%u}", state.phase, state.durationMs, state.remainingMs,
      state.countsFresh ? "true" : "false", state.ns, state.ew);
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
