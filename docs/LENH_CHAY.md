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

### Node thật (Đạt)
Cắm nguồn cho node. Node gửi về IP máy chạy Docker. Nếu đổi mạng hoặc khởi động lại máy, kiểm tra IP:
```powershell
ipconfig
```
Lấy dòng **IPv4 Address** của mục Wi-Fi (bỏ qua `172.x.x.x` của WSL), so với `MQTT_BROKER` trong
`iot/esp32_sensor_node/esp32_sensor_node.ino`. Khác thì sửa rồi nạp lại firmware bằng Arduino IDE.

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
| Danh sách cảnh báo | <http://localhost:8000/api/alerts?device_id=node-01> | (khi Bình làm xong) |
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

# Huấn luyện lại mô hình trên dữ liệu mô phỏng (lưu vào model\lstm_model.keras)
py -3.12 ai\train_model.py --data ai\data\mock_readings.csv

# Xuất dữ liệu thật của node từ Backend ra file CSV
py -3.12 ai\fetch_data.py --device_id node-01 --out ai\data\readings.csv
```
Chạy `predict.py` xong, Dashboard tự lấy dự báo mới trong vòng 5 phút (hoặc bấm F5).

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

---

## 8. Lỗi thường gặp

| Hiện tượng | Nguyên nhân | Cách xử lý |
|---|---|---|
| `npm error enoent ... pbl4\package.json` | Chạy `npm` ở thư mục gốc | `cd frontend` rồi chạy lại |
| `docker: ... cannot connect to the Docker daemon` | Docker Desktop chưa mở | Mở Docker Desktop, đợi chạy xong rồi chạy lại |
| `[Errno 10048] ... address already in use` khi chạy Backend | Đang có Backend khác chiếm cổng 8000 | Đóng terminal Backend cũ, hoặc tắt hết rồi chạy lại |
| Dashboard hiện "dữ liệu mẫu" | Backend chưa chạy hoặc bị lỗi | Xem Terminal 2, chạy lại uvicorn |
| Dashboard không tự cập nhật | Backend vừa khởi động lại, WebSocket bị ngắt | Bấm F5 trên trình duyệt |
| Node báo `Kết nối MQTT thất bại, rc=-2` | Sai IP broker, Docker chưa chạy, tường lửa chặn | Kiểm tra `ipconfig`, Docker, cho phép Docker Desktop qua Windows Firewall |
| Backend báo `422 ... field type conflict` | Lệch kiểu số nguyên / số thực khi ghi InfluxDB | Đã sửa trong code; nếu gặp lại thì pull code mới từ `main` |
| Dữ liệu bị lệch 7 tiếng | Firmware cũ gửi giờ không có `+07:00` | Nạp firmware mới nhất |
| `predict.py` báo không tìm thấy model | Chạy sai thư mục | Chạy ở thư mục gốc `pbl4` như mục 5 |
| GitHub Desktop báo `index.lock` | Một lệnh git trước bị dừng giữa chừng | Đóng các cửa sổ git đang chạy rồi xoá file `.git\index.lock` |

---

## 9. Lấy code mới và đẩy code (GitHub Desktop)

- **Trước khi làm:** chuyển sang nhánh `main` → **Fetch origin** → **Pull origin**.
- **Làm việc:** tạo nhánh mới (**Current Branch → New Branch**), sửa code.
- **Đẩy code:** tick file → ghi nội dung commit → **Commit** → **Push origin** → **Create Pull Request** vào `main`.
- Có thư viện mới trong `requirements.txt` hoặc `package.json` thì chạy lại các lệnh ở mục 1.
