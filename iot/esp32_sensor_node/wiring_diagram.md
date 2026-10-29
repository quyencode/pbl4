# Sơ đồ đấu nối — Node cảm biến ESP32 (Task A1.1)

> ✅ **Cập nhật (Tuần 6):** PMS5003 đã về và đọc **số đo thật** (cắm qua đế chuyển 8 chân
> 1.25 mm → 2.54 mm). DHT11 là cảm biến thật. **CO2 (MH-Z19B) vẫn chưa lắp**, tiếp tục
> **mô phỏng trong firmware** (hàm `simulateCO2()`).
> Thêm phần **cảnh báo tại chỗ**: 3 đèn LED, còi, nút tắt tiếng (mục 4). Hướng dẫn mua
> linh kiện và đóng hộp: `HUONG_DAN_CANH_BAO_VA_DONG_HOP.md`, hình bố trí: `bo_tri_hop_node.png`.

## 1. Tổng quan kết nối

| Module | Chân nguồn | Chân dữ liệu | Nối vào ESP32 |
|---|---|---|---|
| DHT11 (nhiệt độ/độ ẩm) | VCC → 3.3V, GND → GND | DATA → GPIO4 | GPIO4 (kèm điện trở kéo lên 10kΩ) |
| PMS5003 (PM2.5/PM10) | VCC → 5V, GND → GND | TX → GPIO16 (RX2), RX → GPIO17 (TX2, không bắt buộc) | GPIO16/GPIO17 (UART1) |
| LCD 1602 I2C | VCC → 5V, GND → GND | SDA → GPIO21, SCL → GPIO22 | I2C, địa chỉ 0x27 (hoặc 0x3F) |
| LED xanh / vàng / đỏ | Chân ngắn (−) → GND | Chân dài (+) → điện trở 220 Ω → GPIO | GPIO18 / GPIO19 / GPIO23 |
| Còi chủ động 5V | (+) → 5V | (−) → cực C transistor S8050; E → GND; B → điện trở 1 kΩ → GPIO | GPIO27 (qua transistor) |
| Nút tắt tiếng | — | Một chân → GPIO, chân còn lại → GND | GPIO13 (INPUT_PULLUP) |
| MH-Z19B (CO2, chưa lắp) | VCC → 5V, GND → GND | TX → GPIO25, RX → GPIO26 | Để dành UART2 |

Chân này khớp đúng với đoạn code sau trong `esp32_sensor_node.ino`, **không cần sửa code** nếu đấu đúng bảng trên:

```cpp
#define DHTPIN      4
// PMS5003: PMSSerial.begin(9600, SERIAL_8N1, 16, 17)
// LCD:     Wire.begin(21, 22)
#define LED_GREEN   18
#define LED_YELLOW  19
#define LED_RED     23
#define BUZZER_PIN  27
#define BTN_MUTE    13
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

### Cảnh báo tại chỗ (đèn + còi + nút)
- **Không nối còi thẳng vào GPIO**: còi ăn khoảng 20–30 mA, quá mức chân ESP32 chịu được → bật/tắt qua transistor NPN S8050/2N2222.
- Thứ tự chân S8050 (mặt phẳng hướng về mình): **E – B – C**. 2N2222 có thể khác, xem lại bao bì/datasheet.
- Nút nhấn không cần điện trở ngoài: firmware bật điện trở kéo lên có sẵn (`INPUT_PULLUP`).
- Ngưỡng màu đèn và cách còi kêu: xem `HUONG_DAN_CANH_BAO_VA_DONG_HOP.md` mục 3.

## 3. Nguồn điện chung

- ESP32 cấp nguồn qua cổng USB (5V) khi lập trình/test tại bàn
- Khi lắp thực tế ngoài trời (node độc lập, Tuần 4), dùng cục sạc điện thoại 5V/1A trở lên qua cáp USB — PMS5003 tiêu thụ dòng đáng kể lúc quạt chạy, cần nguồn ổn định, không dùng cục sạc dòng yếu
- GND của DHT11 và PMS5003 phải nối chung với GND của ESP32

## 4. Việc cần làm tiếp

- [x] Đối chiếu chân DHT11 và PMS5003 với module thật, test đọc giá trị thật qua Serial Monitor
- [ ] Nối đèn, còi, nút theo bảng mục 1, nạp firmware mới và thử bằng que nhang
- [ ] Đóng hộp theo `bo_tri_hop_node.png` (cửa hút/xả PMS5003 trùng lỗ khoét, DHT11 xa ESP32)
- [ ] Chụp ảnh node đã đóng hộp (mặt nắp + bên trong), lưu vào thư mục này
- [ ] Đọc kỹ ghi chú "CO2 là dữ liệu mô phỏng" trong `iot/mqtt_data_contract.md` trước khi viết báo cáo/bảo vệ, để không bị hiểu nhầm là số đo thật
