# PBL4 — Giám sát và Dự báo Chất lượng Không khí Thông minh
## Kế hoạch thực hiện & Phân công công việc nhóm

| | |
|---|---|
| **Tên đề tài** | Giám sát và Dự báo Chất lượng Không khí Thông minh ứng dụng IoT & AI |
| **Học phần** | PBL4 — IoT & Trí tuệ nhân tạo |
| **GVHD** | Huỳnh Hữu Hưng |
| **Số thành viên** | 4 |
| **Ngày lập kế hoạch** | 22/09/2026 |

---

## 1. Tổng quan dự án

Hệ thống gồm 5 khối chức năng nối tiếp nhau theo một pipeline khép kín:

```
Cảm biến (PM2.5, PM10, CO2, nhiệt độ, độ ẩm)
      │
      ▼
Vi điều khiển ESP32 (đọc, đóng gói dữ liệu)
      │  MQTT / HTTP
      ▼
Backend (MQTT Broker → xử lý → ghi DB)
      │  REST API
      ▼
Mô hình AI (LSTM / CNN-LSTM dự báo AQI/PM2.5 1–24h tới)
      │  REST / WebSocket
      ▼
Web Dashboard (hiển thị realtime, lịch sử, cảnh báo)
```

Bốn thành viên phụ trách bốn khối chính, ghép nối với nhau qua các **hợp đồng dữ liệu** (data contract) đã thống nhất trước — xem mục 5.

---

## 2. Thành viên & vai trò

| # | Họ tên | Vai trò | Khối phụ trách |
|---|---|---|---|
| 1 | **Lê Quang Đạt** | IoT / Cảm biến & Thu thập dữ liệu | Phần cứng, firmware ESP32, thu thập & gửi dữ liệu |
| 2 | **Bùi An Bình** | Mạng máy tính / Backend & Database | MQTT Broker, Backend service, Database, REST API |
| 3 | **Ngô Trí Lợi** | AI / Dự báo chất lượng không khí | Tiền xử lý dữ liệu, huấn luyện & đánh giá mô hình AI |
| 4 | **Nguyễn Anh Quyến** | Web Dashboard / Tích hợp hệ thống & QA | Frontend dashboard, tích hợp toàn hệ thống, kiểm thử |

> Nguyên tắc phân công: mỗi người làm chủ **một khối kỹ thuật** từ đầu đến cuối (thiết kế → code → test), đồng thời có trách nhiệm chéo ở phần tích hợp (mục 6) để tránh tình trạng "mạnh ai nấy làm, ghép không khớp".

---

## 3. Phân công chi tiết theo từng thành viên

### 3.1. Lê Quang Đạt — IoT / Cảm biến & Thu thập dữ liệu

**Mục tiêu:** node cảm biến đọc đúng số liệu, đóng gói và gửi dữ liệu ổn định về server.

| Việc cần làm | Deliverable | Công cụ/công nghệ |
|---|---|---|
| Nghiên cứu datasheet & đấu nối cảm biến PMS5003 (PM2.5/PM10), MH-Z19B (CO2), DHT11/SHT31 (nhiệt độ, độ ẩm) với ESP32 | Sơ đồ đấu nối (wiring diagram) | ESP32, UART/I2C |
| Viết firmware đọc dữ liệu cảm biến theo chu kỳ cố định (30–60s) | `esp32_sensor_node.ino` | Arduino IDE / PlatformIO |
| Đóng gói dữ liệu thành JSON theo đúng data contract (mục 5.1) và publish qua MQTT | Code publish MQTT (topic `sensors/node-XX/data`) | PubSubClient / MQTT.js |
| Cài cơ chế đệm cục bộ (local buffer) khi mất kết nối, gửi bù khi mạng phục hồi | Module buffer trong firmware | Vòng đệm SPIFFS/RAM |
| Gắn `device_id` để định danh từng node | Cấu hình thiết bị | — |
| Hiệu chuẩn cảm biến, đối chiếu với số liệu tham chiếu (nếu có) | Bảng ghi log hiệu chuẩn | — |
| Lắp đặt thử nghiệm 1–3 node tại vị trí thực tế | Ảnh/video lắp đặt + log dữ liệu thực tế | — |
| Viết tài liệu hướng dẫn nạp firmware & thay pin/bảo trì node | `iot/README.md` | Markdown |

