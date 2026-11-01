# Tổng hợp lệnh chạy dự án PBL4

Viết cho máy Windows chạy toàn bộ hệ thống (máy Quyến), dùng **PowerShell** hoặc terminal trong VS Code.
Đường dẫn repo: `C:\Users\Acer\OneDrive\文档\Github\pbl4`.

> **Quy tắc quan trọng nhất:** mỗi lệnh phải chạy **đúng thư mục**. Lỗi hay gặp nhất là chạy
> `npm run dev` ở thư mục gốc `pbl4` (phải `cd frontend` trước), hoặc chạy lệnh Python sai chỗ.
> Mỗi mục "Terminal" bên dưới là **một cửa sổ riêng**, để chạy nền, không gõ lệnh khác vào đó.

---

## 1. Cài đặt lần đầu (chỉ làm 1 lần, hoặc khi có thư viện mới)

```powershell
cd "C:\Users\Acer\OneDrive\文档\Github\pbl4"

# Backend
py -3.12 -m pip install -r backend\requirements.txt

# AI
py -3.12 -m pip install -r ai\requirements.txt

# Dashboard
cd frontend
npm install
```

Cần có sẵn: Docker Desktop (đang mở), Python 3.12 (`py -3.12`), Node.js.
Máy có Python MSYS64 không dùng được, luôn gọi bằng `py -3.12`.

---

## 2. Chạy hệ thống hằng ngày (đúng thứ tự)

### Terminal 1: Hạ tầng (Docker)
```powershell
cd "C:\Users\Acer\OneDrive\文档\Github\pbl4"
docker compose up -d
docker ps
```
Phải thấy 3 container **Up**: `aqi_mosquitto` (1883), `aqi_influxdb` (8086), `aqi_postgres` (5432).

