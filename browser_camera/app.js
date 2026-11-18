const $ = id => document.getElementById(id);
const video = $("video");
const preview = $("preview");
const overlay = preview.getContext("2d");
const frame = document.createElement("canvas");
const image = frame.getContext("2d");
const source = $("camera-source");
const gatewaySelect = $("gateway-select");
const defaultCamera = source.options[0].textContent;
const roads = [null, null];
const colors = ["#ffce4c", "#70d8ff"];
const secureCamera = window.isSecureContext && navigator.mediaDevices?.getUserMedia;

let stream = null;
let opening = false;
let cameraVersion = 0;
let lastFrame = -Infinity;
let lastAnalysis = -Infinity;
let calibration = null;
let selecting = null;
let drag = null;
let results = null;
let previousCounts = "";
let matchingFrames = 0;
let stableCounts = null;
let lastDetection = -Infinity;
let analyzing = false;
let mode = "idle";
let manualCounts;
let queuedFixed = false;
let sending = false;
let sendVersion = 0;
let gatewayInfo = null;
let pairedGatewayId = null;
let soleCandidateId = null;
let gatewayPollFailed = false;
let pollingGateways = false;
let renderedGateways = "";

function status(id, message) {
  const element = $(id);
  if (element.textContent !== message) element.textContent = message;
}

function activeGateway() {
  if (gatewayPollFailed || !gatewayInfo) return null;
  if (gatewayInfo.mode === "manual") return gatewayInfo;
  return gatewayInfo.gateways.find(gateway => gateway.id === pairedGatewayId) ?? null;
}

function stopGatewayCommands(message) {
  mode = "idle";
  manualCounts = undefined;
  queuedFixed = false;
  sendVersion++;
  status("send-status", message);
}

function renderGateways() {
  const gateways = gatewayPollFailed ? [] : gatewayInfo?.gateways ?? [];
  const active = activeGateway();
  $("gateway-choice").hidden = gateways.length < 2 && !(pairedGatewayId && !active && gateways.length);
  const signature = JSON.stringify(gateways);
  if (signature !== renderedGateways) {
    renderedGateways = signature;
    const prompt = new Option("請選擇 ESP32", "");
    prompt.disabled = true;
    gatewaySelect.replaceChildren(prompt, ...gateways.map(gateway =>
      new Option(`${gateway.name}（${gateway.address}）`, gateway.id)));
  }
  gatewaySelect.value = active?.id ?? "";

  let message;
  if (gatewayPollFailed) {
    message = "無法取得 ESP32 的連線狀態。正在重試。";
  } else if (active) {
    message = active.id ? `已配對 ${active.name}（${active.address}）。` : `使用手動指定的位址 ${active.address}。`;
  } else if (gatewayInfo?.state === "unavailable") {
    message = "無法啟動 ESP32 搜尋。請檢查電腦網路設定，或啟動時指定 ESP32 位址。";
  } else if (pairedGatewayId) {
    message = gateways.length ? "已配對的 ESP32 已離線。請等待它重新連線，或選擇另一台。" :
      "已配對的 ESP32 已離線。等待原裝置重新連線。";
  } else if (gateways.length > 1) {
    message = "找到多台 ESP32。請選擇要控制的裝置。";
  } else if (gateways.length === 1) {
    message = `找到 ${gateways[0].name}。正在確認裝置。`;
  } else {
    message = "正在搜尋同一個 Wi-Fi 網路上的 ESP32。";
  }
  status("gateway-status", message);
  updateControls();
}

async function refreshGateways() {
  if (pollingGateways) return;
  pollingGateways = true;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 2500);
  let next;
  try {
    const response = await fetch("/api/gateways", { signal: controller.signal });
    if (!response.ok) throw new Error("Gateway status unavailable");
    next = await response.json();
  } catch {
    next = null;
  } finally {
    clearTimeout(timeout);
    pollingGateways = false;
  }

  const previous = activeGateway();
  gatewayInfo = next;
  gatewayPollFailed = !next;
  if (!pairedGatewayId && next?.mode === "auto" && next.state !== "unavailable" && next.gateways.length === 1) {
    const id = next.gateways[0].id;
    if (id === soleCandidateId) pairedGatewayId = id;
    soleCandidateId = id;
  } else {
    soleCandidateId = null;
  }
  const active = activeGateway();
  if (previous && (previous.id ?? previous.address) !== (active?.id ?? active?.address)) {
    stopGatewayCommands("原 ESP32 的車量傳送已停止。請重新開始傳送。");
  }
  renderGateways();
}

