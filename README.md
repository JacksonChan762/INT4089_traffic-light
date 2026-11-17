# INT4089 十字路口智能紅綠燈

這個課堂模型用六顆 LED 模擬兩條單向道交會的路口。Arduino Uno R3 控制燈號，可獨立執行固定時間循環。接上 ESP32 後，可在手機網頁輸入兩道的等候車量，或用 iPhone 拍攝模型、由 Mac 計數。Uno 會在下一次綠燈開始時，按兩道車量的差額決定綠燈時間。

## 檔案

- `arduino_uno/arduino_uno.cpp`：上傳至 Uno；同資料夾的 `TrafficController.h` 必須保留。
- `esp32_gateway/esp32_gateway.cpp`：上傳至 ESP32。
- [Mac 相機工具](mac_camera/README.md)：安裝 Python 依賴、選擇相機及校準等候區。
- `tests/controller_test.cpp`：電腦上測試控制邏輯。

## 硬體假設與接線

目前假設 ESP32 是 **經典 ESP32-WROOM-32 開發板**，GPIO16/17 可用。如果是 ESP32-C3、S3、WROVER 或 ESP32-CAM，請先核對型號及可用腳位，不能直接沿用板型設定。

兩條單向道交叉，只設兩組紅黃綠燈，共 **6 顆 LED、6 個電阻**。A 道與 B 道各有一組燈，車輛各自沿單一方向通過路口。

```text
           A 道 ↓
           [A 組燈]
B 道 → [B 組燈] ＋ →
                 ↓
```

| Uno 腳位 | 燈號 |
|---|---|
| D2 | A 道紅燈 |
| D3 | A 道黃燈 |
| D4 | A 道綠燈 |
| D5 | B 道紅燈 |
| D6 | B 道黃燈 |
| D7 | B 道綠燈 |

每條 LED 支路：Uno 腳位 → **1 kΩ 電阻** → LED 正極（長腳）→ LED 負極 → GND。每個腳位只接一顆 LED，每顆 LED 各有自己的電阻。此接法假設使用普通低電流 LED，不適用於大功率燈或未知規格紅綠燈模組。

ESP32 與 Uno 用 **單向 UART**：

| 連接 | 用途 |
|---|---|
| ESP32 GPIO17（TX）→ Uno D10（RX） | 車量指令 |
| ESP32 GND ↔ Uno GND | 共地 |
| Uno D11、ESP32 GPIO16 | 不接 |

目前按單向直連測試：使用短線，Uno 程式已在 `gateway.begin(9600)` 後關閉 D10 的內部 5V 上拉。3.3V 訊號直連 Uno 的電壓餘裕有限，不保證所有條件下穩定；若通訊不穩定，再加入支援 UART 的 3.3V 至 5V 電平轉換器。

兩塊開發板各用一條 USB 線供電，可接同一電腦的兩個 USB 插口；兩板 GND 仍須相接。不要互接兩板的 5V 或 3.3V 供電腳。Uno D11 保持不接，不要將 Uno 的 5V 輸出直接接到 ESP32 GPIO。先斷電再接線。

## 上傳及使用

1. 先安裝 PlatformIO Core 或 VS Code 的 PlatformIO IDE 擴充套件。第一次編譯需要連上互聯網，讓 PlatformIO 下載工具鏈。
2. 如果使用 VS Code + PlatformIO，開啟包含 `platformio.ini` 的整個專案資料夾。選 `uno` 環境編譯／上傳至 Uno；選 `esp32` 環境編譯／上傳至 ESP32。上傳時選正確連接埠，或一次只插入要上傳的板。
3. 也可在此資料夾執行 `pio run -e uno` 或 `pio run -e esp32` 編譯；用 `pio device list` 找出兩塊板的連接埠，再加上 `-t upload --upload-port 實際連接埠` 上傳。使用其他 C++ 工具時，需設定相同開發板及 Arduino framework；不能用一般桌面 C++ 編譯器直接編譯板上程式。先單獨上傳 Uno，確認燈號循環。
4. 按上述接線連接兩板。手機加入 Wi-Fi **TrafficLight-Lab**，密碼 **traffic123**。如手機提示沒有網絡，選擇保持連線。
5. 在瀏覽器開啟 **http://192.168.4.1**。實際網址亦會顯示在 ESP32 的序列埠監控視窗（115200 baud）。
6. 輸入 A 道、B 道車量並按「套用車量並持續傳送」。頁面每秒傳送一次已套用的車量；修改輸入框後要再按套用。
7. 按「恢復固定時間循環」可停止適應車量。離開頁面或斷線後，車量資料 5 秒過期。

