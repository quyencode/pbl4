# Khối IoT: Node cảm biến chất lượng không khí (ESP32)

> Tài liệu Task A5.2 (kèm ghi chú chu kỳ gửi của Task A7.2). Người phụ trách: Lê Quang Đạt. Cập nhật ngày 10/11/2026.

- Firmware: [`esp32_sensor_node/esp32_sensor_node.ino`](esp32_sensor_node/esp32_sensor_node.ino)
- Sơ đồ đấu nối chi tiết: [`esp32_sensor_node/wiring_diagram.md`](esp32_sensor_node/wiring_diagram.md)
- Cảnh báo tại chỗ và đóng hộp: [`esp32_sensor_node/HUONG_DAN_CANH_BAO_VA_DONG_HOP.md`](esp32_sensor_node/HUONG_DAN_CANH_BAO_VA_DONG_HOP.md)
- Định dạng dữ liệu gửi lên server: [`mqtt_data_contract.md`](mqtt_data_contract.md)

---

## 1. Node làm gì

```text
PMS5003 (PM2.5, PM10) ──┐
DHT11 (nhiệt độ, độ ẩm) ─┼─► ESP32 ──Wi-Fi / MQTT──► Mosquitto (máy chạy Docker) ──► Backend ──► Dashboard
CO2 (mô phỏng)           ┘      │
                                └─► LCD 1602 + 3 đèn LED + còi + nút tắt tiếng (cảnh báo tại chỗ)
```

- Đọc cảm biến **mỗi 10 giây**, gửi **mỗi 30 giây** lên topic `sensors/node-01/data` (JSON theo
  `mqtt_data_contract.md`), kèm thời gian có múi giờ `+07:00` lấy từ NTP.
- **CO2 là giá trị mô phỏng** trong firmware (`simulateCO2()`), vì chưa lắp MH-Z19B. UART2 (chân 25/26) để dành sẵn.
- Mất Wi-Fi hoặc broker: lưu vào **buffer 50 bản ghi** trong RAM, tự gửi bù khi kết nối lại. Đèn và còi vẫn chạy.

## 2. Linh kiện và nối dây

| Linh kiện | Nguồn | Tín hiệu → ESP32 |
|---|---|---|
| ESP32 DevKit | USB 5V | – |
| PMS5003 (qua đế chuyển 8 chân) | VCC → **5V / VIN** (không dùng 3.3V), GND → GND | TXD → **GPIO16**, RXD → GPIO17; SET, RST để trống |
| DHT11 | VCC → 3.3V, GND → GND | DATA → **GPIO4** |
| LCD 1602 + mạch I2C | VCC → 5V, GND → GND | SDA → **GPIO21**, SCL → **GPIO22** (địa chỉ 0x27, hoặc 0x3F) |
| LED xanh / vàng / đỏ | chân ngắn → GND | chân dài → điện trở 220 Ω → **GPIO18 / 19 / 23** |
| Còi active 5V | (+) → 5V | (−) → chân C của S8050; E → GND; B → điện trở 1 kΩ → **GPIO27** |
| Nút tắt tiếng | một chân → GND | chân kia → **GPIO13** (dùng điện trở kéo lên bên trong chip) |

Tất cả GND phải nối chung. **Luôn rút điện trước khi cắm hoặc tháo dây.**
S8050 đặt mặt phẳng quay về phía mình thì thứ tự chân là **E – B – C**.

## 3. Cài phần mềm trên máy nạp firmware (làm 1 lần)

1. Cài **Arduino IDE 2.x** từ <https://www.arduino.cc/en/software>.
2. **File → Preferences → Additional boards manager URLs**, dán:
   `https://espressif.github.io/arduino-esp32/package_esp32_index.json`