**Kỹ năng cần có:** lập trình C/C++ nhúng, giao tiếp UART/I2C, MQTT publish, đọc datasheet cảm biến.

---

### 3.2. Bùi An Bình — Mạng máy tính / Backend & Database

**Mục tiêu:** tiếp nhận dữ liệu ổn định, lưu trữ đúng cấu trúc, cung cấp API chuẩn cho AI và Dashboard.

| Việc cần làm | Deliverable | Công cụ/công nghệ |
|---|---|---|
| Dựng MQTT Broker (Mosquitto), cấu hình topic, auth cơ bản | `docker-compose.yml` (service mosquitto) | Eclipse Mosquitto |
| Viết service subscribe MQTT, validate dữ liệu, ghi vào DB | `backend/app/mqtt_subscriber.py` | Python (paho-mqtt) |
| Thiết kế schema InfluxDB (time-series: đo lường theo thời gian) | Bucket/measurement design | InfluxDB |
| Thiết kế schema PostgreSQL (quan hệ: node, người dùng, ngưỡng cảnh báo) | `database/init_postgres.sql` | PostgreSQL |
| Xây REST API cung cấp dữ liệu chuẩn hoá cho AI & Dashboard | `backend/app/main.py` (FastAPI) | FastAPI |
| Endpoint lấy dữ liệu lịch sử theo node/khoảng thời gian (phục vụ huấn luyện AI) | `GET /api/readings` | FastAPI + InfluxDB client |
| Endpoint nhận kết quả dự báo từ khối AI và lưu lại | `POST /api/forecasts` | FastAPI |
| WebSocket đẩy dữ liệu realtime cho Dashboard | `backend/app/ws.py` | FastAPI WebSocket |
| Cơ chế log & giám sát phát hiện node mất kết nối | Log/alert cơ bản | logging module |
| Thiết kế hướng mở rộng nhiều node, nhiều người dùng đồng thời | Ghi chú kiến trúc trong tài liệu | — |
| Viết tài liệu API (OpenAPI/Swagger tự sinh từ FastAPI) | `/docs` endpoint | FastAPI |

**Kỹ năng cần có:** thiết kế CSDL, lập trình backend Python, MQTT, REST API, Docker.

---

### 3.3. Ngô Trí Lợi — AI / Dự báo chất lượng không khí

**Mục tiêu:** mô hình dự báo AQI/PM2.5 trong 1–24 giờ tới với sai số chấp nhận được.

| Việc cần làm | Deliverable | Công cụ/công nghệ |
|---|---|---|
| Thu thập dữ liệu lịch sử qua REST API của backend | `ai/fetch_data.py` | requests / pandas |
| Tiền xử lý: làm sạch, chuẩn hoá, xử lý thiếu dữ liệu, tạo sliding window | `ai/preprocess.py` | pandas, NumPy, scikit-learn |
| Kết hợp yếu tố khí tượng (nhiệt độ, độ ẩm) làm đặc trưng đầu vào | Feature engineering trong pipeline | pandas |
| Chia tập Train/Validation/Test theo tỉ lệ ~70/15/15 | Script chia tập | scikit-learn |
| Xây dựng & huấn luyện mô hình chuỗi thời gian (LSTM / CNN-LSTM) | `ai/train_model.py` | TensorFlow/Keras |
| Đánh giá mô hình bằng MAE, RMSE, MAPE; so sánh với baseline (Persistence) | Báo cáo/biểu đồ so sánh | matplotlib |
| Đóng gói mô hình đã huấn luyện để suy luận (inference) | `ai/model/` (file .h5/.keras) | TensorFlow |
| Viết service suy luận, gọi định kỳ, gửi kết quả dự báo về backend (`POST /api/forecasts`) | `ai/predict.py` | requests |
| Tài liệu mô tả kiến trúc mô hình, siêu tham số, kết quả đánh giá | `ai/MODEL_CARD.md` | Markdown |

**Kỹ năng cần có:** Python, xử lý dữ liệu chuỗi thời gian, deep learning (LSTM/CNN), đánh giá mô hình.

