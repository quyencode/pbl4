# Model Card — Mô hình dự báo chất lượng không khí

> Điền lại các mục có "..." sau khi huấn luyện xong. File này dùng để đưa vào
> báo cáo cuối kỳ và giải thích mô hình khi bảo vệ đồ án.

## 1. Bài toán
- Đầu vào: chuỗi lịch sử **24 giờ** gần nhất của PM2.5, PM10, CO2, nhiệt độ, độ ẩm
- Đầu ra: dự báo **PM2.5 (hoặc AQI)** cho **1–24 giờ tiếp theo**
- Loại bài toán: hồi quy chuỗi thời gian đa bước (multi-step time series regression)

## 2. Dữ liệu
- Nguồn dữ liệu: **dữ liệu mô phỏng** `ai/data/mock_readings.csv` (sinh bằng `ai/generate_mock_data.py`).
  Node thật chưa thu đủ dữ liệu nên lần huấn luyện v1 này chưa dùng số đo thật; sẽ huấn luyện lại khi có.
- Khoảng thời gian (mô phỏng): 24/08/2026 đến 22/09/2026 (30 ngày)
- Số lượng bản ghi: 720 (1 bản ghi/giờ)
- Tần suất lấy mẫu: dữ liệu mô phỏng đã ở mức 1 giờ/điểm; dữ liệu thật từ node (5 phút/lần) sẽ được resample về 1 giờ/điểm
- Tỉ lệ chia tập: Train 70% / Validation 15% / Test 15%

## 3. Kiến trúc mô hình
- Loại mô hình: LSTM (v1). CNN-LSTM sẽ thử ở Task C7.1 để so sánh.
- Số layer, số unit: LSTM(64, return_sequences) → LSTM(32) → Dense(32) → Dense(24)
- Số đặc trưng đầu vào: 5 (PM2.5, PM10, CO2, nhiệt độ, độ ẩm), chuẩn hoá MinMax 0–1
- Window size (đầu vào): 24 bước
- Horizon (đầu ra): 24 bước
- Optimizer / Loss: Adam / MSE
- Số epoch huấn luyện thực tế: 50 (khoảng 15–20 giây trên CPU)
- File mô hình: `model/lstm_model.keras` (tạo bởi `train_model.py --model_type lstm`)

## 4. Kết quả đánh giá (tập Test)

| Mô hình | MAE (µg/m³) | RMSE (µg/m³) | MAPE (%) |
|---|---|---|---|
| **Baseline (Persistence)** | 8.66 | 10.77 | 26.96% |
| **LSTM** | 8.34 | 9.73 | 29.10% |

- **Thời gian huấn luyện:** 50 epochs (khoảng 15–20 giây).
- **Đánh giá:** LSTM tốt hơn baseline Persistence một chút về MAE (8.34 so với 8.66, giảm ~4%)
  và RMSE (9.73 so với 10.77, giảm ~10%), nhưng **kém hơn về MAPE** (29.10% so với 26.96%).
  Nghĩa là LSTM giảm được các sai số lớn, nhưng chưa vượt trội rõ rệt so với cách đơn giản
  "lấy giá trị đo gần nhất".
- **Nguyên nhân nghi ngờ:** tập dữ liệu nhỏ (720 giờ, sau khi chia chỉ ~100 cửa sổ test) và là
  dữ liệu mô phỏng có quy luật lặp theo ngày, nên chưa đủ để đánh giá chắc chắn. Cần huấn luyện
  và đánh giá lại trên dữ liệu thật từ node.

## 5. Công thức tính AQI từ PM2.5 (nếu áp dụng)
- Theo bảng breakpoint PM2.5 của **US EPA (cập nhật 2024)**, cài đặt ở `backend/app/aqi.py`
  (bản sao `ai/aqi.py` dùng cho điểm dự báo), nên Backend, AI và Dashboard hiển thị cùng một số.
- Công thức nội suy tuyến tính: AQI = (I_hi − I_lo) / (C_hi − C_lo) × (C − C_lo) + I_lo

| PM2.5 (µg/m³) | AQI | Mức |
|---|---|---|
| 0.0 – 9.0 | 0 – 50 | Tốt |
| 9.1 – 35.4 | 51 – 100 | Trung bình |
| 35.5 – 55.4 | 101 – 150 | Kém (nhóm nhạy cảm) |
| 55.5 – 125.4 | 151 – 200 | Xấu |
| 125.5 – 225.4 | 201 – 300 | Rất xấu |
| 225.5 – 325.4 | 301 – 500 | Nguy hại |

## 6. Giới hạn của mô hình
- Dự báo chỉ đáng tin trong phạm vi dữ liệu huấn luyện đã thấy (không ngoại suy tốt
  cho điều kiện bất thường, ví dụ cháy rừng, pháo hoa...).
- Cần dữ liệu lịch sử tối thiểu 24 giờ liên tục để dự báo được.
- Bản v1 mới huấn luyện trên dữ liệu mô phỏng, chưa phản ánh đúng biến động thật của không khí.
- CO2 trong dữ liệu là giá trị mô phỏng (nhóm chưa có cảm biến MH-Z19B).

## 7. Kế hoạch cải thiện
- Thu thập dữ liệu dài hạn hơn
- Bổ sung dữ liệu khí tượng từ nguồn mở
- Thử nghiệm thêm kiến trúc Transformer/Attention nếu có thời gian

## 8. Thống kê và đánh giá chất lượng dữ liệu (Task C4.2, trên dữ liệu mô phỏng)
- **Tổng số mẫu (Records):** 720 dòng dữ liệu liên tục (`RangeIndex: 720 entries`).
- **Các đặc trưng (Features):** `device_id`, `timestamp`, `temperature`, `humidity`, `pm25`, `pm10`, `co2`.
- **Tỷ lệ thiếu dữ liệu (Missing Values):**
  - `device_id`, `pm10`, `temperature`, `humidity`, `timestamp`: 0% (Hoàn chỉnh).
  - `pm25`: Thiếu ~1.67% (12 mẫu).
  - `co2`: Thiếu ~0.97% (7 mẫu).
  - *Đánh giá:* Tỷ lệ thiếu rất thấp, đã được xử lý làm sạch trước khi đưa vào mô hình.
- **Biên độ giá trị thực tế & mô phỏng (Min/Max/Mean):**
  - **Temperature:** Min = 21.60°C, Max = 36.40°C, Mean = 28.49°C
  - **Humidity:** Min = 55.90%, Max = 88.80%, Mean = 71.95%
  - **PM2.5:** Min = 16.80 µg/m³, Max = 64.20 µg/m³, Mean = 38.04 µg/m³
  - **PM10:** Min = 24.10 µg/m³, Max = 102.10 µg/m³, Mean = 59.03 µg/m³
  - **CO2:** Min = 441.00 ppm, Max = 609.00 ppm, Mean = 500.39 ppm
