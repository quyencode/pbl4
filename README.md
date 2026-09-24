# PBL4 — Giám sát và Dự báo Chất lượng Không khí Thông minh

# 1. Giới thiệu dự án

Hệ thống IoT + AI khép kín: **Cảm biến → ESP32 → MQTT → Backend (InfluxDB/PostgreSQL) →
Mô hình AI dự báo → Web Dashboard**. GVHD: Huỳnh Hữu Hưng. Nhóm 4 người, mỗi người làm
chủ một khối kỹ thuật từ đầu đến cuối (code → test → tích hợp).

| Người | Khối phụ trách |
|---|---|
| 📡 **Đạt** | IoT / Cảm biến & Thu thập dữ liệu |
| 🖥️ **Bình** | Mạng máy tính / Backend & Database |
| 🤖 **Lợi** | AI / Dự báo chất lượng không khí |
| 🎨 **Quyến** | Web Dashboard / Tích hợp hệ thống & QA |

---

# 2. Cấu trúc thư mục dự án

```text
pbl4-air-quality/
│
├── docker-compose.yml
├── .env.example
├── .gitignore
├── README.md
│
├── iot/
│   ├── mqtt_data_contract.md
│   └── esp32_sensor_node/
│       └── esp32_sensor_node.ino
│
├── backend/
│   ├── requirements.txt
│   └── app/
│       ├── main.py
│       ├── mqtt_subscriber.py
│       └── schemas.py
│
├── ai/
│   ├── requirements.txt
│   ├── fetch_data.py
│   ├── preprocess.py
│   ├── train_model.py
│   ├── predict.py
│   ├── MODEL_CARD.md
│   └── model/
│
├── database/
│   └── init_postgres.sql
│
└── frontend/
    ├── package.json
    ├── index.html
    └── src/
        ├── main.jsx
        ├── App.jsx
        └── api.js
```

---

# 3. Nguyên tắc làm việc nhóm

## Nguyên tắc — Mỗi task phải có kiểm tra (test)

```text
Code
  ↓
Test / chạy thử
  ↓
Đối chiếu kết quả với data contract
  ↓
Review chéo
  ↓
Merge
```

## Nguyên tắc — Data contract là bất biến trong tuần

Không ai được tự ý đổi định dạng JSON/API đã chốt ở Tuần 1 (`iot/mqtt_data_contract.md`)
nếu chưa thông báo và được cả 4 người đồng ý.

## Nguyên tắc — Mock trước, thật sau

Mỗi người có thể phát triển độc lập bằng dữ liệu giả lập đúng theo data contract, không
cần chờ module khác xong hẳn.

---

# 4. TUẦN 1 – KHUNG DỰ ÁN + DATA CONTRACT + MÔI TRƯỜNG

## 🎯 Mục tiêu tuần

- [ ] Data contract (JSON MQTT + REST API) được chốt và không đổi nữa
- [ ] Repository + khung thư mục được tạo
- [ ] Mỗi người dựng xong môi trường phát triển riêng
- [ ] Mỗi khối có bản "Hello World" chạy được (chưa cần đúng logic)

---

# 4.1. 🤝 CẢ NHÓM – NGÀY 1–2

## Task 1.1 – Chốt data contract

### Việc cần làm

- [x] Thống nhất field & đơn vị: `pm25`, `pm10` (µg/m³), `co2` (ppm), `temperature` (°C), `humidity` (%)
- [x] Thống nhất định dạng thời gian: ISO-8601, múi giờ thống nhất
- [x] Thống nhất topic MQTT: `sensors/<device_id>/data`
- [x] Thống nhất danh sách endpoint REST: `/api/readings`, `/api/readings/latest`, `/api/forecasts`, `/api/alerts/config`, `/ws/live`
- [x] Ghi lại toàn bộ vào `iot/mqtt_data_contract.md`

```text
size/nồng độ → µg/m³ hoặc ppm (ghi rõ theo từng field)
thời gian     → ISO-8601 (VD: 2026-09-22T09:30:00)
device_id     → dạng "node-XX"
```

### Kiểm tra

- [x] Cả 4 người giải thích giống nhau khi hỏi cùng một field
- [x] Không có module nào tự đặt field mới ngoài contract

---

## Task 1.2 – Tạo repository & khung thư mục

### Việc cần làm

- [x] Tạo Git repository chung
- [ ] Tạo branch `develop`
- [ ] Tạo branch riêng: `feature/iot`, `feature/backend`, `feature/ai`, `feature/web`
- [x] Tạo khung thư mục theo mục 2

### Kiểm tra

- [ ] Cả 4 người clone và build/run được project rỗng
- [ ] `.gitignore` chặn đúng `.env`, `node_modules/`, `__pycache__/`, `*.h5/.keras`

---

# 4.2. 📡 ĐẠT – TUẦN 1

## Task A1.1 – Khảo sát linh kiện & sơ đồ đấu nối

### File

```text
iot/esp32_sensor_node/wiring_diagram.md   (mới tạo)
```

### Việc cần làm

- [x] Đọc datasheet PMS5003 (PM2.5/PM10), MH-Z19B (CO2), DHT22 (nhiệt độ/độ ẩm)
- [x] Xác định chân UART/I2C nối với ESP32
- [x] Vẽ sơ đồ đấu nối (tay hoặc Fritzing)
- [x] Lập danh sách linh kiện cần mua/mượn

### Kiểm tra

- [ ] Sơ đồ không trùng chân giữa các cảm biến
- [x] Bình và Quyến đọc hiểu được sơ đồ mà không cần hỏi lại

---

## Task A1.2 – Dựng môi trường lập trình ESP32

### Việc cần làm

- [x] Cài Arduino IDE hoặc PlatformIO
- [x] Cài thư viện `PubSubClient`, `ArduinoJson`, `DHT sensor library`
- [x] Nạp thử chương trình Blink lên board ESP32
- [x] Test kết nối Wi-Fi cơ bản (in IP ra Serial Monitor)

### Kiểm tra

- [ ] Board nhận code, không lỗi upload
- [ ] Serial Monitor in đúng IP sau khi kết nối Wi-Fi

---

# 4.3. 🖥️ BÌNH – TUẦN 1

## Task B1.1 – Dựng hạ tầng bằng Docker

### File

```text
docker-compose.yml
.env.example
```

### Việc cần làm

- [x] Viết `docker-compose.yml` gồm Mosquitto, InfluxDB, PostgreSQL
- [ ] Chạy `docker compose up -d`, kiểm tra 3 service đều "healthy"
- [ ] Test publish/subscribe thử bằng `mosquitto_pub`/`mosquitto_sub`

### Kiểm tra

- [ ] `docker ps` hiển thị đủ 3 container đang chạy
- [ ] Gửi 1 message MQTT test và subscribe nhận lại được

---

## Task B1.2 – Viết schema PostgreSQL nháp

### File

```text
database/init_postgres.sql
```

### Việc cần làm

- [x] Tạo bảng `devices`, `alert_configs`, `forecast_runs`, `forecast_points`
- [x] Insert dữ liệu mẫu cho 1 node test (`node-01`)

### Kiểm tra

- [ ] Schema chạy không lỗi khi PostgreSQL khởi tạo (`docker-entrypoint-initdb.d`)
- [ ] Query `SELECT * FROM devices;` trả về đúng dữ liệu mẫu

---

# 4.4. 🤖 LỢI – TUẦN 1

## Task C1.1 – Chuẩn bị dữ liệu mẫu (mock)

### File

```text
ai/data/mock_readings.csv   (mới tạo)
```

### Việc cần làm

- [x] Viết script sinh dữ liệu PM2.5/PM10/CO2/nhiệt độ/độ ẩm giả lập theo giờ, trong 30 ngày
- [x] Đảm bảo dữ liệu có dao động ngày/đêm hợp lý (không phẳng)
- [x] Lưu thành CSV đúng cột theo data contract

### Kiểm tra

- [x] File CSV có đủ cột: `timestamp, pm25, pm10, co2, temperature, humidity`
- [x] Không có giá trị âm bất hợp lý

---

## Task C1.2 – Dựng môi trường Python cho AI

### File

```text
ai/requirements.txt
```

### Việc cần làm

- [x] Tạo virtualenv riêng cho `ai/`
- [x] Cài `pandas`, `numpy`, `scikit-learn`, `tensorflow`, `matplotlib`
- [x] Test import toàn bộ thư viện không lỗi

### Kiểm tra