保持頁面在前景，避免手機暫停背景計時器。頁面顯示 ESP32 接收指令成功，不代表 Uno 已接收或實體 LED 已切換；請觀察 LED。Uno 序列埠監控視窗會列出階段編號及持續時間。

## 控制規則

- 啟動：全紅 2 秒。
- 循環：A 道綠 → A 道黃 → 全紅 → B 道綠 → B 道黃 → 全紅。
- 黃燈 3 秒，全紅 2 秒；不會因收到車量指令而跳過。
- 每個綠燈開始時，時間 = `10 + min(max(本方向車量 − 另一方向車量, 0), 5) × 2` 秒。
- 例如 A 道 8 輛、B 道 3 輛：A 道綠 20 秒，B 道綠 10 秒。相同車量或沒有車，兩邊都是 10 秒。
- 兩方向固定輪流，各自綠燈上限 20 秒，避免單邊一直等候。
- 已開始的綠燈不會中途修改。資料過期或恢復固定模式後，**下一次**綠燈用 10 秒；現有階段正常完成。

## 用 iPhone 和 Mac 計數

先在有互聯網時依照 [Mac 相機設定指南](mac_camera/README.md) 安裝依賴並確認 Mac 能讀取 iPhone 畫面。關閉持續傳送手動車量的網頁，再讓 Mac 加入 **TrafficLight-Lab**。

1. 固定鏡頭，啟動 `mac_camera/Start.command`，選取 iPhone 相機。
2. 在預覽視窗按 **R**，依次框選 A、B 道等候區。移走車和手，按 **B** 記錄空路面。
3. 將模型車分開擺放，核對畫面的偵測框和數量，再按 **S** 傳送。Mac 比對空路面與目前畫面，因此陰影或手部也可能被計入，相連的車可能被算成一輛。
4. 按 **P** 停止傳送並要求固定時間，按 **Q** 離開。

## ESP32 車量介面

手動頁面與 Mac 使用相同的表單格式。以下範例將 A 道設為 8 輛、B 道設為 3 輛。

```http
POST /api/counts
Content-Type: application/x-www-form-urlencoded

ns=8&ew=3
```

欄位 `ns` 對應 A 道，`ew` 對應 B 道（保留原有通訊名稱）。兩個欄位只接受 0–99 整數。`POST /api/auto` 恢復固定時間。有效車量會被轉成 `C,8,3\n`，以 9600 baud 送到 Uno。請只讓一個控制頁面或辨識程式持續傳送，以免不同來源互相覆蓋。

## 驗證

電腦邏輯測試：

```sh
c++ -std=c++11 -Wall -Wextra -pedantic tests/controller_test.cpp -o /tmp/traffic-controller-test
/tmp/traffic-controller-test
```

實體測試：

1. 無 ESP32 時，確認兩邊綠燈各 10 秒、黃燈 3 秒、全紅 2 秒。
2. 傳送 A 道 8、B 道 3，確認 A 道下一次綠燈為 20 秒。
3. 改成 A 道 1、B 道 4，確認 B 道下一次綠燈為 16 秒。
4. 在綠燈期間改車量，確認現有綠燈時間不變。
5. 關閉頁面，等待資料過期後，確認下一次綠燈回到 10 秒。
6. 確認任何時候兩個方向不會同時亮綠燈。

Mac 相機測試使用合成影像與本機模擬的 ESP32 服務。安裝相機依賴後，從專案根目錄執行：

```sh
cd mac_camera
.venv/bin/python -m unittest discover -s tests -v
```

## 官方參考

- [Espressif Wi-Fi API](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/wifi.html)
- [Espressif WebServer 範例](https://github.com/espressif/arduino-esp32/blob/master/libraries/WebServer/examples/WebServer/WebServer.cpp)
- [Arduino SoftwareSerial](https://docs.arduino.cc/learn/built-in-libraries/software-serial)

- [PlatformIO 來源檔案篩選設定](https://docs.platformio.org/en/stable/projectconf/sections/env/options/build/build_src_filter.html)
