# Sơ đồ đấu nối — Node cảm biến ESP32 (Task A1.1)

> ⚠️ **Cập nhật:** PM2.5/PM10 (PMS5003) và CO2 (MH-Z19B) đã **bỏ khỏi phần cứng thật**
> do giới hạn ngân sách đề tài. Hai giá trị này giờ được **mô phỏng trong firmware**
> (xem `esp32_sensor_node.ino`, hàm `readPMS5003()` / `readMHZ19B()`) — không cần
> mua hay đấu nối 2 module này nữa. Chỉ còn **DHT11** là cảm biến thật cần lắp.
> Chi tiết lý do & giới hạn: xem `iot/mqtt_data_contract.md` và báo cáo, mục
> "Giới hạn đề tài".

## 1. Tổng quan kết nối

| Module | Chân nguồn | Chân dữ liệu | Nối vào ESP32 |
|---|---|---|---|
| DHT11 (nhiệt độ/độ ẩm) | VCC → 3.3V, GND → GND | DATA → GPIO4 | GPIO4 (kèm điện trở kéo lên 10kΩ) |

Chân này khớp đúng với đoạn code sau trong `esp32_sensor_node.ino`, **không cần sửa code** nếu đấu đúng bảng trên:

```cpp
#define DHTPIN 4
```

## 2. Chi tiết module

### DHT11 (nhiệt độ, độ ẩm)
- Chỉ có 1 chân dữ liệu (1-Wire), nối vào GPIO4
- **Bắt buộc thêm điện trở kéo lên (pull-up) 10kΩ** giữa chân DATA và chân VCC — nếu module bạn mua là dạng breakout board (3 chân, đã tích hợp sẵn điện trở) thì bỏ qua bước này
- Có thể cấp nguồn 3.3V hoặc 5V đều được, ưu tiên 3.3V để đồng bộ mức logic
- Độ chính xác thấp hơn DHT22: 0–50°C (±2°C), độ ẩm 20–90% (±5%), **giá trị số nguyên, không có phần thập phân** — biểu đồ dashboard sẽ có dạng bậc thang rõ hơn, không phải lỗi hiển thị

## 3. Nguồn điện chung

- ESP32 cấp nguồn qua cổng USB (5V) khi lập trình/test tại bàn
- Khi lắp thực tế ngoài trời (node độc lập, Tuần 4), dùng cục sạc điện thoại 5V/1A trở lên qua cáp USB — không còn PMS5003/MH-Z19B nên dòng tiêu thụ thấp hơn nhiều so với thiết kế ban đầu, nguồn yêu cầu nhẹ hơn
- GND của DHT11 phải nối chung với GND của ESP32

## 4. Việc cần làm tiếp (theo Task A1.1)

- [ ] Đối chiếu chân DHT11 ở trên với module thật đang có trong tay
- [ ] Chụp ảnh sơ đồ đấu nối thật sau khi cắm xong, lưu vào thư mục này
- [ ] Ghi chú lại nếu module thật có khác biệt (ví dụ chân đánh số khác, cần điện trở khác) ngay trong file này để Bình/Quyến không bị nhầm khi đọc lại
- [ ] Đọc kỹ ghi chú "PM2.5/PM10/CO2 là dữ liệu mô phỏng" trong `iot/mqtt_data_contract.md` trước khi viết báo cáo/bảo vệ, để không bị hiểu nhầm là số đo thật
