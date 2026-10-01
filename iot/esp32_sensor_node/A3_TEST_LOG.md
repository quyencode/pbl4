# Test Log - Task A3.2

## Thông tin chung

- **Người test:** Lê Quang Đạt
- **Ngày test:** 2026-10-01
- **Thiết bị:** ESP32 DevKit V1, device_id = node-01
- **Firmware:** esp32_sensor_node.ino (Task A3.1)
- **MQTT Broker:** 192.168.1.100:1883 (Mosquitto)
- **SEND_INTERVAL_MS:** 300000 (5 phút)

---

## Test 1: Reconnect MQTT khi mất mạng

### Kịch bản
1. Node đang chạy bình thường, publish thành công
2. Tắt WiFi router trong 2 phút
3. Bật lại WiFi router
4. Quan sát Serial Monitor

### Kết quả mong đợi
- Khi mất mạng: Serial hiện `>>> Mất kết nối MQTT - lưu vào buffer <<<`
- Khi có mạng lại: Serial hiện `Đã kết nối MQTT.` + `>>> Đã publish MQTT thành công <<<`

### Kết quả thực tế
- [ ] PASS
- [ ] FAIL

### Ghi chú
(ghi chú nếu có)

---

## Test 2: Gửi dữ liệu liên tục 30 phút

### Kịch bản
1. Reset ESP32, ghi lại thời điểm bắt đầu
2. Chạy liên tục 30 phút
3. Đếm số message ESP32 gửi (trên Serial Monitor)
4. Đếm số message Backend nhận (trên máy Bình dùng `mosquitto_sub`)
5. So sánh 2 con số

### Lệnh đếm trên máy Bình
```bash
mosquitto_sub -h 192.168.1.100 -t 'sensors/node-01/data' | wc -l