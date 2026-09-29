# Data Contract — Định dạng dữ liệu dùng chung

File này là "hợp đồng" giữa 4 khối (IoT / Backend / AI / Web). **Mọi thay đổi phải được
cả nhóm đồng ý trước khi sửa code**, vì cả 4 module đều phụ thuộc vào đúng định dạng này.

## 1. MQTT — Node cảm biến gửi lên Backend

- **Topic:** `sensors/<device_id>/data` — ví dụ: `sensors/node-01/data`
- **QoS đề xuất:** 1 (at-least-once)
- **Payload (JSON):**

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

| Trường | Kiểu | Đơn vị | Ghi chú |
|---|---|---|---|
| `device_id` | string | — | định danh duy nhất mỗi node, dạng `node-XX` |
| `pm25` | float | µg/m³ | bụi mịn PM2.5 — số đo thật (PMS5003) |
| `pm10` | float | µg/m³ | bụi mịn PM10 — số đo thật (PMS5003) |
| `co2` | int | ppm | nồng độ CO2 — **mô phỏng, xem ghi chú bên dưới** |
| `temperature` | float | °C | số đo thật (DHT11) |
| `humidity` | float | % | số đo thật (DHT11) |
| `timestamp` | string | ISO-8601 | giờ đo tại node (UTC hoặc giờ VN thống nhất trước) |

> ⚠️ **Ghi chú quan trọng (cập nhật Tuần 4):** `pm25`, `pm10` đọc từ cảm biến
> **PMS5003 thật** qua UART. PMS5003 đã đặt mua nhưng đang **về trễ** (~7-9 ngày kể từ
> đầu Tuần 4) — trong lúc chờ hàng, firmware **tự động fallback** sang dữ liệu mô
> phỏng cho `pm25`/`pm10` (không đứt luồng dữ liệu), rồi tự chuyển sang đọc thật ngay
> khi cảm biến được cắm, không cần sửa code hay data contract. `co2` vẫn luôn là
> **dữ liệu mô phỏng** (chưa mua MH-Z19B). `temperature`/`humidity` (DHT11) là số đo
> thật. Tên field, kiểu dữ liệu, đơn vị và toàn bộ format JSON **không đổi** —
> Backend/AI/Web không cần sửa code dù dữ liệu pm25/pm10 đang là thật hay tạm mô
> phỏng. Xem tác động với việc huấn luyện/đánh giá mô hình AI trong `ai/MODEL_CARD.md`.

Node nào chưa đọc được cảm biến nào thì gửi `null` cho trường đó — Backend cần chấp
nhận `null` và không được crash.

## 2. REST API — Backend cung cấp cho AI và Web Dashboard

Base URL mặc định: `http://localhost:8000`

### 2.1. `GET /api/readings`
Lấy dữ liệu lịch sử (dùng để huấn luyện AI và vẽ biểu đồ lịch sử).

Query params: `device_id`, `from` (ISO-8601), `to` (ISO-8601), `limit` (mặc định 1000)

Response:
```json
{
  "device_id": "node-01",
  "items": [
    {"timestamp": "2026-09-22T09:30:00", "pm25": 42.5, "pm10": 68.0, "co2": 620, "temperature": 29.4, "humidity": 71}
  ]
}
```

### 2.2. `GET /api/readings/latest`
Trả về bản ghi mới nhất của mọi node — dùng cho màn hình chính của Dashboard.

### 2.3. `POST /api/forecasts`
Khối AI gọi endpoint này sau mỗi lần chạy dự báo.

Request body:
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

### 2.4. `GET /api/forecasts/latest?device_id=`
Dashboard gọi để lấy dự báo mới nhất cho một node.

### 2.5. `GET/POST /api/alerts/config`
Cấu hình ngưỡng cảnh báo theo node/khu vực.
```json
{ "device_id": "node-01", "pm25_threshold": 55, "aqi_threshold": 100 }
```

### 2.6. `WS /ws/live`
WebSocket đẩy dữ liệu realtime; mỗi message có cùng cấu trúc với một item của
`/api/readings`, kèm `device_id`.

## 3. Quy ước chung

- Toàn bộ thời gian dùng định dạng **ISO-8601**, thống nhất một múi giờ cho cả hệ thống
  (khuyến nghị: lưu UTC trong DB, chuyển đổi hiển thị ở Frontend).
- Toàn bộ số đo dùng **float**, không làm tròn ở tầng truyền dữ liệu — làm tròn khi hiển thị.
- Chỉ số AQI được tính ở khối AI hoặc Backend (thống nhất trước ai tính) từ PM2.5 theo
  công thức AQI chuẩn (EPA breakpoints) — cần ghi rõ công thức dùng trong `ai/MODEL_CARD.md`.
