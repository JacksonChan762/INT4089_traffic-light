# 瀏覽器相機與電腦端影像處理

[English](README.md) · **繁體中文**

控制台可在 macOS、Linux 或 Windows 電腦上執行。請用你要取用鏡頭的裝置開啟控制台。電腦瀏覽器可以選用內建或 USB 鏡頭。手機瀏覽器可以選用內建鏡頭，並透過 Wi-Fi 將壓縮影像傳到同一台控制台主機。電腦用 OpenCV 計算車輛數量，將結果送給 ESP32，再由 ESP32 透過 UART 轉送指令給 Uno。

## 加入電腦的網路

1. 依照[編譯與燒錄說明](../README.zh-TW.md#編譯與燒錄)更新 ESP32。將電腦連到現有的 Wi-Fi 路由器。路由器須提供 **2.4 GHz Wi-Fi** 供 ESP32 連線，並允許區域網路中的裝置互相通訊。
2. 用 USB 將 ESP32 接到電腦，並關閉所有開啟的序列監視器。使用 v1.2.1 套件，在 macOS 開啟 `Start.command`，在 Windows 開啟 `Start.cmd`，或在 Linux 執行 `./start.sh`。
3. 在啟動提示輸入 `W` 並按 Enter。如果列出多個序列埠，選擇 ESP32 使用的序列埠。輸入路由器的 2.4 GHz Wi-Fi 名稱（SSID）與密碼。輸入密碼時畫面不會顯示字元，啟動程式會透過 USB 將設定傳到 ESP32。
4. ESP32 儲存設定後會重新啟動。啟動程式會開啟電腦控制台，並在 ESP32 加入路由器後找到它。完成設定後，下次啟動時直接按 Enter 即可使用電腦鏡頭。若要使用手機鏡頭，請在啟動時輸入電腦的區域網路 IPv4 位址。 [手機鏡頭設定](#從手機瀏覽器使用鏡頭)

### 使用序列監視器設定 Wi-Fi

也可使用 PlatformIO 的 USB 序列監視器設定 ESP32。

1. 執行 `pio device list` 尋找序列埠，再開啟序列監視器。將 `ESP32_PORT` 換成該序列埠，例如 Windows 上的 `COM3`，或 macOS 上的 `/dev/cu.usbserial-XXXX`。

   ```sh
   pio device monitor -e esp32 --port ESP32_PORT --filter send_on_enter
   ```

2. 輸入 `wifi` 並按 Enter。依提示先輸入路由器的 2.4 GHz Wi-Fi 名稱（SSID），再輸入密碼，每次輸入後按 Enter。請讓監視器的本機回顯保持關閉。ESP32 會儲存設定並重新啟動，接著加入指定網路。
3. 在 **115200 baud** 的 USB 序列監視器中找到 **Gateway on computer Wi-Fi**。輸入 `status` 並按 Enter，也能再次顯示位址。可從電腦開啟 ESP32 的 HTTP 網址檢查連線，或搭配 `--esp` 手動配對。

## 尋找並配對 ESP32

執行控制台的電腦會使用多播 DNS（mDNS）尋找區域網路上的 ESP32 閘道。請使用新版閘道韌體，並在 ESP32 加入 Wi-Fi 時讓控制台持續開啟。只找到一台 ESP32 時，控制台會自動配對。如果有多台，請從 **Gateway** 選單中選擇要控制的裝置。

控制台會在本次工作階段記住選定的裝置。即使 IP 改變，重新上線後仍可辨識同一台裝置。連線中斷或改選其他裝置後，請重新開始傳送車輛數量。若電腦要求存取區域網路的權限，請允許。若使用舊版韌體或網路封鎖多播，可從終端機使用 `--esp http://192.168.1.30` 啟動控制台，並替換成 ESP32 實際取得的 IPv4 位址。

## 免安裝套件

選擇符合電腦作業系統與處理器的壓縮檔，將整個檔案解壓縮，再開啟附帶的啟動程式。套件內的 Python 與 OpenCV 會在電腦上執行。使用 v1.2.1 啟動程式時，在提示輸入 `W` 可透過 USB 設定 Wi-Fi，直接按 Enter 可使用電腦鏡頭。如果要使用手機鏡頭，請輸入電腦的區域網路 IPv4 位址，並按下方說明提供受信任的憑證與金鑰。兩種相機模式都會自動尋找 ESP32。 [套件內的啟動說明（英文）](packaging/README.txt)

請依電腦作業系統與處理器下載 v1.2.1 套件。 [發布套件下載](../README.zh-TW.md#下載瀏覽器相機控制台)

若要從原始碼建立五個壓縮檔，請在具備 Python 3.12 與 pip 的環境中，從專案根目錄執行 `python3.12 browser_camera/packaging/build.py`。壓縮檔與 SHA-256 校驗碼會放在 `dist/`。

## 從原始碼安裝

請使用 CPython 3.12，在專案根目錄執行下列命令。

| 電腦平台 | Python 版本 |
| --- | --- |
| Windows | x64 CPython。Windows 11 ARM 可透過[應用程式模擬](https://learn.microsoft.com/en-us/windows/arm/apps-on-arm-x86-emulation)執行 x64 CPython。 |
| Linux | 採用 glibc 的 Linux 發行版（例如 Ubuntu 或 Debian），搭配 x86-64 或 ARM64 CPython。 |
| macOS | Apple Silicon 或 Intel 版 CPython。附帶的 OpenCV wheel 套件需要 macOS 11 以上（Apple Silicon）或 macOS 12 以上（Intel）。 |

控制台使用 OpenCV Headless 在電腦上處理影像。

**Linux 或 macOS**

```sh
python3.12 -m venv .venv-browser
.venv-browser/bin/python -m pip install --only-binary=:all: -r browser_camera/requirements.txt
```

**Windows PowerShell**

```powershell
py -3.12 -m venv .venv-browser
.\.venv-browser\Scripts\python.exe -m pip install --only-binary=:all: -r browser_camera/requirements.txt
```

如果 Windows 11 ARM 同時裝有 ARM64 和 x64 Python，請直接執行 x64 Python 的執行檔來建立環境。若 Windows 上的 OpenCV 回報缺少 DLL，請參考 [OpenCV 的 Windows 疑難排解](https://pypi.org/project/opencv-python-headless/4.10.0.84/#frequently-asked-questions)。

## 使用電腦鏡頭

啟動網頁控制台，並使用預設的自動尋找 ESP32 功能。

```sh
.venv-browser/bin/python -m browser_camera.server
```

Windows 請以 `.\.venv-browser\Scripts\python.exe` 取代 `.venv-browser/bin/python`。在同一台電腦開啟 **http://127.0.0.1:8000/**，按 **Open camera** 並允許使用鏡頭。允許存取後，可透過 **Camera** 選單切換可用的鏡頭。

## 從手機瀏覽器使用鏡頭

手機必須信任電腦網路位址使用的 HTTPS 憑證。手機瀏覽器中的 `localhost` 指向手機本身。使用這個模式時，請在手機與電腦上都用電腦的區域網路網址開啟控制台。 [W3C 相機 API](https://www.w3.org/TR/mediacapture-streams/#navigator-interface-extensions)

1. 將手機接到與電腦和 ESP32 相同的 Wi-Fi 路由器。在電腦的網路設定中查詢這個網路的 IPv4 位址。下列範例使用 **192.168.1.20** 作為電腦位址。控制台會尋找同一網路上的 ESP32。
2. 在電腦安裝 [mkcert](https://github.com/FiloSottile/mkcert)，為電腦 IP 建立憑證。從專案根目錄執行下列命令，並換成實際的電腦 IP 位址。

   ```sh
   mkcert -install
   mkcert -cert-file traffic-cert.pem -key-file traffic-key.pem 192.168.1.20
   mkcert -CAROOT
   ```

3. 從 `mkcert -CAROOT` 顯示的目錄將 **rootCA.pem** 複製到手機。**rootCA-key.pem** 與 **traffic-key.pem** 兩個私密金鑰檔則留在電腦。Android 請透過系統的 **CA 憑證** 選項安裝公開根憑證。若檔案選擇器要求不同副檔名，可將同一份公開憑證另存為 `traffic-root.crt`。在 iPhone 安裝公開根憑證後，到 **設定 → 一般 → 關於本機 → 憑證信任設定** 啟用完整信任。 [mkcert 手機設定](https://github.com/FiloSottile/mkcert#mobile-devices) · [Apple 憑證信任說明](https://support.apple.com/en-us/102390)
4. 以 HTTPS 模式啟動控制台。Windows 請使用 `.\.venv-browser\Scripts\python.exe`。如果防火牆出現提示，請允許控制台在私人網路上通訊。

   ```sh
   .venv-browser/bin/python -m browser_camera.server --bind 192.168.1.20 --cert traffic-cert.pem --key traffic-key.pem
   ```

5. 在 Android 的 Chrome 或 iPhone 的 Safari 開啟 **https://192.168.1.20:8000/**。按 **Open camera**，允許使用鏡頭，再選擇要使用的鏡頭。若電腦 IP 改變，請為新位址建立憑證，並更新 `--bind` 的值。

## 校正並傳送車輛數量

1. 固定鏡頭，讓兩道等候區都出現在預覽中，並維持穩定的光線與取景範圍。
2. 按 **Select Road A**，拖曳框住 A 道等候區。再按 **Select Road B**，以相同方式框住 B 道。兩個辨識框應分開。
3. 清空兩道並按 **Capture empty background**。將彼此分開的模型車放回等候區。電腦會比對每張影像與空景，在畫面標出物件與各道車輛數量。如果有誤判，可以調整差異門檻或最小車輛面積。若場景移動，請重新擷取空景。
4. 連續三次數量相同後，按 **Start sending camera counts**。將頁面留在前景，並且一次只從一個控制台或 ESP32 手動控制頁面傳送數量。
5. 按 **Stop sending and restore fixed timing** 可暫停自適應計時。按 **Close camera** 可釋放鏡頭。若鏡頭或網路斷線，從最後一筆有效數量送達起經過五秒，Uno 便會恢復固定週期。計時變更在下一次綠燈開始時生效。

電腦會暫時將空景存於記憶體，並在本機處理影像。ESP32 接收的是車輛數量。請讓手部與陰影離開等候區，彼此接觸的車輛有可能被算成同一個物件。

也可在 **Manual counts** 輸入車輛數量，再按 **Apply and keep sending**，無須開啟鏡頭。若手邊沒有電腦，可使用 [ESP32 手動控制頁面](../README.zh-TW.md#使用-esp32-手動控制頁面)。

## 用紅綠燈前的排隊車輛測試鏡頭

1. 在控制台按 **Open Traffic Light Test Lab (new tab)**，也可直接在另一台裝置開啟 `browser_camera/traffic_test.html`。將測試頁顯示在鏡頭能拍到的螢幕上。如需放大畫面，請在校正前按 **Expand view**。
2. 保持兩道清空，在控制台開啟鏡頭，讓兩個標示的等候區都入鏡。分別框選 A 道和 B 道的等候區，燈號留在兩個框外。按 **Capture empty background**，之後保持鏡頭和螢幕固定。
3. 設定 A 道和 B 道的車輛數量，按 **Queue cars**。兩道會維持紅燈，車輛會停定。此時可比對控制台顯示的數字與設定車數。
4. 按 **Start signal cycle** 讓車輛行駛，並用 **Speed** 調整車速。按 **Hold red** 可回到兩道停車排隊的畫面，按 **Clear roads** 可回到校正用的空景。

模擬器顯示每道預定的紅燈（**Red**）、黃燈（**Yellow**）和綠燈（**Green**）時間。循環開始後，畫面也會顯示當前燈號階段與倒數。綠燈基本時間為 10 秒，每比另一道多一輛車就加 2 秒，最多 20 秒。每次黃燈維持 3 秒，接著兩道同時亮紅燈 2 秒。每次綠燈開始時會決定該次長度。這些時間是瀏覽器內的模擬數值。

## 在各平台測試控制台

請在專案根目錄使用瀏覽器環境的 Python，執行偵測器與控制台整合測試。

```sh
.venv-browser/bin/python -m unittest discover -s browser_camera/tests -v
```

Windows 請使用 `.\.venv-browser\Scripts\python.exe`。測試會在本機回送介面啟動控制台並上傳合成 JPEG 影像，驗證 A 道有兩個紙團、B 道有一個紙團，最後檢查模擬 ESP32 所收到的請求。
