# Sơ đồ đấu nối — Node cảm biến ESP32 (Task A1.1)

> ⚠️ **Cập nhật (Tuần 2):** đã mua lại **PMS5003** (PM2.5/PM10), dự kiến về trong
> khoảng 8 ngày — cần đấu nối và test lại theo bảng bên dưới khi hàng về.
> **CO2 (MH-Z19B) vẫn chưa mua**, tiếp tục **mô phỏng trong firmware** (xem
> `esp32_sensor_node.ino`, hàm `readMHZ19B()`). DHT11 vẫn là cảm biến thật đã lắp.
> Chi tiết: xem `iot/mqtt_data_contract.md`.

## 1. Tổng quan kết nối

| Module | Chân nguồn | Chân dữ liệu | Nối vào ESP32 |
|---|---|---|---|
| DHT11 (nhiệt độ/độ ẩm) | VCC → 3.3V, GND → GND | DATA → GPIO4 | GPIO4 (kèm điện trở kéo lên 10kΩ) |
| PMS5003 (PM2.5/PM10) | VCC → 5V, GND → GND | TX → GPIO16 (RX2), RX → GPIO17 (TX2, không bắt buộc) | GPIO16/GPIO17 (UART1) |

Chân này khớp đúng với đoạn code sau trong `esp32_sensor_node.ino`, **không cần sửa code** nếu đấu đúng bảng trên:

```cpp
#define DHTPIN 4
#define PMS_RX_PIN 16
#define PMS_TX_PIN 17
```

## 2. Chi tiết module

### DHT11 (nhiệt độ, độ ẩm)
- Chỉ có 1 chân dữ liệu (1-Wire), nối vào GPIO4
- **Bắt buộc thêm điện trở kéo lên (pull-up) 10kΩ** giữa chân DATA và chân VCC — nếu module bạn mua là dạng breakout board (3 chân, đã tích hợp sẵn điện trở) thì bỏ qua bước này
- Có thể cấp nguồn 3.3V hoặc 5V đều được, ưu tiên 3.3V để đồng bộ mức logic
- Độ chính xác thấp hơn DHT22: 0–50°C (±2°C), độ ẩm 20–90% (±5%), **giá trị số nguyên, không có phần thập phân** — biểu đồ dashboard sẽ có dạng bậc thang rõ hơn, không phải lỗi hiển thị

### PMS5003 (PM2.5, PM10)
- Giao tiếp UART, 9600 baud — nối chân **TX của module** vào **GPIO16 (RX2)** của ESP32
- Chân RX của module (nếu dùng) nối vào **GPIO17 (TX2)** — chỉ cần thiết nếu điều khiển chế độ chủ động/thụ động, đọc thụ động thông thường có thể bỏ qua
- Cấp nguồn **5V** (module tiêu thụ dòng cao hơn khi quạt hút bật, ~100mA trung bình, đỉnh ~200mA lúc khởi động quạt)
- **Cần ~30 giây làm nóng** sau khi cấp nguồn để số liệu ổn định — không đọc giá trị ngay khi vừa bật
- GND module nối chung GND với ESP32

## 3. Nguồn điện chung

- ESP32 cấp nguồn qua cổng USB (5V) khi lập trình/test tại bàn
- Khi lắp thực tế ngoài trời (node độc lập, Tuần 4), dùng cục sạc điện thoại 5V/1A trở lên qua cáp USB — PMS5003 tiêu thụ dòng đáng kể lúc quạt chạy, cần nguồn ổn định, không dùng cục sạc dòng yếu
- GND của DHT11 và PMS5003 phải nối chung với GND của ESP32

## 4. Việc cần làm tiếp (theo Task A1.1)

- [ ] Đối chiếu chân DHT11 và PMS5003 ở trên với module thật đang có trong tay (PMS5003 dự kiến về sau ~8 ngày)
- [ ] Chụp ảnh sơ đồ đấu nối thật sau khi cắm xong, lưu vào thư mục này
- [ ] Ghi chú lại nếu module thật có khác biệt (ví dụ chân đánh số khác, cần điện trở khác) ngay trong file này để Bình/Quyến không bị nhầm khi đọc lại
- [ ] Sau khi đấu PMS5003, test đọc giá trị thật qua Serial Monitor, đối chiếu với dải hợp lý ngoài trời (PM2.5 thường 10–100 µg/m³ ở đô thị VN)
- [ ] Đọc kỹ ghi chú "CO2 là dữ liệu mô phỏng" trong `iot/mqtt_data_contract.md` trước khi viết báo cáo/bảo vệ, để không bị hiểu nhầm là số đo thật