### Terminal 2: Backend (chạy ngay sau Docker)
```powershell
cd "C:\Users\Acer\OneDrive\文档\Github\pbl4\backend"
py -3.12 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
Phải thấy dòng `Connected to MQTT broker; subscribed to sensors/+/data`.
Mỗi khi node gửi số sẽ in `Stored sensor reading for node-01`.

> Bật Backend **ngay sau Docker**: nếu node gửi bù dữ liệu lúc Backend chưa chạy thì phần đó bị mất.

### Terminal 3: Web Dashboard
```powershell
cd "C:\Users\Acer\OneDrive\文档\Github\pbl4\frontend"
npm run dev
```
Mở trình duyệt: <http://localhost:5173>
- Bấm **"Bật âm thanh cảnh báo"** một lần để Dashboard được phép phát âm thanh.
- Thấy dòng vàng "Đang hiển thị dữ liệu mẫu" nghĩa là Backend chưa chạy.

### Dự báo AI tự động
Nếu trước đó đã tắt lịch dự báo thì bật lại (xem thêm mục 5):
```powershell
Enable-ScheduledTask -TaskName "PBL4-AirQuality-Predict"
```
Muốn có dự báo mới ngay: `py -3.12 ai\predict.py --device_id node-01` ở thư mục gốc `pbl4`.

> Trước demo, chạy khối lệnh ở **mục 10** để kiểm tra mọi thứ đã chạy đủ.

### Node thật (Đạt)
Cắm nguồn cho node bằng **củ sạc điện thoại 5V ≥ 1A** (không cắm linh kiện thẳng vào ổ điện 220V).
Node gửi về **IP của máy chạy Docker**, nên **trước khi cắm node luôn kiểm tra IP**:
```powershell
ipconfig
```
Lấy dòng **IPv4 Address** của mục đang có mạng (bỏ qua `172.x.x.x` của WSL), so với `MQTT_BROKER` trong
firmware. Khác thì sửa rồi nạp lại firmware bằng Arduino IDE.

> ⚠️ **IP đổi khi chuyển giữa dây mạng (Ethernet) và Wi-Fi**, hoặc khi router cấp lại IP.
> Ví dụ 31/10: cắm dây là `192.168.10.2`, chuyển sang Wi-Fi `Imou-B97E14` thành `192.168.10.4`,
> node báo `Kết nối MQTT thất bại, rc=-2` liên tục. Hôm demo **giữ nguyên một kiểu kết nối (Wi-Fi)**,
> không cắm dây mạng. Hiện tại firmware dùng `192.168.10.4`.

Kiểm tra node đã kết nối broker (thấy dòng `New client connected ... as esp32-node-01` là được):
```powershell
docker exec aqi_mosquitto tail -n 10 /mosquitto/log/mosquitto.log
```

---

## 3. Kiểm tra từng phần đang chạy đúng

| Kiểm tra | Lệnh / địa chỉ | Kết quả đúng |
|---|---|---|
| Backend còn sống | <http://localhost:8000/health> | `{"status":"ok", ...}` |
| Danh sách API, thử API | <http://localhost:8000/docs> | Trang Swagger |
| Số đo mới nhất | <http://localhost:8000/api/readings/latest> | Có bản ghi `node-01` |
| Lịch sử 1 node | <http://localhost:8000/api/readings?device_id=node-01&limit=20> | Danh sách bản ghi |
| Dự báo mới nhất | <http://localhost:8000/api/forecasts/latest?device_id=node-01> | 24 điểm dự báo |
| Ngưỡng cảnh báo | <http://localhost:8000/api/alerts/config?device_id=node-01> | `pm25_threshold`, `aqi_threshold` |
| Danh sách cảnh báo | <http://localhost:8000/api/alerts?device_id=node-01> | `{"device_id": ..., "items": [...]}` |
| InfluxDB (giao diện web) | <http://localhost:8086> | Đăng nhập `admin` / `admin12345` |

Xem dữ liệu node đang gửi tới broker (terminal khác, Ctrl + C để dừng):
```powershell
docker exec -it aqi_mosquitto mosquitto_sub -t "sensors/#" -v
```

Xem dữ liệu trong PostgreSQL:
```powershell
docker exec -it aqi_postgres psql -U aqi_user -d aqi_db
```
Trong psql, gõ thử (thoát bằng `\q`):
```sql
SELECT id, device_id, generated_at, horizon_hours FROM forecast_runs ORDER BY id DESC LIMIT 5;
SELECT COUNT(*) FROM forecast_points WHERE forecast_run_id = (SELECT MAX(id) FROM forecast_runs);
SELECT * FROM alert_configs;
SELECT * FROM alert_events ORDER BY id DESC LIMIT 10;
```

---

## 4. Khi chưa có node thật: tạo dữ liệu giả qua MQTT

Chạy ở thư mục gốc `pbl4`, Docker và Backend phải đang chạy:
```powershell
cd "C:\Users\Acer\OneDrive\文档\Github\pbl4"

# Gửi bù 48 giờ lịch sử (để biểu đồ và AI có dữ liệu)
py -3.12 ai\publish_mock_to_mqtt.py --hours 48

# Giả lập node gửi liên tục, 10 giây/lần (Ctrl + C để dừng)
py -3.12 ai\publish_mock_to_mqtt.py --live --interval 10
```
Dữ liệu giả cũng dùng `device_id = node-01`. Khi demo với node thật thì **không** chạy song song lệnh này.

---

## 5. Khối AI (Lợi)

Chạy ở **thư mục gốc `pbl4`** (không `cd ai`):
```powershell
cd "C:\Users\Acer\OneDrive\文档\Github\pbl4"

# Dự báo 24 giờ tới cho node-01, gửi kết quả về Backend (lưu PostgreSQL)
py -3.12 ai\predict.py --device_id node-01

# Lập lịch chạy predict.py mỗi giờ trên Windows (chạy một lần từ thư mục repo)
powershell -ExecutionPolicy Bypass -File scripts\install_predict_task.ps1 -DeviceId node-01

# Huấn luyện lại mô hình trên dữ liệu mô phỏng (lưu vào model\lstm_model.keras)
py -3.12 ai\train_model.py --data ai\data\mock_readings.csv