- [x] `python -c "import tensorflow"` chạy không lỗi
- [x] `pip freeze` khớp với `requirements.txt`

---

# 4.5. 🎨 QUYẾN – TUẦN 1

## Task D1.1 – Vẽ wireframe Dashboard

### Việc cần làm

- [x] Phác thảo màn hình chính: AQI hiện tại, PM2.5, trạng thái, biểu đồ xu hướng
- [x] Phác thảo khu vực cấu hình ngưỡng cảnh báo
- [x] Thống nhất bảng màu & font chữ cơ bản

### Kiểm tra

- [x] Cả nhóm xem và đồng ý wireframe trước khi code
- [ ] Wireframe thể hiện đủ các phần dữ liệu backend sẽ cung cấp (theo data contract)

---

## Task D1.2 – Dựng project Frontend (Vite + React)

### File

```text
frontend/package.json
frontend/index.html
frontend/src/main.jsx
frontend/src/App.jsx
```

### Việc cần làm

- [x] Khởi tạo project Vite + React
- [x] Cài `recharts`
- [x] Chạy `npm run dev`, hiển thị trang "Hello PBL4" cơ bản

### Kiểm tra

- [x] Trang chạy tại `http://localhost:5173` không lỗi console
- [x] Hot reload hoạt động khi sửa `App.jsx`

---

# 4.6. ✅ CHECKPOINT CUỐI TUẦN 1

## Đạt
- [ ] Sơ đồ đấu nối hoàn chỉnh
- [ ] Môi trường Arduino/PlatformIO chạy được
- [ ] Board kết nối Wi-Fi thành công

## Bình
- [ ] Docker compose chạy đủ 3 service
- [ ] Schema PostgreSQL khởi tạo thành công
- [ ] Test MQTT pub/sub thủ công thành công

## Lợi
- [ ] Có dữ liệu mock hợp lệ (30 ngày)
- [ ] Môi trường Python AI chạy đủ thư viện

## Quyến
- [ ] Wireframe được cả nhóm chốt
- [ ] Project frontend chạy "Hello PBL4"

## Cả nhóm
- [ ] `iot/mqtt_data_contract.md` hoàn chỉnh, mọi người đọc hiểu như nhau
- [ ] Repository có đủ 4 branch `feature/*`

```text
week1-done
```

---

# 5. TUẦN 2 – HẠ TẦNG CƠ BẢN CHẠY ĐƯỢC

## 🎯 Mục tiêu tuần

```text
Đọc cảm biến riêng lẻ
  ↓
Đóng gói JSON đúng contract
  ↓
MQTT broker nhận được message thật
  ↓
Ghi thử vào InfluxDB
  ↓
Dashboard hiển thị dữ liệu tĩnh/mock
```

---

# 5.1. 📡 ĐẠT – TUẦN 2

## Task A2.1 – Đọc thử từng cảm biến qua Serial Monitor

### File

```text
iot/esp32_sensor_node/esp32_sensor_node.ino
```

### Hàm

```cpp
readPMS5003()
readMHZ19B()
dht.readTemperature() / dht.readHumidity()
```

### Việc cần làm

- [ ] Đọc riêng PMS5003, in giá trị PM2.5/PM10 ra Serial
- [ ] Đọc riêng MH-Z19B, in giá trị CO2 ra Serial
- [ ] Đọc riêng DHT22, in nhiệt độ/độ ẩm ra Serial

### Kiểm tra

- [ ] Giá trị đọc được nằm trong dải hợp lý (PM2.5 > 0, CO2 300–5000 ppm)
- [ ] Không có giá trị `NaN` liên tục khi cảm biến hoạt động bình thường

---

## Task A2.2 – Hàm đóng gói JSON theo data contract

### Hàm

```cpp
buildPayload()
```

### Việc cần làm

- [ ] Gộp 5 giá trị cảm biến + `device_id` + `timestamp` vào 1 JSON
- [ ] Xử lý trường hợp cảm biến lỗi → gửi `null` thay vì crash

### Kiểm tra

- [ ] `Serial.println(buildPayload())` in ra đúng format JSON như trong `mqtt_data_contract.md`
- [ ] JSON parse ngược lại được (dán vào jsonlint không lỗi)

---

# 5.2. 🖥️ BÌNH – TUẦN 2

## Task B2.1 – Test MQTT broker với dữ liệu thật

### Việc cần làm

- [ ] Subscribe topic `sensors/+/data` bằng `mosquitto_sub`
- [ ] Nhận thử message publish thủ công đúng format contract

### Kiểm tra

- [ ] Message nhận được khớp 100% với data contract
- [ ] Topic wildcard `+` hoạt động đúng với nhiều `device_id`

---

## Task B2.2 – Khung `mqtt_subscriber.py`

### File

```text
backend/app/mqtt_subscriber.py
```

### Hàm

```python
on_connect()
on_message()
validate_payload()
write_to_influx()
```

### Việc cần làm

- [ ] Kết nối MQTT broker, subscribe đúng topic
- [ ] Parse JSON, validate tối thiểu (`device_id` bắt buộc)
- [ ] Ghi thử 1 điểm dữ liệu vào InfluxDB

### Kiểm tra

- [ ] Ghi thành công 1 record, xem lại được trên InfluxDB UI
- [ ] Payload sai định dạng bị log cảnh báo, không làm crash service

---

# 5.3. 🤖 LỢI – TUẦN 2

## Task C2.1 – Hàm tiền xử lý cơ bản

### File

```text
ai/preprocess.py
```

### Hàm

```python
clean_data()
resample_hourly()
```

### Việc cần làm

- [ ] `clean_data()`: loại bản ghi thiếu target, nội suy các cột số
- [ ] `resample_hourly()`: đưa dữ liệu về tần suất 1 giờ/điểm

### Kiểm tra

- [ ] Chạy trên `ai/data/mock_readings.csv` không lỗi
- [ ] Số dòng sau `resample_hourly()` đúng bằng số giờ trong khoảng dữ liệu

---

## Task C2.2 – Test pipeline với dữ liệu mock

### Việc cần làm

- [ ] Chạy toàn bộ `clean_data → resample_hourly` trên dữ liệu mock
- [ ] In thử `head()`/`describe()` để kiểm tra hợp lý

### Kiểm tra

- [ ] Không còn giá trị `NaN` sau bước tiền xử lý
- [ ] Thống kê mô tả (min/max/mean) hợp lý với dữ liệu mock đã tạo

---

# 5.4. 🎨 QUYẾN – TUẦN 2

## Task D2.1 – Layout trang chính

### File

```text
frontend/src/App.jsx
```

### Việc cần làm

- [ ] Dựng `StatCard` (AQI hiện tại, PM2.5, Trạng thái)
- [ ] Dựng khung vị trí cho 2 biểu đồ (lịch sử + dự báo)

### Kiểm tra

- [ ] Layout không vỡ khi thu nhỏ cửa sổ trình duyệt
- [ ] `StatCard` hiển thị đúng khi giá trị là `null`/`—`

---

## Task D2.2 – Gọi thử API mock

### File

```text
frontend/src/api.js
```

### Việc cần làm

- [ ] Viết hàm `getLatestReadings()`, `getReadingsHistory()`
- [ ] Trỏ tạm tới dữ liệu giả lập (JSON tĩnh) khi backend chưa sẵn sàng

### Kiểm tra

- [ ] Dashboard hiển thị được dữ liệu giả lập không lỗi console
- [ ] Chuyển sang API thật chỉ cần đổi `API_BASE_URL`, không sửa logic hiển thị

---

# 5.5. ✅ CHECKPOINT CUỐI TUẦN 2

## Đạt
- [ ] Đọc riêng từng cảm biến ra số liệu hợp lý
- [ ] `buildPayload()` xuất đúng JSON theo contract

## Bình
- [ ] MQTT broker nhận đúng message thật
- [ ] `mqtt_subscriber.py` ghi được 1 record vào InfluxDB

## Lợi
- [ ] `clean_data()` + `resample_hourly()` chạy đúng trên mock data

## Quyến
- [ ] Layout trang chính hoàn chỉnh
- [ ] Dashboard hiển thị dữ liệu mock qua `api.js`

```text
week2-done
```

---

# 6. TUẦN 3 – MODULE LÕI CỦA TỪNG KHỐI

## 🎯 Mục tiêu tuần

