#pragma once

const char WIFI_SETUP_PAGE[] PROGMEM = R"HTML(
<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Traffic Light Wi-Fi</title>
<style>
*{box-sizing:border-box}
body{font:16px/1.5 system-ui,sans-serif;max-width:540px;margin:0 auto;padding:clamp(16px,5vw,36px);background:#f1f5f9;color:#152238}
h1{line-height:1.2}
form{padding:clamp(14px,4vw,24px);background:white;border:1px solid #d7e1e9;border-radius:12px}
label{display:block;font-weight:600;margin-bottom:14px}
input,button{display:block;width:100%;min-height:44px;padding:8px 12px;border:1px solid #a6b6c3;border-radius:7px;font:inherit}
input{margin-top:4px}button{background:#155e75;color:white;cursor:pointer}
button:disabled{opacity:.55;cursor:default}
</style></head><body><main>
<h1>Traffic Light Wi-Fi</h1>
<p>Join a 2.4 GHz Wi-Fi network to use the traffic lights from other devices on that network.</p>
<form id="wifi" method="post" action="/api/wifi">
  <label>Network name (SSID)<input name="ssid" maxlength="32" required autocapitalize="none" autocorrect="off" spellcheck="false"></label>
  <label>Wi-Fi password (leave blank for an open network)<input name="password" type="password" maxlength="64" autocomplete="off"></label>
  <button id="connect" type="submit">Connect and save</button>
</form>
<p id="wifi-status" role="status"></p>
<p><a href="/control">Open traffic light controls and phase log</a></p>
</main><script>
const form = document.getElementById('wifi');
const button = document.getElementById('connect');
const status = document.getElementById('wifi-status');
let submitting = false;

async function refresh() {
  if (submitting) return;
  try {
    const response = await fetch('/api/wifi', {cache: 'no-store'});
    if (!response.ok) throw Error();
    const {state, address} = await response.json();
    if (submitting) return;
    button.disabled = state === 'connecting' || state === 'connected';
    if (state === 'connecting') status.textContent = 'Connecting… This can take up to 45 seconds.';
    if (state === 'failed') status.textContent = 'Could not connect. Check the network name, password and 2.4 GHz Wi-Fi, then try again.';
    if (state === 'save_failed') status.textContent = 'Connected briefly, but the ESP32 could not save the settings. Try again.';
    if (state === 'connected') {
      const url = 'http://' + address;
      const link = Object.assign(document.createElement('a'), {href: url, textContent: url});
      status.replaceChildren('Connected. Switch your phone to that Wi-Fi network and open ', link, '.');
    }
  } catch {
    if (!submitting && !status.querySelector('a')) {
      status.textContent = 'Waiting for the ESP32. Check that your phone is still on its hotspot.';
    }
  }
}

form.addEventListener('submit', async event => {
  event.preventDefault();
  submitting = button.disabled = true;
  status.textContent = 'Sending Wi-Fi settings…';
  try {
    const response = await fetch('/api/wifi', {method: 'POST', headers: {'X-Traffic-Wifi-Setup': '1'},
      body: new URLSearchParams(new FormData(form))});
    if (!response.ok) throw Error(await response.text());
    form.elements.password.value = '';
    status.textContent = 'Connecting… This can take up to 45 seconds.';
  } catch (error) {
    status.textContent = error.message;
    button.disabled = false;
  } finally {
    submitting = false;
  }
});
void refresh();
setInterval(refresh, 1500);
</script></body></html>)HTML";
