### Terminal 1 — Hạ tầng Docker
```
cd "C:\Users\Acer\OneDrive\文档\Github\pbl4"
docker compose up -d
docker ps
```
Kỳ vọng: 3 container `aqi_postgres`, `aqi_mosquitto`, `aqi_influxdb` đều **Running**.

### Terminal 2 — Backend (để chạy nền xuyên suốt)
```
cd "C:\Users\Acer\OneDrive\文档\Github\pbl4\backend"
py -3.12 -m pip install -r requirements.txt
py -3.12 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
Kiểm tra nhanh (terminal khác): `curl http://localhost:8000/health` → phải ra `{"status":"ok"...}`.

### Terminal 3 — Web Dashboard (để chạy nền xuyên suốt)
```
cd "C:\Users\Acer\OneDrive\文档\Github\pbl4\frontend"
npm install
npm run dev
```
Mở trình duyệt: `http://localhost:5173`

---

## Lúc trình bày — theo đúng thứ tự lên nói (kịch bản 15 phút)

### 0. Mở đầu — không có lệnh
Chỉ nói, có thể chiếu cây thư mục dự án (`README.md` mục "Cấu trúc thư mục") làm nền.

### 1. Khối IoT — Đạt
Không có lệnh PC, chỉ cắm node / mở Serial Monitor trên Arduino IDE.
Nếu không có node thật, tạo dữ liệu giả minh họa:
```
cd "C:\Users\Acer\OneDrive\文档\Github\pbl4\ai"
py -3.12 generate_mock_data.py
```

### 2. Khối Backend — Bình
Đã chạy sẵn ở Terminal 2. Demo bằng:
```
http://localhost:8000/docs
```
hoặc terminal khác:
```
mosquitto_sub -t "sensors/+/data" -v
```

### 3. Khối AI — Lợi
```
cd "C:\Users\Acer\OneDrive\文档\Github\pbl4"
py -3.12 -m pip install pandas numpy scikit-learn tensorflow requests
py -3.12 ai\predict.py --device_id node-01
```
⚠️ Chạy đúng từ thư mục gốc `pbl4` (không `cd ai`) — đường dẫn model trong code chỉ đúng khi chạy từ đây.
⚠️ `train_model.py` **bỏ qua, không chạy** — đang lỗi import (`prepare_dataset`/`FEATURE_COLUMNS` chưa định nghĩa trong `preprocess.py`), và model đã train sẵn rồi nên không cần train lại.

### 4. Khối Web Dashboard — Quyến
Đã chạy sẵn ở Terminal 3, chỉ cần mở `http://localhost:5173` trình bày.

Nếu muốn demo có số liệu trực quan (do Backend 2 API đọc dữ liệu lịch sử còn là TODO, mặc định sẽ trống):
1. Qua **Terminal 2**, bấm `Ctrl + C` để dừng Backend.
2. Quay lại trình duyệt, bấm `F5`.
3. Dashboard tự chuyển sang hiện dữ liệu mẫu (banner cam) — minh họa tính năng tự phát hiện mất kết nối Backend.
4. Xong phần demo, bật lại Backend (chạy lại lệnh `uvicorn` ở Terminal 2) cho phần Hỏi-đáp.

---

## Phụ: IoT có node thật

Lấy IP LAN máy bạn (để Đạt trỏ node vào, vì broker MQTT giờ chạy trên máy bạn):
```
ipconfig
```
→ tìm dòng "IPv4 Address", sửa vào biến `MQTT_BROKER` trong `iot/esp32_sensor_node/esp32_sensor_node.ino`, nạp lại firmware qua Arduino IDE.

---

## Lưu ý máy đã cài đặt (để không cài lại nếu dùng máy khác)
- Docker Desktop + WSL2 (bật sẵn)
- Python 3.12.10 cài qua `py -3.12` (máy có sẵn Python MSYS64 không dùng được, không cài `pip`)
- Node.js v24 / npm 11 (đã có sẵn)
- `ai/requirements.txt` bị lỗi encoding (UTF-16) — không dùng `pip install -r` cho file này, cài tay các gói như lệnh ở trên