- [ ] Node ESP32 publish MQTT hoàn chỉnh, liên tục
- [ ] Backend nhận & lưu dữ liệu thật, có `GET /api/readings`
- [ ] AI có hàm `fetch_data()` + `sliding window` hoàn chỉnh
- [ ] Dashboard vẽ được biểu đồ lịch sử từ API thật (hoặc mock nâng cao)

---

# 6.1. 📡 ĐẠT – TUẦN 3

## Task A3.1 – Firmware publish MQTT hoàn chỉnh

### File

```text
iot/esp32_sensor_node/esp32_sensor_node.ino
```

### Hàm

```cpp
reconnectMQTT()
mqttClient.publish()
```

### Việc cần làm

- [ ] Ghép `readAllSensors()` + `buildPayload()` + publish theo chu kỳ `SEND_INTERVAL_MS`
- [ ] Xử lý reconnect khi mất kết nối MQTT

### Kiểm tra

- [ ] Node tự publish đều đặn mỗi 5 phút không cần can thiệp
- [ ] Rút dây mạng rồi cắm lại, node tự reconnect và publish tiếp

---

## Task A3.2 – Test gửi dữ liệu liên tục

### Việc cần làm

- [ ] Chạy node liên tục tối thiểu 30 phút, ghi log số message gửi thành công
- [ ] Đối chiếu số message với số lần subscribe nhận được ở máy Bình

### Kiểm tra

- [ ] Số message gửi = số message Backend nhận (không thất thoát trong điều kiện mạng ổn định)

---

# 6.2. 🖥️ BÌNH – TUẦN 3

## Task B3.1 – Ghi dữ liệu thật vào InfluxDB

### File

```text
backend/app/mqtt_subscriber.py
```

### Việc cần làm

- [ ] Nhận dữ liệu thật từ node của Đạt (không còn test thủ công)
- [ ] Ghi liên tục, không rò rỉ kết nối (connection leak)

### Kiểm tra

- [ ] Chạy 30 phút liên tục không crash, không tăng bộ nhớ bất thường

---

## Task B3.2 – `GET /api/readings` hoạt động

### File

```text
backend/app/main.py
```

### Hàm

```python
get_readings()
```

### Việc cần làm

- [ ] Viết Flux/query lấy dữ liệu theo `device_id`, `from`, `to`, `limit`
- [ ] Trả JSON đúng `ReadingsResponse` trong `schemas.py`

### Kiểm tra

- [ ] Gọi qua `/docs` (Swagger UI) trả đúng dữ liệu đã ghi ở Task B3.1
- [ ] `limit` hoạt động đúng, không trả nhiều hơn yêu cầu

---

# 6.3. 🤖 LỢI – TUẦN 3

## Task C3.1 – `fetch_data.py` lấy dữ liệu từ backend

### File

```text
ai/fetch_data.py
```

### Hàm

```python
fetch_readings()
```

### Việc cần làm

- [ ] Gọi `GET /api/readings` của Bình, chuyển kết quả thành DataFrame
- [ ] Lưu ra CSV để dùng lại khi huấn luyện

### Kiểm tra

- [ ] Dữ liệu tải về khớp số dòng với dữ liệu Bình đang có trong InfluxDB

---

## Task C3.2 – Hoàn chỉnh `make_sliding_windows()`

### File

```text
ai/preprocess.py
```

### Hàm

```python
make_sliding_windows()
```

### Việc cần làm

- [ ] Cài đặt đúng công thức cửa sổ trượt (window_size, horizon)
- [ ] Viết test nhỏ với mảng số giả lập để kiểm tra shape đầu ra

### Kiểm tra

- [ ] `X.shape == (n, window_size, n_features)`
- [ ] `y.shape == (n, horizon)`

---

# 6.4. 🎨 QUYẾN – TUẦN 3

## Task D3.1 – Kết nối dashboard tới `GET /api/readings`

### File

```text
frontend/src/api.js
```

### Việc cần làm

- [ ] Đổi `API_BASE_URL` sang backend thật (dev) của Bình
- [ ] Xử lý lỗi khi API chưa sẵn sàng (hiển thị thông báo, không crash trắng trang)

### Kiểm tra

- [ ] Tắt backend → dashboard vẫn hiển thị, chỉ báo lỗi kết nối, không crash

---

## Task D3.2 – Biểu đồ lịch sử cơ bản

### File

```text
frontend/src/App.jsx
```

### Việc cần làm

- [ ] Vẽ `LineChart` (Recharts) cho PM2.5 theo thời gian
- [ ] Format trục X gọn (ẩn nếu quá dày, theo code mẫu hiện tại)

### Kiểm tra

- [ ] Biểu đồ hiển thị đúng thứ tự thời gian, không bị đảo ngược
- [ ] Không lỗi khi dữ liệu rỗng (mới bật hệ thống, chưa có lịch sử)

---

# 6.5. ✅ CHECKPOINT CUỐI TUẦN 3

## Đạt
- [ ] Node publish liên tục, tự reconnect khi mất mạng

## Bình
- [ ] Ghi dữ liệu thật ổn định 30 phút
- [ ] `GET /api/readings` trả đúng dữ liệu

## Lợi
- [ ] `fetch_data.py` lấy đúng dữ liệu từ backend
- [ ] `make_sliding_windows()` shape đúng

## Quyến
- [ ] Dashboard vẽ được biểu đồ lịch sử từ API thật

```text
week3-done
```

---

# 7. TUẦN 4 – KẾT NỐI DỮ LIỆU THẬT LẦN ĐẦU (END-TO-END CƠ BẢN)

## 🎯 Mục tiêu tuần

```text
Node thật → MQTT → Backend → API → Dashboard
```
chạy được xuyên suốt lần đầu tiên, dù còn thô.

---

# 7.1. 📡 ĐẠT – TUẦN 4

## Task A4.1 – Lắp node hoàn chỉnh, chạy độc lập

### Việc cần làm

- [ ] Đóng gói node vào hộp/case tạm, cấp nguồn ổn định
- [ ] Đặt node ở vị trí thử nghiệm thực tế (phòng lab hoặc ngoài trời)

### Kiểm tra

- [ ] Node hoạt động liên tục 12 giờ không cần cắm lại máy tính

---

## Task A4.2 – Cơ chế buffer offline

### File

```text
iot/esp32_sensor_node/esp32_sensor_node.ino
```

### Hàm

```cpp
bufferPush()
flushBuffer()
```

### Việc cần làm

- [ ] Lưu payload vào mảng vòng khi mất kết nối MQTT
- [ ] Gửi bù toàn bộ buffer khi kết nối phục hồi

### Kiểm tra

- [ ] Ngắt Wi-Fi 5 phút rồi bật lại → dữ liệu bị đệm được gửi bù đầy đủ, đúng thứ tự

---

# 7.2. 🖥️ BÌNH – TUẦN 4

## Task B4.1 – `GET /api/readings/latest`

### File

```text
backend/app/main.py
```

### Việc cần làm

- [ ] Truy vấn bản ghi mới nhất của từng `device_id`
- [ ] Trả về mảng `items` theo đúng schema

### Kiểm tra

- [ ] Kết quả cập nhật đúng sau mỗi lần node gửi dữ liệu mới

---

## Task B4.2 – Theo dõi luồng dữ liệu thật từ node Đạt

### Việc cần làm

- [ ] Theo dõi log liên tục trong 1 ngày, ghi nhận số lần mất kết nối/lỗi
- [ ] Trao đổi với Đạt nếu phát hiện dữ liệu bất thường (giá trị âm, nhảy vọt)

### Kiểm tra

- [ ] Không có bản ghi trùng lặp bất thường trong InfluxDB
- [ ] Không có lỗi 500 khi node gửi dữ liệu liên tục

---

# 7.3. 🤖 LỢI – TUẦN 4

## Task C4.1 – Thu thập batch dữ liệu thật đầu tiên

### Việc cần làm

- [ ] Dùng `fetch_data.py` tải toàn bộ dữ liệu thật đã có từ Tuần 3–4
- [ ] Lưu thành `ai/data/node-01.csv`, backup định kỳ

### Kiểm tra

- [ ] File CSV có timestamp liên tục, không có khoảng trống lớn bất thường

---

## Task C4.2 – Đánh giá chất lượng dữ liệu

### Việc cần làm

- [ ] Kiểm tra tỉ lệ thiếu (`NaN`) theo từng cột
- [ ] Kiểm tra outlier (giá trị PM2.5/CO2 vượt ngưỡng vật lý hợp lý)
- [ ] Ghi nhận vào `ai/MODEL_CARD.md` mục "Dữ liệu"