3. **Tools → Board → Boards Manager**, tìm `esp32`, cài gói **esp32 by Espressif Systems**.
4. **Tools → Manage Libraries**, tìm đúng tên rồi bấm Install:

   | Tìm theo tên | Tác giả |
   |---|---|
   | PubSubClient | Nick O'Leary |
   | ArduinoJson | Benoit Blanchon |
   | DHT sensor library | Adafruit (cài kèm **Adafruit Unified Sensor** khi được hỏi) |
   | PMS Library | Mariusz Kacki |
   | MH-Z19 | Jonathan Dempsey |
   | LiquidCrystal I2C | Frank de Brabander |

5. Cắm ESP32 mà **Tools → Port** không hiện cổng COM nào: cài driver **CP210x** (Silicon Labs) hoặc
   **CH340**, tùy chip USB in trên board, rồi cắm lại.

## 4. Cấu hình trước khi nạp

Mở `esp32_sensor_node.ino`, sửa khối **CẤU HÌNH THIẾT BỊ** ở đầu file:

```cpp
const char* DEVICE_ID     = "node-01";        // mỗi node một tên riêng: node-01, node-02...
const char* WIFI_SSID     = "<tên Wi-Fi>";    // Wi-Fi 2.4 GHz (ESP32 không bắt được 5 GHz)
const char* WIFI_PASSWORD = "<mật khẩu Wi-Fi>";
const char* MQTT_BROKER   = "<IP máy chạy Docker>";   // ví dụ 192.168.10.4
const int   MQTT_PORT     = 1883;
```

- **`MQTT_BROKER` phải là IP hiện tại của máy chạy Docker** (máy Quyến). Trên máy đó mở PowerShell, gõ `ipconfig`,
  lấy dòng **IPv4 Address** của card mạng đang dùng (Wi-Fi hoặc Ethernet). Bỏ qua `172.x.x.x` của mục *vEthernet (WSL)*.
- ⚠️ **IP đổi khi máy chuyển giữa dây mạng và Wi-Fi**, hoặc khi router cấp lại IP. Ngày 31/10: cắm dây là `192.168.10.2`,
  chuyển sang Wi-Fi thành `192.168.10.4`, và node báo `rc=-2` liên tục. Hôm demo giữ nguyên một kiểu kết nối
  và **kiểm tra IP trước khi cắm node**.
- ESP32 và máy chạy Docker phải **cùng một mạng**: 3 cụm số đầu của IP giống nhau, ví dụ cùng `192.168.10.x`.
- Máy chạy Docker cần mở cổng **1883** qua tường lửa (lệnh ở `docs/LENH_CHAY.md`, mục 8).

## 5. Nạp firmware

1. Cắm ESP32 vào máy bằng cáp USB **có truyền dữ liệu** (cáp chỉ sạc sẽ không hiện cổng COM).
2. **Tools → Board → esp32 → ESP32 Dev Module**; **Tools → Port** chọn cổng COM của ESP32.
3. Bấm **Verify** (✓) để biên dịch, rồi **Upload** (→).
4. Báo `Failed to connect to ESP32` hoặc `Timed out waiting for packet header`: **giữ nút BOOT** trên board
   khi IDE hiện `Connecting....`, thả ra khi bắt đầu nạp.

## 6. Kiểm tra node chạy đúng

Mở **Tools → Serial Monitor**, chọn baud **115200**, bấm nút **EN/RST**. Thứ tự đúng:

```text
=== ESP32 Sensor Node - PBL4 ===
MQTT topic: sensors/node-01/data
MQTT broker: 192.168.10.4
Đang kết nối WiFi.....
WiFi đã kết nối, IP: 192.168.10.xxx        <- 3 cụm đầu phải giống IP broker
Đang đồng bộ NTP..
Giờ hiện tại: 2026-...T...+07:00           <- có đuôi +07:00
Chờ 30s warm-up cảm biến...
Đang kết nối MQTT broker...
Đã kết nối MQTT.
PM2.5=24.0 PM10=25.0 CO2=754 T=29.8 H=78.0 (PMS:THAT)
=== JSON PAYLOAD ===
{"device_id":"node-01","timestamp":"...+07:00","pm25":24,...}
====================
>>> Đã publish MQTT thành công <<<
```