---

### 3.4. Nguyễn Anh Quyến — Web Dashboard / Tích hợp hệ thống & QA

**Mục tiêu:** giao diện trực quan, dễ dùng; toàn hệ thống chạy thông suốt từ cảm biến đến cảnh báo; chất lượng được kiểm chứng.

| Việc cần làm | Deliverable | Công cụ/công nghệ |
|---|---|---|
| Thiết kế giao diện: AQI hiện tại, PM2.5, trạng thái, xu hướng 7 ngày | Wireframe / mockup | Figma (tuỳ chọn) |
| Xây dựng Web Dashboard hiển thị dữ liệu realtime & lịch sử theo từng node | `frontend/` (React/Vue) | React hoặc Vue.js |
| Biểu đồ xu hướng AQI, biểu đồ so sánh thực tế vs dự báo | Component biểu đồ | Chart.js / Recharts |
| Kết nối WebSocket nhận dữ liệu realtime từ backend | Module socket client | WebSocket API |
| Cấu hình ngưỡng cảnh báo theo khu vực & hiển thị thông báo khi vượt ngưỡng | Tính năng cảnh báo | — |
| Giao diện responsive (máy tính & di động) | CSS responsive | Tailwind/CSS |
| **Tích hợp toàn hệ thống:** đảm bảo IoT → Backend → AI → Dashboard chạy end-to-end | Biên bản kiểm tra tích hợp | — |
| Viết test case & thực hiện kiểm thử (unit test backend, test API, test giao diện) | `tests/` + báo cáo QA | pytest, Postman/curl |
| Theo dõi lỗi, tổng hợp issue giữa các thành viên | Bảng theo dõi lỗi (issue tracker) | GitHub Issues |
| Tổng hợp tài liệu, hỗ trợ chuẩn bị báo cáo & slide bảo vệ | Bản nháp báo cáo cuối kỳ | Word/PowerPoint |

**Kỹ năng cần có:** lập trình frontend (React/Vue), WebSocket, kiểm thử phần mềm, kỹ năng tổng hợp/quản lý.

---

## 4. Timeline thực hiện (dự kiến 10 tuần — điều chỉnh theo lịch học phần thực tế)

| Tuần | Nội dung chính | Đạt/Bình | Đạt (IoT) | Lợi (AI) | Quyến (Web/QA) |
|---|---|---|---|---|---|
| 1 | Họp nhóm, phân công, chốt đề cương, thiết kế kiến trúc & data contract | Thiết kế schema DB | Chọn linh kiện, đọc datasheet | Khảo sát nguồn dữ liệu AQI mở (tham khảo) | Vẽ wireframe dashboard |
| 2 | Dựng hạ tầng cơ bản | Dựng MQTT broker, Docker | Đấu nối phần cứng, test đọc cảm biến | Chuẩn bị pipeline tiền xử lý mẫu | Khởi tạo project frontend |
| 3 | Phát triển module lõi | Backend nhận & lưu dữ liệu (mock) | Firmware publish MQTT hoàn chỉnh | Viết script fetch + preprocess | Dựng layout + kết nối API mock |
| 4 | Kết nối thật lần 1 | Test nhận dữ liệu thật từ node | Gửi dữ liệu thật liên tục | Thu thập dữ liệu thật ban đầu | Hiển thị dữ liệu thật cơ bản |
| 5 | Hoàn thiện API | REST API đầy đủ + WebSocket | Thêm buffer offline, hiệu chuẩn | Huấn luyện mô hình bản v1 | Biểu đồ realtime + lịch sử |
| 6 | Tích hợp AI | Endpoint nhận forecast | Lắp thêm node (nếu có) | Đánh giá MAE/RMSE, tinh chỉnh | Hiển thị dự báo trên dashboard |
| 7 | Tính năng cảnh báo | Cơ chế cảnh báo ngưỡng | Giám sát ổn định node ngoài trời | Tối ưu mô hình v2 | Cấu hình ngưỡng, thông báo |
| 8 | **Kiểm thử tích hợp toàn hệ thống (Quyến chủ trì)** | Fix lỗi backend | Fix lỗi phần cứng phát sinh | Fix lỗi pipeline dữ liệu | Test end-to-end, ghi nhận lỗi |
| 9 | Hoàn thiện & tối ưu | Tối ưu hiệu năng, log | Hoàn thiện tài liệu firmware | Hoàn thiện Model Card | Responsive, UI polish |
| 10 | Viết báo cáo, chuẩn bị bảo vệ | Đóng góp phần Backend | Đóng góp phần IoT | Đóng góp phần AI | Tổng hợp báo cáo & slide |