### Kiểm tra

- [ ] Có báo cáo ngắn (vài dòng) mô tả chất lượng dữ liệu thật thu được

---

# 7.4. 🎨 QUYẾN – TUẦN 4

## Task D4.1 – Hiển thị dữ liệu thật (bỏ mock)

### Việc cần làm

- [ ] Gỡ toàn bộ dữ liệu giả lập tĩnh, chỉ dùng API thật
- [ ] Thêm trạng thái loading khi đang tải dữ liệu

### Kiểm tra

- [ ] Refresh trang nhiều lần đều lấy đúng dữ liệu mới nhất từ node thật

---

## Task D4.2 – `StatCard` hiển thị đúng AQI/PM2.5

### Việc cần làm

- [ ] Nối `StatCard` với `getLatestReadings()`
- [ ] Định dạng số liệu (làm tròn 1 chữ số thập phân)

### Kiểm tra

- [ ] Giá trị hiển thị khớp với dữ liệu mới nhất trên InfluxDB UI

---

# 7.5. ✅ CHECKPOINT CUỐI TUẦN 4

## Đạt
- [ ] Node hoạt động độc lập 12h+
- [ ] Buffer offline hoạt động đúng

## Bình
- [ ] `readings/latest` cập nhật đúng thời gian thực
- [ ] Theo dõi ổn định 1 ngày không lỗi nghiêm trọng

## Lợi
- [ ] Có bộ dữ liệu thật đầu tiên, đã đánh giá chất lượng

## Quyến
- [ ] Dashboard chạy hoàn toàn bằng dữ liệu thật, không còn mock

## Cả nhóm
- [ ] Pipeline Node → MQTT → Backend → API → Dashboard chạy xuyên suốt ít nhất 1 lần demo

```text
week4-done
```

---

# 8. TUẦN 5 – HOÀN THIỆN API & MÔ HÌNH AI PHIÊN BẢN 1

## 🎯 Mục tiêu tuần

- [ ] WebSocket realtime hoạt động
- [ ] Mô hình LSTM v1 huấn luyện xong, có số liệu MAE/RMSE/MAPE
- [ ] Dashboard vẽ biểu đồ realtime

---

# 8.1. 📡 ĐẠT – TUẦN 5

## Task A5.1 – Hiệu chuẩn cảm biến

### Việc cần làm

- [ ] So sánh số liệu node với 1 nguồn tham chiếu (app AQI công cộng gần vị trí lắp đặt, hoặc cảm biến thứ 2)
- [ ] Ghi lại độ lệch (offset) nếu có, cân nhắc hiệu chỉnh trong firmware

### Kiểm tra

- [ ] Có bảng ghi log hiệu chuẩn với ít nhất 3 mốc thời gian so sánh

---

## Task A5.2 – Viết `iot/README.md`

### File

```text
iot/README.md   (mới tạo)
```

### Việc cần làm

- [ ] Hướng dẫn nạp firmware, cấu hình Wi-Fi/MQTT
- [ ] Hướng dẫn thay pin/bảo trì node

### Kiểm tra

- [ ] Quyến làm theo hướng dẫn và nạp thành công mà không cần hỏi thêm Đạt

---

# 8.2. 🖥️ BÌNH – TUẦN 5

## Task B5.1 – `WS /ws/live`

### File

```text
backend/app/main.py
```

### Hàm

```python
websocket_live()
broadcast_reading()
```

### Việc cần làm

- [ ] Chấp nhận kết nối WebSocket, giữ danh sách `active_connections`
- [ ] Đẩy dữ liệu mới ngay khi `mqtt_subscriber` ghi record mới (qua queue/callback)

### Kiểm tra

- [ ] Mở 2 tab dashboard, cả 2 đều nhận dữ liệu mới cùng lúc

---

## Task B5.2 – Khung `POST/GET /api/forecasts`

### File

```text
backend/app/main.py
```

### Việc cần làm

- [ ] `POST /api/forecasts` nhận đúng payload theo contract
- [ ] `GET /api/forecasts/latest` trả về bản ghi vừa nhận (tạm lưu in-memory hoặc DB)

### Kiểm tra

- [ ] Gửi thử payload mẫu bằng `curl`/Postman, nhận lại đúng qua `GET`

---

# 8.3. 🤖 LỢI – TUẦN 5

## Task C5.1 – Huấn luyện LSTM v1

### File

```text
ai/train_model.py
```

### Hàm

```python
build_lstm_model()
```

### Việc cần làm

- [ ] Chạy `train_model.py --model_type lstm` trên dữ liệu thật Tuần 4
- [ ] Ghi lại số epoch, thời gian huấn luyện

### Kiểm tra

- [ ] Loss giảm dần qua các epoch (không tăng bất thường)
- [ ] Mô hình lưu được file `.keras` thành công

---

## Task C5.2 – Đánh giá mô hình so với baseline

### Hàm

```python
evaluate()
persistence_baseline()
```

### Việc cần làm

- [ ] Tính MAE/RMSE/MAPE trên tập test
- [ ] So sánh với baseline Persistence

### Kiểm tra

- [ ] LSTM có MAE thấp hơn baseline (nếu không, ghi rõ nguyên nhân nghi ngờ — thường do thiếu dữ liệu)
- [ ] Kết quả được ghi vào `ai/MODEL_CARD.md`

---

# 8.4. 🎨 QUYẾN – TUẦN 5

## Task D5.1 – Kết nối WebSocket vào dashboard

### File

```text
frontend/src/api.js
frontend/src/App.jsx
```

### Hàm

```js
connectLiveSocket()
```

### Việc cần làm

- [ ] Mở kết nối `/ws/live` khi load trang
- [ ] Cập nhật `history`/`latest` khi nhận message mới (bỏ `TODO` hiện tại)

### Kiểm tra

- [ ] Khi node gửi dữ liệu mới, dashboard tự cập nhật không cần refresh trang

---

## Task D5.2 – Hiển thị "Trạng thái"

### Việc cần làm

- [ ] Tính trạng thái (Ổn định/Trung bình/Cảnh báo) dựa trên AQI/PM2.5 hiện tại
- [ ] Gắn màu sắc tương ứng cho từng mức trạng thái

### Kiểm tra

- [ ] Trạng thái đổi màu đúng khi thay đổi ngưỡng thử nghiệm

---

# 8.5. ✅ CHECKPOINT CUỐI TUẦN 5

## Đạt
- [ ] Có log hiệu chuẩn cảm biến
- [ ] `iot/README.md` hoàn chỉnh, người khác làm theo được

## Bình
- [ ] WebSocket đẩy dữ liệu realtime ổn định
- [ ] `POST/GET /api/forecasts` hoạt động cơ bản

## Lợi
- [ ] Có mô hình LSTM v1 với MAE/RMSE/MAPE ghi lại rõ ràng

## Quyến
- [ ] Dashboard cập nhật realtime qua WebSocket
- [ ] Hiển thị đúng trạng thái theo ngưỡng

```text
week5-done
```

---

# 9. TUẦN 6 – TÍCH HỢP AI VÀO HỆ THỐNG

## 🎯 Mục tiêu tuần

```text
Model đã huấn luyện
  ↓
predict.py chạy định kỳ
  ↓
POST /api/forecasts
  ↓
Lưu DB
  ↓
Hiển thị trên Dashboard
```

---

# 9.1. 📡 ĐẠT – TUẦN 6

## Task A6.1 – Lắp thêm node thứ 2 (nếu đủ điều kiện)

### Việc cần làm

- [ ] Lặp lại quy trình lắp đặt/hiệu chuẩn như node 1
- [ ] Đặt `device_id = node-02`, đảm bảo không trùng node-01

### Kiểm tra

- [ ] Backend nhận và phân biệt đúng dữ liệu 2 node riêng biệt

---

## Task A6.2 – Giám sát ổn định 48 giờ

### Việc cần làm

- [ ] Theo dõi liên tục 48h, ghi log các lần mất kết nối/lỗi cảm biến
- [ ] Tổng hợp báo cáo ổn định gửi cả nhóm

### Kiểm tra

- [ ] Uptime node trong 48h đạt tối thiểu ~95% (ghi nhận số liệu thật, không làm tròn tuỳ tiện)

---

# 9.2. 🖥️ BÌNH – TUẦN 6

## Task B6.1 – Lưu forecast vào PostgreSQL