Kiểm tra trên máy chạy Docker:

```powershell
# Node đã kết nối broker chưa: thấy "New client connected ... as esp32-node-01" là được
docker exec aqi_mosquitto tail -n 10 /mosquitto/log/mosquitto.log

# Xem từng gói tin node gửi (Ctrl + C để dừng)
docker exec -it aqi_mosquitto mosquitto_sub -t "sensors/#" -v
```

Nếu Backend đang chạy thì cửa sổ Backend in `Stored sensor reading for node-01`, và Dashboard tự cập nhật.

## 7. Đọc trạng thái trên node

**LCD:** dòng 1 là `PM:<PM2.5> <mức>`, dòng 2 là `T:<nhiệt độ>C H:<độ ẩm>%`.
Mức là `TOT` (≤ 9,0), `TB` (trung bình, 9,1–35,4), `KEM`, `XAU` hoặc `RAT XAU`, cùng tên mức với Dashboard nhưng tính theo PM2.5 trung bình 2 phút. `IM` nghĩa là đang tắt tiếng; `LOI` là chưa có số đo hoặc PMS5003 lỗi.

**Đèn và còi** dựa trên **PM2.5 trung bình 2 phút** (12 lần đọc), không dựa trên AQI. Bảng mức theo US EPA 2024, giống Backend:

| PM2.5 TB 2 phút (µg/m³) | Đèn | Còi |
|---|---|---|
| ≤ 35,4 | Xanh | Im |
| 35,5 – 55,4 | Vàng | Kêu **1 tiếng** khi chuyển từ xanh sang (lúc vừa khởi động mà đã ở mức vàng thì không kêu) |
| 55,5 – 125,4 | Đỏ | Kêu **3 tiếng** khi vừa chuyển sang |
| > 125,4 | Đỏ nháy | Kêu 3 tiếng, **lặp lại mỗi 60 giây** |
| Chưa có số đo / PMS lỗi | Vàng nháy | Im |

- Muốn hạ mức thì PM2.5 phải giảm thêm **2 µg/m³** dưới ranh giới, để đèn không nhảy qua lại liên tục.
- Còi chỉ kêu khi chất lượng **xấu đi**, không kêu khi tốt lên.
- **Nút tắt tiếng:** bấm 1 lần thì im 30 phút (LCD hiện `IM`), đèn vẫn chạy; bấm lần nữa thì còi bật lại.
- **22h–6h:** chỉ bật đèn, còi không kêu.
- Vừa cấp điện: sáng cả 3 đèn và kêu 1 tiếng để tự kiểm tra.

## 8. Cấp nguồn và lắp đặt (chạy độc lập)

1. Nạp firmware xong, rút cáp khỏi máy tính.
2. Cắm cáp USB vào **củ sạc 5V, từ 1A trở lên** (ví dụ củ sạc điện thoại 5V/2A). Quạt PMS5003 ăn dòng khoảng 100 mA,
   lúc khởi động lên tới khoảng 200 mA, nên không dùng củ sạc yếu.
3. **Không** cắm linh kiện thẳng vào ổ điện 220V. **Không** cấp 5V vào chân 3.3V.
   **Không** vừa cấp nguồn qua chân VIN vừa cắm USB máy tính cùng lúc.
4. Đặt node chỗ **khô ráo, thoáng gió**. Không úp cửa hút/xả của PMS5003 vào tường; mạch hở không chạm khung kim loại;
   tránh nắng chiếu trực tiếp, mưa, và nguồn khói hoặc nhiệt cục bộ (bếp, quạt hút).
5. Khi đóng hộp: khoét lỗ cho cả cửa hút lẫn cửa xả của PMS5003; đặt DHT11 sát lỗ thông gió, xa ESP32 vì ESP32 hơi ấm khi chạy.
6. Dữ liệu tự gửi về server, không cần mở Serial Monitor. Kiểm tra bằng Dashboard hoặc log Mosquitto (mục 6).

## 9. Bảo trì

