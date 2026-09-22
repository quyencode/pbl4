# PBL4 — Giám sát và Dự báo Chất lượng Không khí Thông minh

Bộ khung khởi tạo (starter kit) cho dự án PBL4, gồm 4 phần tương ứng 4 thành viên
trong nhóm. Xem phân công chi tiết tại `PHAN_CONG_CONG_VIEC.md` (đi kèm ngoài repo
này) và hợp đồng dữ liệu tại `iot/mqtt_data_contract.md`.

```
project/
├── docker-compose.yml       # Mosquitto (MQTT) + InfluxDB + PostgreSQL
├── .env.example              # mẫu biến môi trường - copy thành .env
├── iot/
│   ├── mqtt_data_contract.md      # đặc tả định dạng dữ liệu dùng chung
│   └── esp32_sensor_node/
│       └── esp32_sensor_node.ino  # firmware mẫu cho ESP32
├── backend/
│   ├── requirements.txt
│   └── app/
│       ├── main.py            # FastAPI - REST API + WebSocket
│       ├── mqtt_subscriber.py # nhận dữ liệu MQTT, ghi InfluxDB
│       └── schemas.py         # Pydantic models
├── ai/
│   ├── requirements.txt
│   ├── fetch_data.py     # lấy dữ liệu lịch sử từ backend
│   ├── preprocess.py     # làm sạch, chuẩn hoá, sliding window
│   ├── train_model.py    # huấn luyện LSTM / CNN-LSTM
│   ├── predict.py        # suy luận + gửi dự báo về backend
│   └── MODEL_CARD.md     # template mô tả mô hình
├── database/
│   └── init_postgres.sql # schema PostgreSQL
└── frontend/              # Web Dashboard (React + Vite + Recharts)
    ├── package.json
    ├── index.html
    └── src/
```

## 1. Chạy hạ tầng nền (MQTT, InfluxDB, PostgreSQL)

Yêu cầu: Docker + Docker Compose đã cài.

```bash
cp .env.example .env      # chỉnh giá trị nếu cần
docker compose up -d
```

- MQTT broker: `localhost:1883`
- InfluxDB UI: `http://localhost:8086`
- PostgreSQL: `localhost:5432` (schema tự khởi tạo từ `database/init_postgres.sql`)

## 2. Chạy Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export $(cat ../.env | xargs)   # nạp biến môi trường (Linux/Mac); Windows dùng cách khác
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Kiểm tra: mở `http://localhost:8000/docs` để xem tài liệu API tự sinh.

## 3. Nạp firmware cho ESP32 (khối IoT)

1. Mở `iot/esp32_sensor_node/esp32_sensor_node.ino` bằng Arduino IDE hoặc PlatformIO.
2. Cài các thư viện: `PubSubClient`, `ArduinoJson`, `DHT sensor library`.
3. Chỉnh `WIFI_SSID`, `WIFI_PASSWORD`, `MQTT_BROKER` (IP máy chạy Docker), `DEVICE_ID`.
4. Hoàn thiện hàm `readPMS5003()` và `readMHZ19B()` theo datasheet cảm biến thật.
5. Nạp code và mở Serial Monitor để kiểm tra log.

## 4. Huấn luyện & chạy mô hình AI

```bash
cd ai
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python fetch_data.py --device_id node-01 --out data/node-01.csv
python train_model.py --data data/node-01.csv --model_type lstm

python predict.py --device_id node-01   # gửi dự báo về backend
```

## 5. Chạy Web Dashboard

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Mở `http://localhost:5173`.

## 6. Kiểm thử nhanh không cần phần cứng thật

Có thể giả lập một node gửi dữ liệu MQTT để test Backend/AI/Dashboard trước khi
phần cứng IoT sẵn sàng:

```bash
pip install paho-mqtt
python - <<'PY'
import json, time, paho.mqtt.publish as publish
payload = {
    "device_id": "node-01", "pm25": 42.5, "pm10": 68.0, "co2": 620,
    "temperature": 29.4, "humidity": 71,
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
}
publish.single("sensors/node-01/data", json.dumps(payload), hostname="localhost")
print("Đã gửi gói tin giả lập.")
PY
```

## Ghi chú

Đây là **bộ khung khởi tạo**, không phải hệ thống hoàn chỉnh — các phần đánh dấu
`TODO` trong code cần được từng thành viên hoàn thiện theo phân công tại
`PHAN_CONG_CONG_VIEC.md`.