### File

```text
backend/app/main.py
database/init_postgres.sql
```

### Việc cần làm

- [ ] Thay lưu in-memory bằng ghi thật vào `forecast_runs` + `forecast_points`
- [ ] Đảm bảo 1 lần `POST /api/forecasts` tạo đúng 1 `forecast_run` + N `forecast_points`

### Kiểm tra

- [ ] Query PostgreSQL thấy đúng số điểm dự báo tương ứng `horizon_hours`

---

## Task B6.2 – `GET /api/forecasts/latest` đọc từ DB

### Việc cần làm

- [ ] Đổi từ in-memory sang query PostgreSQL (lấy `forecast_run` mới nhất theo `device_id`)

### Kiểm tra

- [ ] Kết quả trả về đúng dự báo mới nhất, không lẫn dự báo cũ

---

# 9.3. 🤖 LỢI – TUẦN 6

## Task C6.1 – Hoàn thiện `predict.py`

### File

```text
ai/predict.py
```

### Hàm

```python
run_once()
```

### Việc cần làm

- [ ] Lấy dữ liệu gần nhất, chạy mô hình, gửi `POST /api/forecasts`
- [ ] Lưu lại `scaler` đã fit lúc train (thay vì fit lại mỗi lần predict — xử lý `TODO` hiện tại)

### Kiểm tra

- [ ] Chạy `python predict.py --device_id node-01` thành công, Bình xác nhận nhận được dữ liệu

---

## Task C6.2 – Test chạy dự báo định kỳ

### Việc cần làm

- [ ] Thiết lập chạy `predict.py` mỗi giờ (cron job hoặc chạy tay nhiều lần trong ngày để test)
- [ ] Theo dõi 24h xem có lỗi phát sinh không

### Kiểm tra

- [ ] Chạy 24 lần liên tiếp không crash, không rò rỉ bộ nhớ

---

# 9.4. 🎨 QUYẾN – TUẦN 6

## Task D6.1 – Hiển thị dự báo AI trên dashboard

### File

```text
frontend/src/App.jsx
```

### Việc cần làm

- [ ] Nối `getLatestForecast()` với biểu đồ dự báo
- [ ] Vẽ 2 đường: PM2.5 thực tế (lịch sử) và PM2.5 dự báo trên cùng biểu đồ hoặc 2 biểu đồ liền kề

### Kiểm tra

- [ ] Biểu đồ dự báo cập nhật đúng sau mỗi lần `predict.py` chạy

---

## Task D6.2 – Xử lý trạng thái "chưa có dự báo"

### Việc cần làm

- [ ] Hiển thị thông báo rõ ràng khi API trả 404 (chưa có forecast)
- [ ] Không để trắng trang hoặc lỗi console khi thiếu dữ liệu dự báo

### Kiểm tra

- [ ] Với node mới chưa từng chạy AI, dashboard vẫn hiển thị gọn gàng, không lỗi

---

# 9.5. ✅ CHECKPOINT CUỐI TUẦN 6

## Đạt
- [ ] (Tuỳ điều kiện) Có 2 node hoạt động song song
- [ ] Báo cáo ổn định 48h

## Bình
- [ ] Forecast được lưu và đọc đúng từ PostgreSQL

## Lợi
- [ ] `predict.py` chạy ổn định, tự động gửi dự báo

## Quyến
- [ ] Dashboard hiển thị đầy đủ: dữ liệu thật + dự báo AI

```text
week6-done
```

---

# 10. TUẦN 7 – TÍNH NĂNG CẢNH BÁO

## 🎯 Mục tiêu tuần

- [ ] Cấu hình được ngưỡng cảnh báo theo node
- [ ] Hệ thống tự phát hiện khi vượt ngưỡng
- [ ] Mô hình AI có phiên bản 2 (CNN-LSTM) để so sánh

---

# 10.1. 📡 ĐẠT – TUẦN 7

## Task A7.1 – Kiểm tra độ trôi cảm biến

### Việc cần làm

- [ ] So sánh số liệu hiện tại với log hiệu chuẩn ở Tuần 5
- [ ] Hiệu chỉnh lại nếu độ lệch vượt quá mức chấp nhận được

### Kiểm tra

- [ ] Ghi rõ mức trôi (nếu có) vào tài liệu — phục vụ phần "Thách thức" trong báo cáo

---

## Task A7.2 – Tối ưu chu kỳ gửi dữ liệu

### Việc cần làm

- [ ] Đánh giá lại `READ_INTERVAL_MS`/`SEND_INTERVAL_MS` có hợp lý không
- [ ] Cân bằng giữa độ mới của dữ liệu và tiêu thụ điện/băng thông

### Kiểm tra

- [ ] Có ghi chú lý do chọn chu kỳ cuối cùng (đưa vào báo cáo)

---

# 10.2. 🖥️ BÌNH – TUẦN 7

## Task B7.1 – `GET/POST /api/alerts/config`

### File

```text
backend/app/main.py
database/init_postgres.sql
```

### Việc cần làm

- [ ] Đọc/ghi thật vào bảng `alert_configs` (thay vì trả giá trị mặc định cố định)

### Kiểm tra

- [ ] Cập nhật ngưỡng qua API, query lại DB thấy đúng giá trị mới

---

## Task B7.2 – Logic phát hiện vượt ngưỡng

### Hàm

```python
# trong mqtt_subscriber.py, sau write_to_influx()
```

### Việc cần làm

- [ ] Sau khi ghi dữ liệu mới, so sánh với `alert_configs` của node đó
- [ ] Nếu vượt ngưỡng, tạo bản ghi trong `alert_events`

### Kiểm tra

- [ ] Hạ ngưỡng test thấp hơn giá trị hiện tại → 1 `alert_event` mới được tạo đúng

---

# 10.3. 🤖 LỢI – TUẦN 7

## Task C7.1 – Huấn luyện CNN-LSTM (v2)

### File

```text
ai/train_model.py
```

### Hàm

```python
build_cnn_lstm_model()
```

### Việc cần làm

- [ ] Chạy `train_model.py --model_type cnn_lstm`
- [ ] So sánh MAE/RMSE/MAPE với LSTM v1

### Kiểm tra

- [ ] Có bảng so sánh rõ ràng 2 mô hình + baseline, chọn ra mô hình dùng chính thức

---

## Task C7.2 – Cập nhật Model Card

### File

```text
ai/MODEL_CARD.md
```

### Việc cần làm

- [ ] Điền đầy đủ kiến trúc, số liệu đánh giá thật (không còn "...")
- [ ] Ghi rõ giới hạn của mô hình dựa trên dữ liệu thật đã thu thập

### Kiểm tra

- [ ] Người ngoài đọc `MODEL_CARD.md` hiểu được mô hình mà không cần hỏi thêm Lợi

---

# 10.4. 🎨 QUYẾN – TUẦN 7

## Task D7.1 – UI cấu hình ngưỡng cảnh báo

### Việc cần làm

- [ ] Form nhập `pm25_threshold`, `aqi_threshold` theo từng node
- [ ] Gọi `POST /api/alerts/config` khi lưu

### Kiểm tra

- [ ] Đổi ngưỡng trên UI, load lại trang vẫn giữ đúng giá trị đã lưu

---

## Task D7.2 – Thông báo khi vượt ngưỡng

### Việc cần làm

- [ ] Hiển thị banner/toast khi AQI/PM2.5 hiện tại vượt ngưỡng đã cấu hình
- [ ] Không spam thông báo liên tục (chỉ hiện khi trạng thái thay đổi)

### Kiểm tra

- [ ] Hạ ngưỡng test → banner cảnh báo xuất hiện đúng, không lặp lại nhiều lần không cần thiết

---

# 10.5. ✅ CHECKPOINT CUỐI TUẦN 7

## Đạt
- [ ] Đã kiểm tra & xử lý độ trôi cảm biến (nếu có)

## Bình
- [ ] Cấu hình ngưỡng đọc/ghi DB thật
- [ ] Alert event được tạo đúng khi vượt ngưỡng

## Lợi
- [ ] Có mô hình v2, đã so sánh và chọn mô hình chính thức
- [ ] Model Card hoàn chỉnh với số liệu thật

## Quyến
- [ ] UI cấu hình ngưỡng hoạt động đầy đủ
- [ ] Thông báo cảnh báo hiển thị đúng lúc

```text
week7-done
```

---