> Bảng này là khung tham khảo — điều chỉnh số tuần theo lịch trình PBL4 thực tế của lớp.

---

## 5. Hợp đồng dữ liệu & giao diện tích hợp (Data Contract)

Đây là phần **quan trọng nhất để 4 khối ghép được với nhau** — cả nhóm cần thống nhất và không tự ý đổi khi đã chốt.

### 5.1. Gói tin MQTT (IoT → Backend)

- Topic: `sensors/node-<id>/data`
- Payload JSON:
```json
{
  "device_id": "node-01",
  "pm25": 42.5,
  "pm10": 68.0,
  "co2": 620,
  "temperature": 29.4,
  "humidity": 71,
  "timestamp": "2026-09-22T09:30:00"
}
```

### 5.2. REST API (Backend ↔ AI, Backend ↔ Dashboard)

| Endpoint | Method | Mục đích | Dùng bởi |
|---|---|---|---|
| `/api/readings?device_id=&from=&to=` | GET | Lấy dữ liệu lịch sử | Khối AI (huấn luyện), Dashboard (biểu đồ) |
| `/api/readings/latest` | GET | Lấy dữ liệu mới nhất mọi node | Dashboard |
| `/api/forecasts` | POST | Ghi kết quả dự báo mới | Khối AI |
| `/api/forecasts/latest?device_id=` | GET | Lấy dự báo mới nhất | Dashboard |
| `/api/alerts/config` | GET/POST | Cấu hình ngưỡng cảnh báo | Dashboard |
| `/ws/live` | WebSocket | Đẩy dữ liệu realtime | Dashboard |

### 5.3. Định dạng kết quả dự báo (AI → Backend)

```json
{
  "device_id": "node-01",
  "generated_at": "2026-09-22T10:00:00",
  "horizon_hours": 24,
  "predictions": [
    {"timestamp": "2026-09-22T11:00:00", "aqi": 58.2, "pm25": 39.1},
    {"timestamp": "2026-09-22T12:00:00", "aqi": 61.0, "pm25": 41.3}
  ]
}
```

> File JSON schema đầy đủ đặt tại `iot/mqtt_data_contract.md` trong bộ file khởi tạo dự án — mọi thay đổi định dạng phải được cả 4 người đồng ý trước khi sửa code.

---

## 6. Ma trận phụ thuộc công việc

| Ai chờ ai | Cần gì | Từ ai | Rủi ro nếu trễ |
|---|---|---|---|
| Bình (Backend) | Gói tin MQTT thật để test | Đạt (IoT) | Có thể dùng script giả lập MQTT để không bị chặn tiến độ |
| Lợi (AI) | Dữ liệu lịch sử qua REST API | Bình (Backend) | Backend cần ưu tiên xong API `/api/readings` trước tuần 4 |
| Quyến (Web) | REST API + WebSocket hoạt động | Bình (Backend) | Có thể dùng mock data trước, tích hợp thật sau |
| Quyến (Web) | Endpoint `/api/forecasts/latest` | Lợi (AI) + Bình (Backend) | Dashboard hiển thị "đang cập nhật" nếu chưa có |

**Khuyến nghị:** mỗi người có thể phát triển độc lập bằng **dữ liệu giả lập (mock data)** đúng theo data contract ở mục 5, không cần chờ module khác xong hẳn mới bắt đầu.

---

## 7. Quy trình làm việc nhóm