async function post(path, body = new URLSearchParams(), headers = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 3200);
  try {
    const response = await fetch(path, {
      method: "POST", body, headers, signal: controller.signal,
    });
    if (!response.ok) {
      const message = response.headers.get("Content-Type")?.startsWith("application/json")
        ? (await response.json()).reason : await response.text();
      throw new Error(message);
    }
    return response;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("連線逾時");
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

function changeMode(next, fixed = false) {
  mode = next;
  sendVersion++;
  queuedFixed ||= fixed;
  updateControls();
  void send();
}

async function send() {
  const gateway = activeGateway();
  if (!gateway || sending || (document.hidden && !queuedFixed)) return;
  const fixed = queuedFixed;
  const counts = mode === "manual" ? manualCounts : mode === "camera" && countsAreFresh() && stableCounts;
  if (!fixed && !counts) {
    if (mode === "camera") status("send-status", "等待穩定車量。暫停送出計數。");
    return;
  }
  queuedFixed = false;
  sending = true;
  const version = sendVersion;
  const headers = gateway.id ? { "X-Gateway-ID": gateway.id } : {};
  try {
    await post(fixed ? "/api/auto" : "/api/counts",
      fixed ? new URLSearchParams() : new URLSearchParams({ ns: counts[0], ew: counts[1] }), headers);
    if (version === sendVersion) {
      status("send-status", fixed ? "ESP32 已接收固定時間要求。" :
        "ESP32 已接收" + (mode === "camera" ? "相機" : "手動") +
        "車量。A 道 " + counts[0] + "，B 道 " + counts[1] + "。");
    }
  } catch (error) {
    if (version === sendVersion) status("send-status", "傳送失敗。 " + error.message);
  } finally {
    sending = false;
    if (queuedFixed || version !== sendVersion || (fixed && mode !== "idle")) void send();
  }
}

function freshFrame() {
  return stream && video.readyState >= 2 && video.videoWidth &&
    !stream.getVideoTracks()[0].muted && performance.now() - lastFrame < 1500;
}

function countsAreFresh() {
  return stableCounts && freshFrame() && performance.now() - lastDetection < 1500;
}

function updateControls() {
  $("start-camera").disabled = !secureCamera || opening || !!stream;
  $("stop-camera").disabled = !opening && !stream;
  const ready = !!freshFrame();
  $("select-a").disabled = !ready;
  $("select-b").disabled = !ready;
  $("capture-background").disabled = !ready || roads.some(road => !road) ||
    selecting !== null || (calibration && !calibration.ready);
  const connected = !!activeGateway();
  $("send-camera").disabled = !connected || !countsAreFresh() || mode === "camera";
  $("send-manual").disabled = !connected;
  $("fixed").disabled = !connected;
}

function resetCounts() {
  results = null;
  previousCounts = "";
  matchingFrames = 0;
  stableCounts = null;
  for (const id of ["count-a", "count-b"]) status(id, "—");
  updateControls();
  paintOverlay();
}

function invalidateCalibration() {
  calibration = null;
  resetCounts();
  if (mode === "camera") changeMode("idle", true);
}

function endSelection() {
  selecting = null;
  drag = null;
  preview.classList.remove("selecting");
  $("select-a").setAttribute("aria-pressed", "false");
  $("select-b").setAttribute("aria-pressed", "false");
}

function closeCamera(message) {
  cameraVersion++;
  opening = false;
  if (stream) stream.getTracks().forEach(track => track.stop());
  stream = null;
  video.srcObject = null;
  $("stage").hidden = true;
  lastFrame = -Infinity;
  roads.fill(null);
  endSelection();
  invalidateCalibration();
  status("camera-status", message);
  updateControls();
}

function cameraError(error) {
  if (error.name === "NotAllowedError") return "請在網站及系統設定中允許相機，再試一次。";
  if (error.name === "NotFoundError") return "找不到相機。請連接相機或選擇其他鏡頭。";
  if (error.name === "NotReadableError") return "無法讀取相機。請關閉其他使用相機的程式。";
  if (error.name === "OverconstrainedError") return "此相機已不可用。請改用自動選擇。";
  return "無法開啟相機。 " + error.message;
}

async function refreshCameras(version) {
  try {
    const devices = await navigator.mediaDevices.enumerateDevices();
    if (cameraVersion !== version || !stream) return;
    const activeId = stream.getVideoTracks()[0].getSettings().deviceId;
    source.replaceChildren(new Option(defaultCamera, ""));
    let number = 0;
    for (const device of devices) {
      if (device.kind !== "videoinput" || !device.deviceId) continue;
      number++;
      source.add(new Option(device.label || "相機 " + number, device.deviceId));
    }
    if (Array.from(source.options).some(option => option.value === activeId)) source.value = activeId;
  } catch {
    // The selected stream is usable even if the browser will not list cameras.
  }
}

async function startCamera() {
  if (!secureCamera || document.hidden) return;
  const deviceId = source.value;
  closeCamera("等待相機權限…");
  const version = cameraVersion;
  opening = true;
  updateControls();
  try {
    const next = await navigator.mediaDevices.getUserMedia({
      video: {
        width: { ideal: 640 },
        height: { ideal: 480 },
        ...(deviceId ? { deviceId: { exact: deviceId } } : { facingMode: { ideal: "environment" } }),
      },
      audio: false,
    });
    if (version !== cameraVersion) {
      next.getTracks().forEach(track => track.stop());
      return;
    }
    stream = next;
    lastFrame = performance.now();
    const track = next.getVideoTracks()[0];
    track.addEventListener("ended", () => {
      if (stream === next) closeCamera("相機已中斷。請重新開啟。");
    });
    $("stage").hidden = false;
    video.srcObject = next;
    opening = false;
    updateControls();
    await video.play();
    if (version !== cameraVersion) return;
    status("camera-status", "請框選兩道各自的等候區。");
    watchFrames(next);
    void refreshCameras(version);
  } catch (error) {
    if (version === cameraVersion) closeCamera(cameraError(error));
  }
}

function watchFrames(activeStream) {
  let previousTime = -1;
  const observedFrames = typeof video.requestVideoFrameCallback === "function";
  function nextFrame() {
    if (stream !== activeStream) return;
    if (video.videoWidth && video.readyState >= 2 &&
        (observedFrames || video.currentTime !== previousTime)) {
      previousTime = video.currentTime;
      acceptFrame();
    }
    if (observedFrames) video.requestVideoFrameCallback(nextFrame);
    else requestAnimationFrame(nextFrame);
  }
  if (observedFrames) video.requestVideoFrameCallback(nextFrame);
  else requestAnimationFrame(nextFrame);
}

function acceptFrame() {
  const now = performance.now();
  lastFrame = now;
  const scale = Math.min(1, 640 / Math.max(video.videoWidth, video.videoHeight));
  const width = Math.max(1, Math.round(scale * video.videoWidth));
  const height = Math.max(1, Math.round(scale * video.videoHeight));
  if (frame.width !== width || frame.height !== height) {
    frame.width = preview.width = width;
    frame.height = preview.height = height;
    if (roads.some(Boolean) || drag) status("camera-status", "畫面尺寸已變更。請重新框選兩道。");
    roads.fill(null);
    endSelection();
    invalidateCalibration();
  }
  updateControls();
  if (calibration?.ready && !analyzing && now - lastAnalysis >= 250 && freshFrame()) {
    lastAnalysis = now;
    void analyze(calibration);
  }
}

function jpegFrame() {
  image.drawImage(video, 0, 0, frame.width, frame.height);
  return new Promise((resolve, reject) => frame.toBlob(blob => {
    if (blob) resolve(blob);
    else reject(new Error("無法擷取相機畫面"));
  }, "image/jpeg", .8));
}

async function captureBackground() {
  if (!freshFrame() || roads.some(road => !road)) return;
  invalidateCalibration();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  const token = Array.from(bytes, byte => byte.toString(16).padStart(2, "0")).join("");
  const selected = { token, ready: false };
  calibration = selected;
  updateControls();
  status("camera-status", "正在儲存空景…");
  try {
    await post("/api/camera/background", await jpegFrame(), { "X-Camera-Session": token });
    if (calibration !== selected) return;
    selected.ready = true;
    status("camera-status", "空景已儲存。放回分開的模型車，等待車量穩定。");
  } catch (error) {
    if (calibration !== selected) return;
    calibration = null;
    status("camera-status", "無法儲存空景。 " + error.message);
  }
  updateControls();
}

function roadHeader({ x, y, w, h }) {
  return [x, y, w, h].join(",");
}

async function analyze(selected) {
  analyzing = true;
  const headers = {
    "X-Camera-Session": selected.token,
    "X-Road-A": roadHeader(roads[0]),
    "X-Road-B": roadHeader(roads[1]),
    "X-Threshold": $("threshold").value,
    "X-Min-Area": $("min-area").value,
  };
  try {
    const blob = await jpegFrame();
    if (calibration !== selected) return;
    const response = await post("/api/camera/analyze", blob, headers);
    const detection = await response.json();
    if (calibration !== selected || !freshFrame()) return;
    if (detection.reason) {
      resetCounts();
      status("camera-status", detection.reason);
      return;
    }
    results = detection;
    lastDetection = performance.now();
    const signature = detection.counts.join(",");
    matchingFrames = signature === previousCounts ? matchingFrames + 1 : 1;
    previousCounts = signature;
    stableCounts = matchingFrames >= 3 ? detection.counts : null;
    status("count-a", String(detection.counts[0]));
    status("count-b", String(detection.counts[1]));
    status("camera-status", stableCounts ? "車量已穩定。" : "等待三次相同計數。");
    updateControls();
    paintOverlay();
  } catch (error) {
    if (calibration === selected) {
      resetCounts();
      status("camera-status", "影像分析失敗。 " + error.message);
    }
  } finally {
    analyzing = false;
  }
}

function paintOverlay() {
  overlay.clearRect(0, 0, preview.width, preview.height);
  overlay.lineWidth = 2;
  for (const [index, road] of roads.entries()) {
    if (!road) continue;
    overlay.strokeStyle = colors[index];
    overlay.strokeRect(road.x, road.y, road.w, road.h);
    overlay.font = "bold 16px system-ui";
    overlay.fillStyle = "#142739";
    overlay.fillRect(road.x, road.y, 23, 22);
    overlay.fillStyle = colors[index];
    overlay.fillText(index === 0 ? "A" : "B", road.x + 5, road.y + 16);
  }
  overlay.strokeStyle = "#55f389";
  for (const lane of results?.boxes ?? []) {
    for (const [x, y, width, height] of lane) overlay.strokeRect(x, y, width, height);
  }
  if (drag) {
    const road = dragRoad();
    overlay.strokeStyle = colors[selecting];
    overlay.strokeRect(road.x, road.y, road.w, road.h);
  }
}

function selectRoad(index) {
  if (!freshFrame()) return;
  endSelection();
  invalidateCalibration();
  selecting = index;
  preview.classList.add("selecting");
  $(index === 0 ? "select-a" : "select-b").setAttribute("aria-pressed", "true");
  status("camera-status", "請在畫面拖曳框選 " + (index === 0 ? "A" : "B") + " 道。");
  updateControls();
}

function position(event) {
  const box = preview.getBoundingClientRect();
  return {
    x: Math.round(Math.max(0, Math.min(1, (event.clientX - box.left) / box.width)) * preview.width),
    y: Math.round(Math.max(0, Math.min(1, (event.clientY - box.top) / box.height)) * preview.height),
  };
}

function dragRoad() {
  const { start, end } = drag;
  return { x: Math.min(start.x, end.x), y: Math.min(start.y, end.y),
    w: Math.abs(start.x - end.x), h: Math.abs(start.y - end.y) };
}

function overlaps(a, b) {
  return b && a.x < b.x + b.w && b.x < a.x + a.w &&
    a.y < b.y + b.h && b.y < a.y + a.h;
}

preview.addEventListener("pointerdown", event => {
  if (selecting === null || !event.isPrimary || event.button !== 0) return;
  const point = position(event);
  drag = { id: event.pointerId, start: point, end: point };
  preview.setPointerCapture(event.pointerId);
});

preview.addEventListener("pointermove", event => {
  if (drag?.id !== event.pointerId) return;
  drag.end = position(event);
  paintOverlay();
});

preview.addEventListener("pointerup", event => {
  if (drag?.id !== event.pointerId) return;
  drag.end = position(event);
  const road = dragRoad();
  drag = null;
  if (road.w < 10 || road.h < 10 || overlaps(road, roads[1 - selecting])) {
    status("camera-status", "框選範圍至少需 10 × 10 像素，且兩道不可重疊。請重新框選。");
  } else {
    roads[selecting] = road;
    endSelection();
    status("camera-status", roads.every(Boolean) ? "清空兩道後，擷取空景。" : "請框選另一道。");
  }
  paintOverlay();
  updateControls();
});

preview.addEventListener("lostpointercapture", () => {
  if (drag) {
    drag = null;
    paintOverlay();
  }
});

$("start-camera").addEventListener("click", startCamera);
$("stop-camera").addEventListener("click", () => closeCamera("相機已關閉。"));
source.addEventListener("change", () => { if (stream || opening) void startCamera(); });
$("select-a").addEventListener("click", () => selectRoad(0));
$("select-b").addEventListener("click", () => selectRoad(1));
$("capture-background").addEventListener("click", captureBackground);
$("send-camera").addEventListener("click", () => {
  if (activeGateway() && countsAreFresh()) changeMode("camera");
});
$("fixed").addEventListener("click", () => {
  if (activeGateway()) changeMode("idle", true);
});

gatewaySelect.addEventListener("change", () => {
  if (gatewayInfo?.mode !== "auto" ||
      !gatewayInfo.gateways.some(gateway => gateway.id === gatewaySelect.value) ||
      pairedGatewayId === gatewaySelect.value) return;
  pairedGatewayId = gatewaySelect.value;
  stopGatewayCommands("已選擇 ESP32。請開始傳送要使用的車量。");
  renderGateways();
});

for (const id of ["threshold", "min-area"]) {
  const input = $(id);
  input.addEventListener("change", () => {
    const value = input.valueAsNumber;
    input.value = Number.isFinite(value)
      ? Math.max(Number(input.min), Math.min(Number(input.max), Math.round(value)))
      : input.defaultValue;
    if (calibration) {
      calibration = { ...calibration };
      resetCounts();
    }
  });
}

$("manual-form").addEventListener("submit", event => {
  event.preventDefault();
  if (!activeGateway()) return;
  manualCounts = [$("ns").valueAsNumber, $("ew").valueAsNumber];
  changeMode("manual");
});

function leavePage() {
  if (stream || opening) closeCamera("頁面已離開前景。請重新開啟相機。");
  if (mode !== "idle") changeMode("idle", true);
}

document.addEventListener("visibilitychange", () => {
  if (document.hidden) leavePage();
  else {
    void refreshGateways();
    void send();
  }
});
window.addEventListener("pagehide", leavePage);
setInterval(() => {
  if (stream && performance.now() - lastFrame >= (video.readyState >= 2 ? 1500 : 3000)) {
    closeCamera("相機畫面已停頓。請重新開啟。");
  }
  void send();
}, 1000);

if (!secureCamera) {
  status("camera-status", "這個頁面無法取用相機。請在電腦用 localhost，或在手機用受信任的 HTTPS 網址。");
}
updateControls();
void refreshGateways();
setInterval(refreshGateways, 2000);