# 11. TUẦN 8 – KIỂM THỬ TÍCH HỢP TOÀN HỆ THỐNG (Quyến chủ trì)

## 🎯 Mục tiêu tuần

```text
IoT → Backend → AI → Dashboard
```
chạy thông suốt, không còn lỗi chặn (blocker) trước khi bước vào tuần hoàn thiện.

---

# 11.1. 🎨 QUYẾN – TUẦN 8 (chủ trì tích hợp)

## Task D8.1 – Viết test case end-to-end

### File

```text
tests/e2e_checklist.md   (mới tạo)
```

### Việc cần làm

- [ ] Liệt kê kịch bản: node mất mạng → phục hồi → dữ liệu đủ trên dashboard
- [ ] Liệt kê kịch bản: AQI vượt ngưỡng → cảnh báo hiển thị đúng
- [ ] Liệt kê kịch bản: chưa có dự báo → dashboard không lỗi

### Kiểm tra

- [ ] Mỗi kịch bản có bước thực hiện rõ ràng và kết quả mong đợi

---

## Task D8.2 – Tổng hợp bug tracker

### Việc cần làm

- [ ] Tạo bảng theo dõi lỗi (GitHub Issues hoặc bảng trong repo)
- [ ] Phân loại mức độ: Blocker / Major / Minor

### Kiểm tra

- [ ] Mọi lỗi phát hiện trong tuần đều được ghi nhận, có người phụ trách

---

# 11.2. 📡 ĐẠT – TUẦN 8

## Task A8.1 – Fix lỗi phần cứng phát sinh

### Việc cần làm

- [ ] Xử lý các lỗi được Quyến ghi nhận liên quan tới node/firmware

### Kiểm tra

- [ ] Lỗi được đánh dấu "Resolved" kèm mô tả cách khắc phục

---

## Task A8.2 – Xác nhận buffer offline khi test mất mạng thật

### Việc cần làm

- [ ] Phối hợp với Quyến chạy lại kịch bản mất mạng trong test case D8.1

### Kiểm tra

- [ ] Kết quả khớp với "kết quả mong đợi" đã viết ở Task D8.1

---

# 11.3. 🖥️ BÌNH – TUẦN 8

## Task B8.1 – Fix lỗi backend phát hiện khi test tích hợp

### Việc cần làm

- [ ] Xử lý các lỗi API/DB được ghi nhận trong bug tracker

### Kiểm tra

- [ ] Lỗi được đánh dấu "Resolved", có ghi chú nguyên nhân

---

## Task B8.2 – Kiểm tra khả năng chịu tải cơ bản

### Việc cần làm

- [ ] Giả lập nhiều node gửi dữ liệu đồng thời (script publish MQTT song song)
- [ ] Theo dõi CPU/RAM của backend khi tải tăng

### Kiểm tra

- [ ] Backend không crash với số node giả lập gấp 3–5 lần thực tế hiện có

---

# 11.4. 🤖 LỢI – TUẦN 8

## Task C8.1 – Fix lỗi pipeline dữ liệu

### Việc cần làm

- [ ] Xử lý các trường hợp dữ liệu thiếu/lệch định dạng được phát hiện khi test tích hợp

### Kiểm tra

- [ ] Pipeline không crash khi API trả về dữ liệu rỗng hoặc thiếu cột

---

## Task C8.2 – Đảm bảo `predict.py` ổn định

### Việc cần làm

- [ ] Thêm xử lý khi dữ liệu không đủ `WINDOW_SIZE` (đã có `TODO`, hoàn thiện thật)
- [ ] Thêm log rõ ràng khi bỏ qua một lần chạy dự báo

### Kiểm tra

- [ ] Chạy với node vừa mới bật (ít dữ liệu) không làm sập service

---

# 11.5. ✅ CHECKPOINT CUỐI TUẦN 8

## Cả nhóm
- [ ] Toàn bộ test case trong `tests/e2e_checklist.md` đạt kết quả mong đợi
- [ ] Không còn bug mức "Blocker" trong bug tracker
- [ ] Demo thử toàn hệ thống trước nhóm thành công 1 lần trọn vẹn

```text
week8-done
```

---

# 12. TUẦN 9 – HOÀN THIỆN & TỐI ƯU

## 🎯 Mục tiêu tuần

- [ ] Mỗi khối được dọn code, viết tài liệu đầy đủ
- [ ] Regression test toàn bộ tính năng đã làm từ Tuần 1–8

---

# 12.1. 📡 ĐẠT – TUẦN 9

## Task A9.1 – Hoàn thiện tài liệu & minh chứng

### Việc cần làm

- [ ] Hoàn thiện `iot/README.md`
- [ ] Chụp ảnh/quay video node hoạt động thực tế

### Kiểm tra

- [ ] Ảnh/video đủ rõ để đưa vào báo cáo và slide

---

## Task A9.2 – Dọn code firmware

### Việc cần làm

- [ ] Xoá code test/debug không cần thiết
- [ ] Viết comment rõ ràng cho từng hàm chính

### Kiểm tra

- [ ] Người khác đọc code hiểu được luồng chạy mà không cần hỏi thêm

---

# 12.2. 🖥️ BÌNH – TUẦN 9

## Task B9.1 – Tối ưu & logging

### File

```text
backend/app/main.py
backend/app/mqtt_subscriber.py
```

### Việc cần làm

- [ ] Thêm logging đầy đủ cho các luồng chính (nhận MQTT, ghi DB, lỗi API)
- [ ] Kiểm tra và xử lý các điểm có thể tối ưu tốc độ truy vấn

### Kiểm tra

- [ ] Log đủ để debug một sự cố mà không cần thêm print tạm thời

---

## Task B9.2 – Hoàn chỉnh tài liệu API

### Việc cần làm

- [ ] Rà soát toàn bộ docstring/mô tả trong FastAPI để Swagger UI (`/docs`) rõ ràng
- [ ] Xuất tài liệu API (ảnh chụp hoặc export) đưa vào báo cáo

### Kiểm tra

- [ ] Người ngoài nhóm đọc `/docs` hiểu và gọi thử được API mà không cần hỏi Bình

---

# 12.3. 🤖 LỢI – TUẦN 9

## Task C9.1 – Hoàn thiện Model Card & biểu đồ

### File

```text
ai/MODEL_CARD.md
```

### Việc cần làm

- [ ] Vẽ biểu đồ so sánh thực tế vs dự báo trên tập test (matplotlib)
- [ ] Chèn biểu đồ vào Model Card hoặc thư mục báo cáo

### Kiểm tra

- [ ] Biểu đồ thể hiện rõ xu hướng, có chú thích trục và đơn vị

---

## Task C9.2 – Dọn code AI

### Việc cần làm

- [ ] Xoá code thử nghiệm không dùng tới trong `ai/*.py`
- [ ] Thống nhất docstring ngắn gọn cho từng hàm

### Kiểm tra

- [ ] Toàn bộ script trong `ai/` chạy lại từ đầu (fetch → preprocess → train → predict) không lỗi

---

# 12.4. 🎨 QUYẾN – TUẦN 9

## Task D9.1 – Responsive & UI polish

### File

```text
frontend/src/App.jsx
```

### Việc cần làm

- [ ] Kiểm tra hiển thị trên kích thước màn hình di động
- [ ] Tinh chỉnh khoảng cách, màu sắc, cỡ chữ cho nhất quán

### Kiểm tra

- [ ] Không có phần tử bị tràn/che khuất trên màn hình nhỏ (< 400px)

---

## Task D9.2 – Regression test toàn bộ tính năng

### Việc cần làm

- [ ] Chạy lại toàn bộ test case trong `tests/e2e_checklist.md`
- [ ] Kiểm tra các tính năng cũ (Tuần 1–7) vẫn hoạt động sau các thay đổi mới

### Kiểm tra

- [ ] Không có tính năng cũ nào bị hỏng do thay đổi ở Tuần 8–9 (không regression)

---

# 12.5. ✅ CHECKPOINT CUỐI TUẦN 9

## Đạt
- [ ] Tài liệu + minh chứng thực tế đầy đủ
- [ ] Code firmware sạch, có comment

## Bình
- [ ] Logging đầy đủ, tài liệu API rõ ràng

## Lợi
- [ ] Model Card hoàn chỉnh với biểu đồ minh hoạ
- [ ] Code AI sạch, chạy lại toàn pipeline không lỗi

## Quyến
- [ ] Giao diện responsive tốt
- [ ] Regression test không phát hiện lỗi mới