- **Quản lý mã nguồn:** dùng chung 1 repository Git, mỗi thành viên làm việc trên nhánh riêng (`feature/iot`, `feature/backend`, `feature/ai`, `feature/web`), merge vào `main` qua Pull Request, có ít nhất 1 người khác review trước khi merge.
- **Họp nhóm:** họp ngắn định kỳ hằng tuần (đề xuất 30–45 phút) để báo cáo tiến độ, nêu vướng mắc; họp riêng khi có vấn đề tích hợp giữa hai module.
- **Theo dõi công việc:** dùng bảng Kanban (GitHub Projects/Trello) với các cột `Cần làm / Đang làm / Chờ review / Hoàn thành`.
- **Tài liệu dùng chung:** mọi thay đổi về data contract (mục 5) phải cập nhật vào file chung và thông báo cho cả nhóm.
- **Đặt tên nhánh & commit:** commit message ngắn gọn, mô tả rõ thay đổi (ví dụ: `feat(backend): add /api/readings endpoint`).

---

## 8. Checklist nghiệm thu (Definition of Done) theo từng khối

**IoT (Đạt):**
- [ ] Node đọc đúng cả 5 thông số (PM2.5, PM10, CO2, nhiệt độ, độ ẩm)
- [ ] Gửi dữ liệu qua MQTT đúng định dạng JSON đã thống nhất
- [ ] Có cơ chế đệm khi mất mạng, gửi bù khi có mạng lại
- [ ] Chạy ổn định liên tục tối thiểu 48 giờ không cần can thiệp thủ công

**Backend (Bình):**
- [ ] MQTT broker nhận dữ liệu từ nhiều node đồng thời
- [ ] Dữ liệu được ghi đúng, đầy đủ vào database
- [ ] REST API trả đúng dữ liệu theo data contract, có tài liệu API
- [ ] WebSocket đẩy dữ liệu realtime ổn định

**AI (Lợi):**
- [ ] Pipeline tiền xử lý chạy được từ dữ liệu thô
- [ ] Mô hình huấn luyện xong, có kết quả MAE/RMSE/MAPE ghi lại
- [ ] Mô hình cho kết quả tốt hơn baseline (Persistence)
- [ ] Service dự báo tự động gửi kết quả về backend theo chu kỳ

**Web Dashboard & QA (Quyến):**
- [ ] Hiển thị đúng dữ liệu realtime & lịch sử
- [ ] Hiển thị dự báo AI, so sánh với thực tế
- [ ] Cảnh báo hoạt động đúng khi vượt ngưỡng
- [ ] Đã kiểm thử end-to-end toàn hệ thống, không lỗi chặn (blocker)
- [ ] Giao diện responsive trên di động

---

## 9. Rủi ro & phương án dự phòng

| Rủi ro | Ảnh hưởng | Phương án dự phòng |
|---|---|---|
| Cảm biến sai số trôi theo thời gian | Dữ liệu AI huấn luyện kém chính xác | Hiệu chuẩn định kỳ, đối chiếu nguồn tham chiếu |
| Mất kết nối mạng tại nơi lắp node | Thiếu dữ liệu | Đệm cục bộ + gửi bù (đã đưa vào checklist IoT) |
| Dữ liệu lịch sử chưa đủ dài để huấn luyện AI tốt | Mô hình dự báo kém | Bổ sung dữ liệu khí tượng mở, thu thập sớm ngay từ tuần 2 |
| Một thành viên bị chậm tiến độ | Chặn tiến độ người khác | Dùng mock data theo data contract để các phần không phụ thuộc cứng vào nhau |
| Tích hợp cuối kỳ phát sinh nhiều lỗi | Không kịp deadline | Dành hẳn tuần 8 cho tích hợp & test, không dồn vào phút chót |

---

## 10. Tài liệu & sản phẩm bàn giao cuối kỳ

- [ ] Mã nguồn đầy đủ 4 khối (IoT firmware, Backend, AI, Web Dashboard)
- [ ] File báo cáo dự án dạng Word (phân tích chi tiết — xem file đi kèm)
- [ ] Slide thuyết trình (đã có: `pbl4.pptx`)
- [ ] Video/ảnh minh chứng hệ thống chạy thực tế
- [ ] Model Card mô tả mô hình AI đã huấn luyện
- [ ] Tài liệu API (Swagger/OpenAPI)
- [ ] File hướng dẫn cài đặt & chạy hệ thống (`README.md`)
