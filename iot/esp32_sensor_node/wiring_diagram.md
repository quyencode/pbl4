# Sơ đồ đấu nối — Node cảm biến ESP32 (Task A1.1)

> ⚠️ Đây là sơ đồ tham khảo dựa theo cách đấu phổ biến nhất cho 3 module này và
> đúng khớp với chân đã khai báo sẵn trong `esp32_sensor_node.ino`. Trước khi
> hàn/cắm dây thật, **đối chiếu lại với datasheet in trên chính module bạn mua**
> — một số shop bán board chuyển đổi (breakout) có thể đánh số chân khác.

## 1. Tổng quan kết nối

| Module | Chân nguồn | Chân dữ liệu | Nối vào ESP32 |
|---|---|---|---|
| PMS5003 (PM2.5/PM10) | VCC → 5V, GND → GND | TX → RX2, RX → TX2 | GPIO16 (RX2), GPIO17 (TX2) |
| MH-Z19B (CO2) | VIN → 5V, GND → GND | TX → RX, RX → TX | GPIO25, GPIO26 |
| DHT22 (nhiệt độ/độ ẩm) | VCC → 3.3V, GND → GND | DATA → GPIO4 | GPIO4 (kèm điện trở kéo lên 10kΩ) |

Các chân này khớp đúng với đoạn code sau trong `esp32_sensor_node.ino`, **không cần sửa code** nếu đấu đúng bảng trên:

```cpp
#define DHTPIN 4
PMSSerial.begin(9600, SERIAL_8N1, 16, 17);   // RX=16, TX=17
CO2Serial.begin(9600, SERIAL_8N1, 25, 26);   // RX=25, TX=26
```

## 2. Chi tiết từng module

### PMS5003 (cảm biến bụi mịn PM2.5/PM10)
- Giao tiếp UART, mức logic 3.3V (an toàn cho ESP32, không cần chia áp)
- Cấp nguồn 5V riêng — **không dùng chân 3.3V của ESP32** để cấp cho PMS5003, dòng tiêu thụ lúc quạt hút chạy có thể vượt quá khả năng của chân 3.3V, dễ gây tụt áp/reset ESP32
- Đấu chéo TX-RX: chân **TX** của PMS5003 nối vào chân **RX2 (GPIO16)** của ESP32, chân **RX** của PMS5003 nối vào chân **TX2 (GPIO17)**

### MH-Z19B (cảm biến CO2)
- Giao tiếp UART, mức logic thường là 3.3V ở chân TX (kiểm tra lại thông số ghi trên module bạn mua, một số bản yêu cầu chia áp nếu ra 5V)
- Cấp nguồn 5V — module cần dòng ổn định khi làm nóng bộ cảm biến NDIR lúc mới khởi động (2-3 phút đầu số đo chưa chuẩn, là bình thường)
- Đấu chéo tương tự: TX của MH-Z19B → GPIO25 (RX), RX của MH-Z19B → GPIO26 (TX)

### DHT22 (nhiệt độ, độ ẩm)
- Chỉ có 1 chân dữ liệu (1-Wire), nối vào GPIO4
- **Bắt buộc thêm điện trở kéo lên (pull-up) 10kΩ** giữa chân DATA và chân VCC — nếu module bạn mua là dạng breakout board (3 chân, đã tích hợp sẵn điện trở) thì bỏ qua bước này
- Có thể cấp nguồn 3.3V hoặc 5V đều được, ưu tiên 3.3V để đồng bộ mức logic

## 3. Nguồn điện chung

- ESP32 cấp nguồn qua cổng USB (5V) khi lập trình/test tại bàn
- Khi lắp thực tế ngoài trời (node độc lập, Tuần 4), dùng cục sạc điện thoại 5V/2A trở lên qua cáp USB — dòng PMS5003 lúc quạt chạy có thể lên tới ~100mA, cộng dồn cả 3 module nên nguồn yếu dễ gây treo/reset ESP32 liên tục
- Tất cả GND của 3 module **phải nối chung** với GND của ESP32 (GND chung — rất hay bị quên, gây lỗi đọc sai số ngẫu nhiên nếu thiếu)

## 4. Việc cần làm tiếp (theo Task A1.1)

- [ ] Đối chiếu bảng chân ở trên với module thật đang có trong tay
- [ ] Chụp ảnh sơ đồ đấu nối thật sau khi cắm xong, lưu vào thư mục này
- [ ] Ghi chú lại nếu module thật có khác biệt (ví dụ chân đánh số khác, cần điện trở khác) ngay trong file này để Bình/Quyến không bị nhầm khi đọc lại
