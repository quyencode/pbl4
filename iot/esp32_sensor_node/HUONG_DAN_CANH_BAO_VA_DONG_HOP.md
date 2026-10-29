# Node cảm biến: cảnh báo đèn + còi và đóng hộp

## 1. Linh kiện cần mua thêm

| Linh kiện | Số lượng | Ghi chú |
|---|---|---|
| LED 5 mm xanh, vàng, đỏ | 1 mỗi màu | Nên mua loại có đế gắn vỏ (đế LED 5 mm) cho đẹp |
| Điện trở 220 Ω | 3 | Cho 3 LED |
| Còi chủ động (active buzzer) 5V | 1 | Loại có 2 chân, cấp điện là kêu |
| Transistor NPN S8050 hoặc 2N2222 | 1 | Để ESP32 bật/tắt còi |
| Điện trở 1 kΩ | 1 | Nối vào chân B của transistor |
| Nút nhấn | 1 | Nút tắt tiếng, loại gắn vỏ (12 mm) |
| Hộp nhựa điện tử ABS khoảng 150×100×70 mm | 1 | Hoặc hộp lớn hơn nếu đế ESP32 dài |
| Board đục lỗ (PCB lỗ) hoặc breadboard mini 170 lỗ | 1 | Thay breadboard lớn |
| Dây đực–cái ngắn 10 cm, dây rút, keo nến, băng dính 2 mặt | | Gọn dây, cố định linh kiện |

## 2. Sơ đồ nối phần cảnh báo

| Linh kiện | Nối | Vào ESP32 |
|---|---|---|
| LED xanh | Chân dài (+) → điện trở 220 Ω | GPIO18; chân ngắn (−) vào GND |
| LED vàng | Chân dài (+) → điện trở 220 Ω | GPIO19; chân ngắn vào GND |
| LED đỏ | Chân dài (+) → điện trở 220 Ω | GPIO23; chân ngắn vào GND |
| Transistor S8050 (mặt phẳng hướng về mình: E – B – C) | B → điện trở 1 kΩ | GPIO27 |
| | E | GND |
| | C | Chân (−) của còi |
| Còi | Chân (+) (chân dài, có dấu +) | 5V / VIN |
| Nút nhấn | Một chân | GPIO13 |
| | Chân còn lại | GND |

Không nối còi thẳng vào GPIO: còi ăn dòng lớn hơn mức chân ESP32 chịu được.
Thứ tự chân của 2N2222 có thể khác S8050, xem lại sơ đồ in trên bao bì hoặc tra datasheet.

Các chân đang dùng, **không** dùng lại: GPIO16/17 (PMS5003), 4 (DHT11), 21/22 (LCD), 25/26 (để dành MH-Z19B).

## 3. Cách hoạt động (firmware mới)

| PM2.5 trung bình 2 phút | Đèn | Còi | LCD dòng 1 |
|---|---|---|---|
| ≤ 35.4 µg/m³ (Tốt, Trung bình) | Xanh | Im | `PM:24.0 TOT` |
| 35.5 – 55.4 (Kém) | Vàng | 1 tiếng khi vừa chuyển sang | `PM:40.0 KEM` |
| 55.5 – 125.4 (Xấu) | Đỏ | 3 tiếng khi vừa chuyển sang | `PM:70.0 XAU` |
| > 125.4 (Rất xấu trở lên) | Đỏ nháy | 3 tiếng, lặp lại mỗi 60 giây | `PM:130.0 RAT XAU` |
| Cảm biến lỗi / đang khởi động | Vàng nháy | Im | `PM:-- LOI` |

- Ngưỡng theo chuẩn US EPA 2024, giống bảng AQI của Backend và Dashboard.
- Dùng trung bình 2 phút và trễ 2 µg/m³ khi hạ mức, nên đèn không chớp qua lại quanh ngưỡng.
- **Nút tắt tiếng:** bấm 1 lần thì còi im 30 phút (LCD hiện `IM`), đèn vẫn chạy; bấm lần nữa để bật lại.
- **Ban đêm 22h–6h:** chỉ bật đèn, không kêu.
- **Khi khởi động:** sáng cả 3 đèn và kêu 1 tiếng để tự kiểm tra.
- Cảnh báo chạy ngay trên node nên **vẫn hoạt động khi mất Wi-Fi hoặc server tắt**. Firmware mới cũng không còn bị treo vài chục giây khi mất mạng.

**Lưu ý:** file firmware mới để trống tên và mật khẩu Wi-Fi (`YOUR_WIFI_SSID`). Đạt điền lại trước khi nạp, và kiểm tra lại IP broker.

## 4. Đóng hộp cho giống một thiết bị

**Bố trí trong hộp**
- **Mặt nắp:** khoét ô chữ nhật cho LCD; khoan 3 lỗ 5 mm cho 3 đèn, 1 lỗ cho còi, 1 lỗ cho nút tắt tiếng.
- **Thành hộp:** khoét đúng chỗ **cửa hút và cửa xả của PMS5003**, áp sát cảm biến vào thành hộp, không để bị che. Đây là lỗi hay gặp nhất khi đóng hộp: PMS5003 bị bít thì đo sai.
- **DHT11:** đặt sát lỗ thông gió ở thành hộp, xa ESP32 (ESP32 toả nhiệt làm nhiệt độ đo cao hơn thật). Tốt nhất khoan thêm vài lỗ thoáng quanh DHT11.
- **ESP32:** cố định đáy hộp bằng băng dính 2 mặt hoặc ốc; khoét lỗ cho cáp USB cấp nguồn.

**Đi dây**
- Bỏ breadboard lớn. Hàn lên board đục lỗ, hoặc dùng breadboard mini 170 lỗ dán đáy hộp.
- Dùng dây ngắn 10 cm, bó gọn bằng dây rút; GND và 5V đi chung một đường.
- Dán nhãn ngoài hộp, ví dụ "PBL4 · Node 01 · Giám sát không khí", và chú thích màu đèn cạnh 3 LED.

**Thứ tự làm**
1. Nối thử đèn, còi, nút trên breadboard; nạp firmware mới và kiểm tra (xem mục 5).
2. Đo, đánh dấu và khoét hộp.
3. Chuyển mạch vào hộp, đi dây gọn, cố định linh kiện.
4. Chạy lại toàn bộ: Serial báo publish thành công, Dashboard nhận số, đèn đúng màu.

## 5. Kiểm tra trước khi demo

1. **Khi cắm điện:** sáng cả 3 đèn và kêu 1 tiếng, sau đó đèn vàng nháy khoảng 30 giây trong lúc chờ cảm biến.
2. **Không khí bình thường:** đèn xanh, LCD hiện `TOT`.
3. **Thử cảnh báo:** đưa que nhang (hoặc thổi khói) lại gần cửa hút PMS5003. Sau khoảng 1–2 phút đèn chuyển vàng rồi đỏ và còi kêu; Serial in `Mức cảnh báo: XAU ...`; Dashboard cũng đổi màu AQI.
4. **Bấm nút:** LCD hiện `IM`, còi không kêu nữa.
5. **Tắt Wi-Fi:** đèn và còi vẫn chạy bình thường; bật lại Wi-Fi thì node tự kết nối lại và gửi bù dữ liệu.
6. **Chụp ảnh và quay video** node trong hộp lúc đèn đỏ và còi kêu, để đưa vào báo cáo.