```text
week9-done
```

---

# 13. TUẦN 10 – BÁO CÁO & BẢO VỆ ĐỒ ÁN

## 🎯 Mục tiêu tuần

```text
Báo cáo hoàn chỉnh
  ↓
Slide hoàn chỉnh
  ↓
Demo chạy trơn tru
  ↓
Tập dượt bảo vệ
```

---

# 13.1. 🤝 CẢ NHÓM – TUẦN 10

## Task 10.1 – Hoàn thiện báo cáo & slide

### Việc cần làm

- [ ] Rà soát lại `PHAN_TICH_DU_AN_PBL4.docx` với số liệu thật đã có (thay các mục "minh hoạ" bằng số liệu thực nếu có)
- [ ] Cập nhật `pbl4.pptx` nếu có thay đổi lớn so với thiết kế ban đầu
- [ ] Mỗi người viết phần mình phụ trách, 1 người tổng hợp cuối cùng (đề xuất: Quyến)

### Kiểm tra

- [ ] Không còn phần "TODO"/"..." chưa điền trong báo cáo
- [ ] Số liệu trong báo cáo khớp với số liệu thật đo được (không copy nguyên số liệu minh hoạ ban đầu)

---

## Task 10.2 – Quay video / chụp ảnh demo

### Việc cần làm

- [ ] Quay video hệ thống chạy thực tế: node đo → dashboard cập nhật → cảnh báo khi vượt ngưỡng
- [ ] Chụp ảnh lắp đặt thực tế của node

### Kiểm tra

- [ ] Video đủ rõ, có thể dùng làm minh chứng khi bảo vệ nếu demo trực tiếp gặp sự cố

---

## Task 10.3 – Tập dượt bảo vệ

### Việc cần làm

- [ ] Phân chia phần trình bày: đặt vấn đề, kiến trúc, demo, kết quả, định hướng
- [ ] Tập dượt hỏi-đáp chéo giữa các thành viên (mỗi người phải trả lời được cả phần không phải của mình ở mức tổng quan)

### Kiểm tra

- [ ] Mỗi thành viên trả lời được câu hỏi tổng quan về khối của người khác
- [ ] Tổng thời gian trình bày đúng với thời lượng cho phép của học phần

---

# 13.2. ✅ CHECKPOINT CUỐI TUẦN 10 — FINAL

- [ ] Báo cáo Word hoàn chỉnh
- [ ] Slide hoàn chỉnh
- [ ] Video/ảnh demo hệ thống thật
- [ ] Toàn bộ code đã merge vào `main`, tag `release-candidate`
- [ ] Cả 4 người đã tập dượt ít nhất 1 lần trước ngày bảo vệ

```text
week10-done / release-candidate
```

---

# 14. MA TRẬN KIỂM TRA THEO TUẦN

## Tuần 1

| Test | Người | Pass condition |
|---|---|---|
| Data contract | Cả nhóm | Cả 4 người hiểu giống nhau |
| Docker services | Bình | 3 container "healthy" |
| Board Wi-Fi | Đạt | In đúng IP qua Serial |
| Mock data | Lợi | CSV đủ cột, không âm bất hợp lý |
| Frontend chạy | Quyến | "Hello PBL4" hiển thị đúng |

## Tuần 2

| Test | Người | Pass condition |
|---|---|---|
| Đọc cảm biến | Đạt | Giá trị trong dải hợp lý |
| MQTT pub/sub | Bình | Message khớp contract |
| Preprocess mock | Lợi | Không còn NaN sau xử lý |
| Layout | Quyến | Không vỡ khi resize |

## Tuần 3

| Test | Người | Pass condition |
|---|---|---|
| Publish liên tục | Đạt | Gửi = Nhận trong 30 phút |
| GET /api/readings | Bình | Trả đúng dữ liệu đã ghi |
| Sliding window | Lợi | Shape X/y đúng công thức |
| Biểu đồ lịch sử | Quyến | Thứ tự thời gian đúng |

## Tuần 4

| Test | Người | Pass condition |
|---|---|---|
| Node độc lập 12h | Đạt | Không cần can thiệp |
| Buffer offline | Đạt | Gửi bù đúng thứ tự |
| readings/latest | Bình | Cập nhật đúng thời gian thực |
| Dữ liệu thật | Lợi | CSV liên tục, đã đánh giá chất lượng |
| Dashboard dữ liệu thật | Quyến | Không còn mock |

## Tuần 5

| Test | Người | Pass condition |
|---|---|---|
| Hiệu chuẩn | Đạt | Có log ≥ 3 mốc so sánh |
| WebSocket | Bình | 2 tab nhận đồng thời |
| LSTM v1 | Lợi | Loss giảm dần, có MAE/RMSE/MAPE |
| Realtime UI | Quyến | Tự cập nhật không cần refresh |

## Tuần 6

| Test | Người | Pass condition |
|---|---|---|
| Node thứ 2 | Đạt | Backend phân biệt đúng 2 node |
| Forecast → DB | Bình | Số điểm khớp horizon_hours |
| predict.py | Lợi | Chạy 24 lần không crash |
| Hiển thị dự báo | Quyến | Cập nhật đúng sau mỗi lần predict |

## Tuần 7

| Test | Người | Pass condition |
|---|---|---|
| Kiểm tra trôi cảm biến | Đạt | Có ghi chú mức trôi |
| alerts/config | Bình | Cập nhật DB đúng |
| Alert event | Bình | Tạo đúng khi vượt ngưỡng |
| CNN-LSTM v2 | Lợi | Có bảng so sánh với v1 |
| UI ngưỡng cảnh báo | Quyến | Lưu & load đúng |

## Tuần 8

| Test | Người | Pass condition |
|---|---|---|
| E2E mất mạng | Đạt + Quyến | Khớp kết quả mong đợi |
| Chịu tải | Bình | Không crash khi tải x3–x5 |
| Dữ liệu thiếu/lệch | Lợi | Pipeline không crash |
| Bug tracker | Quyến | Không còn Blocker |

## Tuần 9

| Test | Người | Pass condition |
|---|---|---|
| Regression | Quyến | Tính năng cũ không hỏng |
| Responsive | Quyến | Không tràn ở màn hình nhỏ |
| Pipeline AI đầy đủ | Lợi | fetch→preprocess→train→predict không lỗi |
| API docs | Bình | Gọi thử được không cần hỏi thêm |

## Tuần 10

| Test | Người | Pass condition |
|---|---|---|
| Báo cáo | Cả nhóm | Không còn "..."/TODO |
| Demo thật | Cả nhóm | Video/ảnh rõ ràng |
| Bảo vệ thử | Cả nhóm | Trả lời được câu hỏi chéo |

---

# 15. BỘ TEST CASE CHÍNH

| ID | Test | Pass condition |
|---|---|---|
| T01 | Đọc cảm biến | Giá trị trong dải vật lý hợp lý |
| T02 | Payload JSON | Đúng 100% data contract |
| T03 | MQTT publish/subscribe | Message không thất thoát |
| T04 | Buffer offline | Gửi bù đúng thứ tự, không mất dữ liệu |
| T05 | Ghi InfluxDB | Record ghi đúng, đọc lại khớp |
| T06 | GET /api/readings | Trả đúng theo device_id/from/to/limit |
| T07 | GET /api/readings/latest | Cập nhật đúng theo thời gian thực |
| T08 | WebSocket /ws/live | Nhiều client nhận đồng thời |
| T09 | POST /api/forecasts | Tạo đúng forecast_run + forecast_points |
| T10 | GET /api/forecasts/latest | Trả đúng dự báo mới nhất |
| T11 | Sliding window | Shape X/y đúng công thức |
| T12 | Huấn luyện mô hình | Loss giảm dần, không NaN |
| T13 | Đánh giá mô hình | MAE/RMSE/MAPE tốt hơn baseline |
| T14 | predict.py | Chạy định kỳ không crash |
| T15 | Alert config | Đọc/ghi đúng theo device_id |
| T16 | Alert event | Tạo đúng khi vượt ngưỡng, không tạo khi trong ngưỡng |
| T17 | Dashboard hiển thị dữ liệu thật | Không còn mock, không lỗi khi rỗng |
| T18 | Dashboard hiển thị dự báo | Đồng bộ với dữ liệu backend |
| T19 | Chịu tải nhiều node | Không crash khi tải tăng x3–x5 |
| T20 | Regression toàn hệ thống | Tính năng cũ không bị hỏng bởi thay đổi mới |