Node dùng nguồn từ củ sạc USB, **không dùng pin**. Nếu chạy bằng sạc dự phòng thì sạc lại trước khi cạn. Một số
sạc dự phòng tự ngắt khi dòng nhỏ, nên không hợp để chạy qua đêm. Node mất điện là mất luôn dữ liệu đang nằm trong buffer.

| Việc | Khi nào | Cách làm |
|---|---|---|
| Kiểm tra node còn gửi | Hằng ngày | Dashboard có số mới trong vài phút gần nhất; hoặc lệnh ở mục 6 |
| Vệ sinh PMS5003 | Khoảng 1 tháng/lần, hoặc khi số PM thấp hoặc đứng yên bất thường | Rút điện, thổi nhẹ bụi ở cửa hút/xả. **Không** mở vỏ, không xịt nước hay cồn vào |
| Kiểm tra dây | Sau mỗi lần di chuyển node, hoặc khi LCD báo `LOI` | Ấn chặt dây dupont; cáp PMS cắm chắc vào đế chuyển |
| Đối chiếu số đo | Định kỳ | So PM2.5 với một nguồn tham chiếu (ví dụ app IQAir, trạm gần nhất), ghi lại độ lệch |
| Kiểm tra IP broker | Mỗi khi đổi mạng hoặc máy chạy Docker khởi động lại | Làm lại mục 4 và 5 |
| Cập nhật firmware | Khi repo có bản mới | Pull code, giữ lại cấu hình Wi-Fi/IP của mình, nạp lại |

Theo nhà sản xuất, quạt và laser của PMS5003 bền khoảng **8.000 giờ chạy liên tục** (~1 năm). Nếu chạy lâu dài,
nên tăng chu kỳ gửi (mục 10).

**Buffer khi mất mạng:** node giữ tối đa **50 bản ghi** gần nhất trong RAM (khoảng 25 phút ở chu kỳ 30 giây), gửi bù
khi kết nối lại. Buffer đầy thì bỏ bản ghi cũ nhất. Buffer **mất** khi node mất điện, bị reset hoặc nạp lại code. Khi bật
lại hệ thống, chạy **Backend ngay sau Docker** để không bỏ lỡ phần dữ liệu node gửi bù.

## 10. Chu kỳ đọc và gửi (Task A7.2)

| Thông số | Giá trị hiện tại | Lý do |
|---|---|---|
| `READ_INTERVAL_MS` | 10.000 (10 s) | Đủ dày để tính PM2.5 trung bình 2 phút (12 mẫu) cho cảnh báo tại chỗ, phản ứng nhanh khi có khói |
| `SEND_INTERVAL_MS` | 30.000 (30 s) | **Chế độ demo**: Dashboard cập nhật gần thời gian thực. Khoảng 2.880 bản ghi/ngày, ~0,4 MB/ngày với gói tin ~150 byte |
| Đề xuất khi chạy lâu dài | 300.000 (5 phút) | AI chỉ dùng trung bình theo giờ, 12 mẫu/giờ là đủ. Số bản ghi giảm 10 lần (~288/ngày), đỡ tải broker và DB |
| `BUFFER_SIZE` | 50 bản ghi | Ở 30 s giữ được ~25 phút mất mạng; ở 5 phút giữ được ~4 giờ |
| `WIFI_RETRY_MS` / `MQTT_RETRY_MS` | 30 s / 30 s | Mỗi lần thử kết nối broker có thể chặn ~3 s, nên thử thưa để đèn, còi, nút bị gián đoạn ít nhất |

Cảnh báo tại chỗ dựa trên chu kỳ **đọc** (10 s), nên tăng chu kỳ gửi lên 5 phút không làm chậm đèn và còi.

## 11. Kết quả chạy thử dài giờ

| Lần chạy | Kết quả |
|---|---|
| 31/10 13:57 → 01/11 01:57: 12 giờ, nguồn củ sạc 5V, gửi 30 s/lần | **1.438 bản ghi** (lý thuyết 1.440, ~99,9%), **0** khoảng mất dữ liệu > 2 phút |
| Buffer khi mất kết nối (31/10, broker sai IP) | Giữ 14 bản ghi, gửi bù đủ khi kết nối lại |