# Xuất dữ liệu thật của node từ Backend ra file CSV
py -3.12 ai\fetch_data.py --device_id node-01 --out ai\data\readings.csv
```
Chạy `predict.py` xong, Dashboard tự lấy dự báo mới trong vòng 5 phút (hoặc bấm F5).
Lệnh cài lịch tạo Windows Scheduled Task `PBL4-AirQuality-Predict`; máy chạy lịch cần có Python 3.12,
dependencies trong `ai/requirements.txt`, model/scaler và Backend đang truy cập được. Phối hợp với Lợi
để cài lịch trên máy AI và xác nhận đúng device/model trước khi bật.

### Lịch dự báo tự động (Scheduled Task `PBL4-AirQuality-Predict`)

Xem trạng thái:
```powershell
Get-ScheduledTask -TaskName "PBL4-AirQuality-Predict" | Get-ScheduledTaskInfo
```

| `LastTaskResult` | Ý nghĩa |
|---|---|
| `0` | Chạy thành công |
| `267009` | Đang chạy dở (TensorFlow nạp mất ~30 giây), đợi rồi xem lại |
| `267011` | Chưa tới giờ chạy lần đầu |
| `2147942402` (`0x80070002`) | **Không tìm thấy file** (`py` hoặc `predict.py`), thường do đường dẫn có chữ `文档` bị lỗi mã hoá. Cài lại bằng khối lệnh bên dưới |

> Lưu ý: `0` chỉ có nghĩa là lệnh `py` chạy xong. Nếu Backend đang tắt thì lần đó **không lưu được dự báo**.
> Kiểm tra thật bằng Dashboard: góc biểu đồ phải ghi "Dự báo lúc ..." trong vòng 1 giờ, không có chữ "đã cũ".

Cài lại task với đường dẫn đầy đủ (PowerShell thường, dán **cả khối**). Chạy lần đầu sau 1 phút, rồi mỗi giờ:
```powershell
$repo = "C:\Users\Acer\OneDrive\文档\Github\pbl4"
$py   = (Get-Command py).Source
$action   = New-ScheduledTaskAction -Execute $py -Argument "-3.12 ai\predict.py --device_id node-01" -WorkingDirectory $repo
$trigger  = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Hours 1)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName "PBL4-AirQuality-Predict" -Action $action -Trigger $trigger -Settings $settings -Force
```

Tạm tắt khi không chạy hệ thống / bật lại khi demo:
```powershell
Disable-ScheduledTask -TaskName "PBL4-AirQuality-Predict"
Enable-ScheduledTask  -TaskName "PBL4-AirQuality-Predict"
```

Cách tạm nếu task hỏng mà chưa kịp sửa: mở một cửa sổ PowerShell riêng ở thư mục `pbl4`, chạy rồi để nguyên
(Ctrl + C để dừng):
```powershell
while ($true) { py -3.12 ai\predict.py --device_id node-01; Start-Sleep -Seconds 3600 }
```

---

## 6. Nạp firmware cho node (Đạt)

1. Mở `iot\esp32_sensor_node\esp32_sensor_node.ino` bằng Arduino IDE.
2. Kiểm tra `WIFI_SSID`, `WIFI_PASSWORD`, `MQTT_BROKER` ở đầu file.
3. **Tools → Board → ESP32 Dev Module**, chọn đúng cổng COM, bấm **Upload**.
4. **Tools → Serial Monitor**, baud **115200**. Đúng thì thấy `Đã kết nối MQTT.` và `Đã publish MQTT thành công`.

Chi tiết nối dây cảnh báo và đóng hộp: `iot\esp32_sensor_node\HUONG_DAN_CANH_BAO_VA_DONG_HOP.md`.

---

## 7. Tắt hệ thống

1. Dashboard và Backend: bấm **Ctrl + C** trong Terminal 3 và Terminal 2.
2. Docker:
```powershell
cd "C:\Users\Acer\OneDrive\文档\Github\pbl4"
docker compose down
```
`docker compose down` **giữ nguyên dữ liệu**. **Không** dùng `docker compose down -v`: lệnh đó xoá luôn dữ liệu InfluxDB và PostgreSQL.
3. Tắt lịch dự báo cho máy nhẹ: `Disable-ScheduledTask -TaskName "PBL4-AirQuality-Predict"` (bật lại bằng `Enable-ScheduledTask`).
4. Nhắn Đạt rút điện node.

---

## 8. Lỗi thường gặp

| Hiện tượng | Nguyên nhân | Cách xử lý |
|---|---|---|
| `npm error enoent ... pbl4\package.json` | Chạy `npm` ở thư mục gốc | `cd frontend` rồi chạy lại |
| `docker: ... cannot connect to the Docker daemon` | Docker Desktop chưa mở | Mở Docker Desktop, đợi chạy xong rồi chạy lại |
| `[Errno 10048] ... address already in use` khi chạy Backend | Đang có Backend khác chiếm cổng 8000 | Đóng terminal Backend cũ, hoặc tắt hết rồi chạy lại |
| Dashboard hiện "dữ liệu mẫu" | Backend chưa chạy hoặc bị lỗi | Xem Terminal 2, chạy lại uvicorn |
| Dashboard không tự cập nhật | Backend vừa khởi động lại, WebSocket bị ngắt | Bấm F5 trên trình duyệt |
| Node báo `Kết nối MQTT thất bại, rc=-2` | **IP máy đã đổi** (hay gặp nhất: chuyển dây mạng ↔ Wi-Fi), Docker chưa chạy, tường lửa chặn | `ipconfig` → sửa `MQTT_BROKER` rồi nạp lại; mở Docker; mở cổng 1883 (xem dưới bảng) |
| Backend báo `422 ... field type conflict` | Lệch kiểu số nguyên / số thực khi ghi InfluxDB | Đã sửa trong code; nếu gặp lại thì pull code mới từ `main` |
| Dữ liệu bị lệch 7 tiếng | Firmware cũ gửi giờ không có `+07:00` | Nạp firmware mới nhất |
| `predict.py` báo không tìm thấy model | Chạy sai thư mục | Chạy ở thư mục gốc `pbl4` như mục 5 |
| GitHub Desktop báo `index.lock` | Một lệnh git trước bị dừng giữa chừng | Đóng các cửa sổ git đang chạy rồi xoá file `.git\index.lock` |
| Dashboard ghi "Dự báo lúc ... · đã cũ", đường dự báo nằm lẫn vào quá khứ | Scheduled Task không chạy được | Xem mục 5, phần Scheduled Task |
| Dashboard cảnh báo liên tục dù PM2.5 chỉ ~40 | Ngưỡng **AQI 100** ứng với PM2.5 chỉ 35.4, thấp hơn ngưỡng PM2.5 = 55 | Đặt ngưỡng AQI = **150** cho khớp PM2.5 = 55, bấm **Lưu ngưỡng** |
| Còi node không kêu dù Dashboard đã cảnh báo | Còi dựa vào **PM2.5 trung bình 2 phút** của node, không dựa vào AQI; mức vàng chỉ kêu 1 tiếng ngắn; LCD hiện `IM` là đang tắt tiếng | Để khói gần PMS 1–2 phút cho vượt 55.4 (đèn đỏ, kêu 3 tiếng); bấm nút tắt tiếng lần nữa để bật lại |
| Biểu đồ dự báo nhảy cao bất thường so với số đo hiện tại | 24 giờ gần nhất có ít dữ liệu thật (node mới chạy lại) | Để node chạy vài giờ, task tự dự báo lại mỗi giờ |

Mở cổng 1883 cho node kết nối (PowerShell **Run as administrator**, chạy 1 lần):
```powershell
New-NetFirewallRule -DisplayName "PBL4 MQTT 1883" -Direction Inbound -Protocol TCP -LocalPort 1883 -Action Allow
```
Mạng Wi-Fi của máy nên để chế độ **Private** (Settings → Network & Internet → Wi-Fi → tên mạng → Network profile type).

---

## 9. Lấy code mới và đẩy code (GitHub Desktop)

- **Trước khi làm:** chuyển sang nhánh `main` → **Fetch origin** → **Pull origin**.
- **Làm việc:** tạo nhánh mới (**Current Branch → New Branch**), sửa code.
- **Đẩy code:** tick file → ghi nội dung commit → **Commit** → **Push origin** → **Create Pull Request** vào `main`.
- Có thư viện mới trong `requirements.txt` hoặc `package.json` thì chạy lại các lệnh ở mục 1.

---

## 10. Kiểm tra nhanh mọi thứ đang chạy (dùng trước demo)

Dán **cả khối** vào một cửa sổ PowerShell (không dán vào cửa sổ Backend/Dashboard):
```powershell
"=== Docker ==="
docker ps --format "{{.Names}}  {{.Status}}"
"=== Backend (8000) / Dashboard (5173) ==="
foreach ($p in 8000, 5173) { if (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue) { "Cong $p : DANG CHAY" } else { "Cong $p : KHONG chay" } }
"=== Python dang chay ==="
Get-Process py, python -ErrorAction SilentlyContinue | Select-Object Id, ProcessName, StartTime | Format-Table -AutoSize
"=== Scheduled Task du bao ==="
Get-ScheduledTask -TaskName "PBL4-AirQuality-Predict" | Get-ScheduledTaskInfo | Select-Object LastRunTime, LastTaskResult, NextRunTime | Format-List
"=== Node gui du lieu moi nhat ==="
try { $l = Invoke-RestMethod "http://localhost:8000/api/readings?device_id=node-01&limit=1"; $x = @(if ($l.items) { $l.items } else { $l })[0]; "Ban ghi moi nhat: $(([datetime]$x.timestamp).ToLocalTime())   (bay gio: $(Get-Date))" } catch { "Khong goi duoc Backend" }
```

| Mục | Đúng khi |
|---|---|
| Docker | 3 container `aqi_mosquitto`, `aqi_influxdb`, `aqi_postgres` đều **Up** |
| Cổng 8000 / 5173 | **DANG CHAY** |
| Python | Có ít nhất 1 tiến trình (Backend) |
| Scheduled Task | `LastTaskResult : 0`, `LastRunTime` trong vòng 1 giờ |
| Node | "Ban ghi moi nhat" cách giờ hiện tại **dưới 1 phút** |

---

## 11. Chạy dài giờ / qua đêm

1. Node cắm củ sạc 5V, đặt trên mặt bàn khô ráo (mạch hở không chạm khung sắt), PMS5003 để chỗ thoáng.
2. Máy chạy Docker **luôn cắm sạc** và không ngủ:
```powershell
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
```
   Hoặc Settings → System → Power & battery → Screen, sleep, & hibernate timeouts → mục **Plugged in** chọn **Never**.
   Tắt **Energy saver** (gạt **Always use energy saver** sang Off).
   Muốn gập máy thì Control Panel → Power Options → *Choose what closing the lid does* → **Plugged in: Do nothing**.
3. Trong lúc chạy **vẫn dùng máy làm việc khác được**, chỉ **không**: tắt máy/khởi động lại/Sleep, đóng cửa sổ Backend
   hoặc Docker Desktop, cắm dây mạng hay đổi Wi-Fi, rút sạc lâu, chạy `docker compose down`.
4. Node có **buffer 50 bản ghi (~25 phút)**: gián đoạn ngắn hơn thế thì không mất dữ liệu, node tự gửi bù.
5. Ban đêm 22h–6h còi node tự im, chỉ bật đèn.

---

## 12. Đếm số giờ chạy và số bản ghi (minh chứng cho báo cáo)

Đổi `from=` thành lúc bắt đầu chạy (giờ UTC = giờ Việt Nam − 7; ví dụ 13:50 ngày 31/10 là `2026-10-31T06:50:00Z`).
`limit=5000` đủ cho ~41 giờ ở chu kỳ 30 giây; chạy lâu hơn thì tăng lên.

**Toàn bộ từ lúc bắt đầu tới giờ:**
```powershell
$r = Invoke-RestMethod "http://localhost:8000/api/readings?device_id=node-01&from=2026-10-31T06:50:00Z&limit=5000"
$items = @(if ($r.items) { $r.items } else { $r })
$t = $items | ForEach-Object { [datetime]$_.timestamp } | Sort-Object
"So ban ghi : $($items.Count)"
"Dau tien   : $($t[0].ToLocalTime())"
"Moi nhat   : $($t[-1].ToLocalTime())"
"Da chay    : {0:N1} gio" -f ($t[-1] - $t[0]).TotalHours
$gaps = for ($i = 1; $i -lt $t.Count; $i++) { if (($t[$i] - $t[$i-1]).TotalMinutes -gt 2) { "$($t[$i-1].ToLocalTime()) -> $($t[$i].ToLocalTime())" } }
"So lan mat du lieu > 2 phut: $(@($gaps).Count)"
$gaps
```

**Chỉ đúng 12 giờ đầu** (thay dòng `$t = ...` ở trên bằng 2 dòng này):
```powershell
$all = $items | ForEach-Object { [datetime]$_.timestamp } | Sort-Object
$t = $all | Where-Object { $_ -le $all[0].AddHours(12) }
```
Chu kỳ 30 giây → 12 giờ ≈ **1.440 bản ghi**.

> Kết quả lần chạy 31/10–01/11: 13:57:50 → 01:57:46, **1.438 bản ghi (~99,9%)**, **12,0 giờ**, **0** lần mất dữ liệu > 2 phút.

---

## 13. Xem và xuất dữ liệu

**Dữ liệu nằm ở đâu:** số đo node lưu trong **InfluxDB** (bucket `air_quality`); dự báo, ngưỡng và lịch sử cảnh báo
lưu trong **PostgreSQL** (`forecast_runs`, `forecast_points`, `alert_configs`, `alert_events`). Cả hai nằm trong
Docker volume (`docker volume ls`), không phải file trong repo.

**Xem bằng InfluxDB Data Explorer:** <http://localhost:8086> (`admin` / `admin12345`) → biểu tượng Data Explorer →
bucket `air_quality` → `_measurement` = `air_quality` → `_field` (vd `pm25`, `pm10`) → thêm bộ lọc `device_id` = `node-01`
→ chọn khoảng thời gian (vd **Past 12h**) → **SUBMIT**. Bật **View Raw Data** để xem bảng; nút **CSV** để tải về.
Mặc định đang lấy trung bình (`mean`), chọn **CUSTOM → last** nếu muốn từng bản ghi gốc.
Chụp 2 ảnh riêng: PM2.5 + PM10, và nhiệt độ + độ ẩm (đơn vị khác nhau nên vẽ chung khó nhìn).

**Xuất ra CSV** (thư mục gốc `pbl4`):
```powershell
py -3.12 ai\fetch_data.py --device_id node-01 --out ai\data\node-01.csv
```
File này có **cả dữ liệu mô phỏng cũ** (24/08–22/09, mỗi giờ 1 bản ghi) và các lần chạy thử trước. Tách riêng
**dữ liệu thật** (đổi mốc thời gian nếu cần):
```powershell
Import-Csv ai\data\node-01.csv | Where-Object { [datetime]$_.timestamp -ge [datetime]"2026-10-31T13:57:00+07:00" } | Export-Csv ai\data\node-01_real.csv -NoTypeInformation -Encoding UTF8
(Import-Csv ai\data\node-01_real.csv).Count
```
`ai/data/*.csv` đã nằm trong `.gitignore` nên **không commit**; gửi cho Lợi qua Zalo/Drive.