---

# 16. CHECKLIST ĐÚNG/SAI TRƯỚC KHI MERGE

## 📡 Đạt

### Phải trả lời được
- [ ] Task này ảnh hưởng đến dữ liệu gửi đi như thế nào?
- [ ] Payload có còn đúng data contract không?
- [ ] Test nào chứng minh cảm biến đọc đúng?

### Không merge nếu
- [ ] Đổi field JSON mà chưa thông báo cả nhóm
- [ ] Chưa test thực tế trên board, chỉ test lý thuyết
- [ ] Không có cơ chế xử lý khi cảm biến trả về lỗi/NaN

## 🖥️ Bình

### Phải trả lời được
- [ ] Endpoint này input/output là gì, có khớp `schemas.py` không?
- [ ] Dữ liệu ghi vào DB nào (InfluxDB hay PostgreSQL), vì sao?
- [ ] Test nào xác nhận endpoint hoạt động đúng?

### Không merge nếu
- [ ] Chưa cập nhật `schemas.py` khi đổi cấu trúc dữ liệu
- [ ] API không xử lý trường hợp dữ liệu rỗng/lỗi
- [ ] Chưa test qua `/docs` hoặc Postman

## 🤖 Lợi

### Phải trả lời được
- [ ] Input/Output của hàm là gì, đơn vị nào?
- [ ] MAE/RMSE/MAPE hiện tại là bao nhiêu, có tốt hơn baseline không?
- [ ] Mô hình có bị overfit không (so sánh loss train/val)?

### Không merge nếu
- [ ] Chưa đánh giá trên tập test độc lập
- [ ] Hard-code đường dẫn dữ liệu cá nhân (không dùng biến môi trường)
- [ ] Không lưu lại được mô hình để dùng cho `predict.py`

## 🎨 Quyến

### Phải trả lời được
- [ ] Component này lấy dữ liệu từ API nào?
- [ ] Xử lý ra sao khi API lỗi/rỗng?
- [ ] Test case nào đã chạy qua cho tính năng này?

### Không merge nếu
- [ ] Chưa test trên màn hình nhỏ (mobile)
- [ ] Còn dữ liệu mock cứng trong code (khi đã có API thật)
- [ ] Gây lỗi console khi API trả về rỗng/lỗi

---

# 17. QUY TRÌNH COMMIT / REVIEW

## Đầu tuần

```text
pull develop
  ↓
checkout feature/<module>
  ↓
đọc lại data contract & API đã chốt
```

## Trong tuần

```text
code
  ↓
test/chạy thử
  ↓
commit nhỏ, rõ ràng
```

## Giữa tuần

```text
Đạt ↔ Bình review chéo (IoT–Backend)
Lợi ↔ Quyến review chéo (AI–Web)
```

## Cuối tuần

```text
chạy lại toàn bộ test liên quan
  ↓
tích hợp thử với module liền kề
  ↓
merge vào develop
  ↓
tag weekN-done
```

### Commit convention

```text
feat(iot): add mqtt publish with local buffer
feat(backend): add /api/readings endpoint
fix(ai): correct sliding window horizon calculation
test(web): add e2e checklist for alert banner
docs(iot): update wiring diagram
refactor(backend): move influx query into helper
```

---

# 18. KHÔNG MERGE KHI

- [ ] Code chưa chạy thử thực tế (chỉ đọc bằng mắt)
- [ ] Đổi data contract nhưng chưa cập nhật tài liệu & thông báo cả nhóm
- [ ] Chưa có test/kiểm tra tương ứng với task
- [ ] Hard-code thông tin cá nhân (Wi-Fi, IP, API key) vào code chung
- [ ] Có file trùng chức năng (duplicate) giữa các module
- [ ] Không giải thích được vì sao kết quả test là đúng

---

# 19. FINAL DEFINITION OF DONE

- [ ] Node cảm biến đo & gửi dữ liệu ổn định theo data contract
- [ ] Có cơ chế đệm/gửi bù khi mất kết nối
- [ ] MQTT broker + Backend nhận, xử lý, ghi DB ổn định
- [ ] REST API đầy đủ: readings, readings/latest, forecasts, alerts/config
- [ ] WebSocket đẩy dữ liệu realtime
- [ ] Mô hình AI huấn luyện xong, có đánh giá MAE/RMSE/MAPE rõ ràng, tốt hơn baseline
- [ ] `predict.py` chạy định kỳ, tự động cập nhật dự báo
- [ ] Dashboard hiển thị đầy đủ: dữ liệu thật, lịch sử, dự báo, cảnh báo
- [ ] Cấu hình ngưỡng cảnh báo hoạt động đúng
- [ ] Đã kiểm thử end-to-end, không còn bug Blocker
- [ ] Tài liệu đầy đủ: `README.md`, `iot/README.md`, `MODEL_CARD.md`, tài liệu API
- [ ] Báo cáo Word + Slide hoàn chỉnh, không còn placeholder
- [ ] Video/ảnh minh chứng hệ thống chạy thực tế
- [ ] Toàn bộ code merge vào `main`, gắn tag `release-candidate`

---

# 20. ROADMAP NGẮN GỌN

```text
TUẦN 1
Cả nhóm → Data contract + khung repo
        ↓
Môi trường mỗi người sẵn sàng

TUẦN 2
Đạt → Đọc cảm biến riêng lẻ
Bình → MQTT/DB chạy được
Lợi → Preprocess trên mock
Quyến → Layout + mock API
        ↓
Hạ tầng cơ bản chạy

TUẦN 3
Đạt → Publish MQTT hoàn chỉnh
Bình → GET /api/readings
Lợi → fetch_data + sliding window
Quyến → Biểu đồ lịch sử
        ↓
Module lõi hoàn chỉnh

TUẦN 4
Đạt → Node độc lập + buffer offline
Bình → readings/latest
Lợi → Dữ liệu thật đầu tiên
Quyến → Dashboard dữ liệu thật
        ↓
End-to-end cơ bản chạy

TUẦN 5
Đạt → Hiệu chuẩn cảm biến
Bình → WebSocket + khung forecasts
Lợi → LSTM v1 + đánh giá
Quyến → Realtime UI
        ↓
API đầy đủ + Model v1

TUẦN 6
Đạt → Node 2 (nếu có) + giám sát 48h
Bình → Forecast lưu DB
Lợi → predict.py tự động
Quyến → Hiển thị dự báo AI
        ↓
AI tích hợp vào hệ thống

TUẦN 7
Đạt → Kiểm tra trôi cảm biến
Bình → Alert config + alert event
Lợi → CNN-LSTM v2
Quyến → UI cảnh báo
        ↓
Tính năng cảnh báo hoàn chỉnh

TUẦN 8
Quyến chủ trì → Test E2E toàn hệ thống
Cả nhóm → Fix bug Blocker
        ↓
Hệ thống ổn định

TUẦN 9
Cả nhóm → Dọn code, hoàn thiện tài liệu, regression test
        ↓
Sẵn sàng viết báo cáo

TUẦN 10
Cả nhóm → Báo cáo + Slide + Demo + Tập dượt
        ↓
BẢO VỆ ĐỒ ÁN
```

---

# 21. SIGN-OFF HÀNG TUẦN

| Tuần | Đạt | Bình | Lợi | Quyến | Tích hợp | Tag |
|---|---|---|---|---|---|---|
| Tuần 1 | [ ] | [ ] | [ ] | [ ] | [ ] | `week1-done` |
| Tuần 2 | [ ] | [ ] | [ ] | [ ] | [ ] | `week2-done` |
| Tuần 3 | [ ] | [ ] | [ ] | [ ] | [ ] | `week3-done` |
| Tuần 4 | [ ] | [ ] | [ ] | [ ] | [ ] | `week4-done` |
| Tuần 5 | [ ] | [ ] | [ ] | [ ] | [ ] | `week5-done` |
| Tuần 6 | [ ] | [ ] | [ ] | [ ] | [ ] | `week6-done` |
| Tuần 7 | [ ] | [ ] | [ ] | [ ] | [ ] | `week7-done` |
| Tuần 8 | [ ] | [ ] | [ ] | [ ] | [ ] | `week8-done` |
| Tuần 9 | [ ] | [ ] | [ ] | [ ] | [ ] | `week9-done` |
| Tuần 10 | [ ] | [ ] | [ ] | [ ] | [ ] | `release-candidate` |

---

# END
