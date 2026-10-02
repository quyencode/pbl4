# Model Card — Mô hình dự báo chất lượng không khí

> Điền lại các mục có "..." sau khi huấn luyện xong. File này dùng để đưa vào
> báo cáo cuối kỳ và giải thích mô hình khi bảo vệ đồ án.

## 1. Bài toán
- Đầu vào: chuỗi lịch sử **24 giờ** gần nhất của PM2.5, PM10, CO2, nhiệt độ, độ ẩm
- Đầu ra: dự báo **PM2.5 (hoặc AQI)** cho **1–24 giờ tiếp theo**
- Loại bài toán: hồi quy chuỗi thời gian đa bước (multi-step time series regression)

## 2. Dữ liệu
- Nguồn dữ liệu: ...
- Khoảng thời gian thu thập: ... đến ...
- Số lượng bản ghi: ...
- Tần suất lấy mẫu gốc: mỗi 5 phút → resample về 1 giờ/điểm
- Tỉ lệ chia tập: Train 70% / Validation 15% / Test 15%

## 3. Kiến trúc mô hình
- Loại mô hình: LSTM / CNN-LSTM (chọn một, ghi rõ lý do)
- Số layer, số unit: ...
- Window size (đầu vào): 24 bước
- Horizon (đầu ra): 24 bước
- Optimizer / Loss: Adam / MSE
- Số epoch huấn luyện thực tế: ...

## 4. Kết quả đánh giá (tập Test)

| Mô hình | MAE (µg/m³) | RMSE | MAPE (%) |
|---|---|---|---|
| Baseline (Persistence) | ... | ... | ... |
| LSTM | ... | ... | ... |
| CNN-LSTM | ... | ... | ... |

## 5. Công thức tính AQI từ PM2.5 (nếu áp dụng)
- Ghi rõ công thức/breakpoints sử dụng (vd: theo chuẩn US EPA) để Backend và
  Dashboard hiển thị nhất quán.

## 6. Giới hạn của mô hình
- Dự báo chỉ đáng tin trong phạm vi dữ liệu huấn luyện đã thấy (không ngoại suy tốt
  cho điều kiện bất thường, ví dụ cháy rừng, pháo hoa...).
- Cần dữ liệu lịch sử tối thiểu 24 giờ liên tục để dự báo được.
- ...

## 7. Kế hoạch cải thiện
- Thu thập dữ liệu dài hạn hơn
- Bổ sung dữ liệu khí tượng từ nguồn mở
- Thử nghiệm thêm kiến trúc Transformer/Attention nếu có thời gian
## Task4loi Thống kê và đánh giá chất lượng dữ liệu (Dataset Quality)
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