Cách đếm: `docs/LENH_CHAY.md` mục 12. Đánh giá chất lượng dữ liệu thật: `ai/MODEL_CARD.md` mục 2.2.

## 12. Lỗi thường gặp

| Hiện tượng (Serial / LCD) | Nguyên nhân | Cách xử lý |
|---|---|---|
| `WiFi kết nối thất bại!` | Sai tên hoặc mật khẩu, Wi-Fi 5 GHz, node ở xa router | Sửa `WIFI_SSID` / `WIFI_PASSWORD`, dùng Wi-Fi 2.4 GHz, đặt node gần router |
| `Kết nối MQTT thất bại, rc=-2` lặp lại | **IP máy chạy Docker đã đổi**, Docker chưa chạy, tường lửa chặn cổng 1883, khác mạng | `ipconfig` rồi sửa `MQTT_BROKER` và nạp lại; mở Docker; mở cổng 1883 |
| `(PMS:LOI)`, `Không nhận được dữ liệu từ PMS5003`, LCD `LOI`, đèn vàng nháy | PMS5003 không gửi dữ liệu | Kiểm tra 5V; **đổi chỗ 2 dây GPIO16/GPIO17**; đợi đủ 30 giây khởi động |
| `T=nan H=nan`, LCD hiện `--` (ngay từ lúc khởi động) | DHT11 chưa đọc được lần nào. Nếu đang chạy mà DHT11 lỗi, node giữ giá trị đọc được gần nhất | Kiểm tra dây DATA vào GPIO4; thêm điện trở 10 kΩ giữa DATA và VCC nếu module không có sẵn |
| `Giờ hiện tại: chưa đồng bộ được NTP` | Wi-Fi không ra được Internet | Node vẫn gửi, server tự gán giờ nhận; kiểm tra mạng |
| LCD sáng nhưng không có chữ | Sai địa chỉ I2C hoặc chưa chỉnh độ tương phản | Đổi `0x27` thành `0x3F` trong code; vặn biến trở xanh sau LCD |
| Còi không kêu dù PM cao | Mức vàng chỉ kêu 1 tiếng ngắn; đang tắt tiếng (`IM`); đang trong khung 22h–6h; cắm ngược chân S8050 | Bấm nút để bật lại còi; kiểm tra thứ tự chân E – B – C |
| Đèn sai màu | Đổi chỗ dây GPIO19 và GPIO23 | Vàng → GPIO19, đỏ → GPIO23 |
| Độ ẩm đứng yên ở 80% về đêm | DHT11 bão hoà ở độ ẩm cao (cảm biến rẻ, sai số ±5%) | Không phải lỗi, ghi vào phần hạn chế. Muốn chính xác hơn thì thay DHT22 hoặc SHT31 |

## 13. Lưu ý bảo mật

File firmware trong repo đang chứa tên và mật khẩu Wi-Fi thật để tiện demo. Trước khi để repo public hoặc nộp mã nguồn,
thay bằng giá trị mẫu (`"<tên Wi-Fi>"`, `"<mật khẩu Wi-Fi>"`) rồi mới commit.

## 14. Danh sách kiểm tra nghiệm thu (A5.2)

Người kiểm tra (không phải người viết tài liệu) tự làm theo mục 3–6 rồi tick:

- [ ] Cài được Arduino IDE, board ESP32 và đủ thư viện
- [ ] Sửa cấu hình Wi-Fi/MQTT và nạp firmware thành công
- [ ] Serial Monitor hiện `Đã kết nối MQTT.` và `Đã publish MQTT thành công`
- [ ] Log Mosquitto có `esp32-node-01`, Dashboard hiện số mới
- [ ] Không phải hỏi thêm người phụ trách IoT

Người kiểm tra: ______________ Ngày: ____/____/2026
