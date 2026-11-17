#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>

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
<p>兩條單向道、兩組燈。第一版：手動模擬鏡頭計數。車多的一邊延長綠燈。</p>
<form id="form"><label>A 道等候車輛（0–99）<input id="ns" type="number" min="0" max="99" step="1" value="0" required></label>
<label>B 道等候車輛（0–99）<input id="ew" type="number" min="0" max="99" step="1" value="0" required></label>
<button>套用車量並持續傳送</button></form>
<button id="auto">恢復固定時間循環</button><p id="status" role="status">尚未傳送指令</p>
<p>綠燈 10–20 秒，黃燈 3 秒，全紅 2 秒。時間在下一次綠燈開始時更新。</p>
<p>請保持此頁在前景。停止傳送 5 秒後，下一次綠燈使用固定 10 秒。</p>
<small>顯示的是 ESP32 接收狀態；此版本未接收 Arduino 燈號回報。手機鏡頭自動識別尚未實作。</small>
<script>
const status=document.querySelector('#status');let counts=null,busy=false;
async function send(path,body){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body,signal:AbortSignal.timeout(3000)});if(!r.ok)throw Error(await r.text());return r.text()}
async function heartbeat(){if(!counts||busy)return;busy=true;try{await send('/api/counts',new URLSearchParams(counts));status.textContent='ESP32 已接收車量：A 道 '+counts.ns+'、B 道 '+counts.ew;}catch(e){status.textContent='傳送失敗，請檢查 Wi-Fi：'+e.message;}finally{busy=false;}}
document.querySelector('#form').onsubmit=e=>{e.preventDefault();if(busy)return;counts={ns:document.querySelector('#ns').value,ew:document.querySelector('#ew').value};heartbeat();};
document.querySelector('#auto').onclick=async()=>{if(busy)return;counts=null;busy=true;try{await send('/api/auto','');status.textContent='ESP32 已接收固定時間模式要求';}catch(e){status.textContent='傳送失敗；停止車量傳送後將自動回復固定時間';}finally{busy=false;}};
setInterval(heartbeat,1000);
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
void setup() {
  Serial.begin(115200);
  uno.begin(9600, SERIAL_8N1, 16, 17); // RX unused; TX GPIO17 -> Uno D10.
  WiFi.mode(WIFI_AP);
  if (!WiFi.softAP(SSID, PASSWORD)) {
    Serial.println("Wi-Fi AP failed; restart ESP32.");
    while (true) delay(1000);
  }
  Serial.print("Phone page: http://"); Serial.println(WiFi.softAPIP());
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
void loop() { server.handleClient(); }
