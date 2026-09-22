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
| `pm25` | float | µg/m³ | bụi mịn PM2.5 |
| `pm10` | float | µg/m³ | bụi mịn PM10 |
| `co2` | int | ppm | nồng độ CO2 |
| `temperature` | float | °C | |
| `humidity` | float | % | |
| `timestamp` | string | ISO-8601 | giờ đo tại node (UTC hoặc giờ VN thống nhất trước) |

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
