# Model Card — Mô hình dự báo chất lượng không khí

> Cập nhật 10/11/2026 cho mô hình đang chạy thật (`model/lstm_model.keras` + `model/scaler.pkl`, PR #23 của Lợi).
> Mọi số trong mục 4 đã được **chạy lại** từ đúng file mô hình và scaler trong repo trên tập test mô phỏng,
> kết quả trùng với số Lợi báo khi huấn luyện. Lợi kiểm tra lại mục 3 (cách train) và bổ sung nếu thiếu.

## 1. Bài toán
- Đầu vào: chuỗi lịch sử **24 giờ** gần nhất (trung bình theo giờ) của 5 đặc trưng:
  `pm25`, `pm10`, `co2`, `temperature`, `humidity` (đúng thứ tự `FEATURE_COLUMNS` trong `ai/preprocess.py`).
- Đầu ra: dự báo **PM2.5 cho 24 giờ tiếp theo** (24 giá trị, ra thẳng một lần, không dự báo cuốn chiếu).
  AQI của từng giờ được tính từ PM2.5 dự báo theo bảng US EPA (mục 5).
- Loại bài toán: hồi quy chuỗi thời gian đa biến, đa bước (multivariate multi-step regression).

## 2. Dữ liệu

### 2.1. Dữ liệu huấn luyện: mô phỏng
- File: `ai/data/mock_readings.csv`, sinh bằng `ai/generate_mock_data.py`.
- Khoảng thời gian (mô phỏng): 24/08/2026 → 22/09/2026, **720 bản ghi** (1 bản ghi/giờ, 30 ngày).
- Lý do dùng mô phỏng: tới lúc huấn luyện, node thật chưa chạy liên tục đủ lâu
  (cần ≥ 48 giờ liên tục chỉ để có 1 cửa sổ 24 giờ vào + 24 giờ ra).
- Thống kê đã làm ở Task C4.2 (xem mục 8): thiếu `pm25` ~1.67%, `co2` ~0.97%, đã nội suy trước khi train.

### 2.2. Dữ liệu thật từ node (đánh giá chất lượng, Task C4.1–C4.2)
- File: `ai/data/node-01_real.csv`, xuất bằng `fetch_data.py` rồi lọc từ **31/10/2026 13:57**
  (cách làm: `docs/LENH_CHAY.md` mục 13). File gốc `node-01.csv` còn chứa dữ liệu mô phỏng cũ, **không dùng** làm dữ liệu thật.
- Khoảng thời gian: **31/10/2026 13:57:50 → 01/11/2026 02:38:16** (12,7 giờ), **1.519 bản ghi**, chu kỳ 30 giây.

| Tiêu chí | Kết quả |
|---|---|
| Khoảng cách giữa 2 bản ghi | trung vị 30 s, 95% ≤ 30 s, lớn nhất 86 s (1 lần duy nhất > 60 s) |
| Khoảng mất dữ liệu > 2 phút | **0** |
| Bản ghi trùng thời gian | 0 |
| Thiếu giá trị | `pm25`, `pm10`, `aqi`: 1 bản ghi (0,07%, một lần PMS5003 không trả frame); các cột khác 0% |
| Ngoài ngưỡng vật lý (PM < 0 hoặc > 1000, nhiệt độ ngoài −10…60 °C, độ ẩm ngoài 0…100%) | 0 |
| PM10 < PM2.5 (vô lý vì PM10 bao gồm PM2.5) | 0 |

| Cột | Nguồn | Min | Trung bình | Max |
|---|---|---|---|---|
| PM2.5 (µg/m³) | **đo thật** (PMS5003) | 19 | 36,1 | 54 |
| PM10 (µg/m³) | **đo thật** (PMS5003) | 21 | 42,3 | 68 |
| Nhiệt độ (°C) | **đo thật** (DHT11) | 28,0 | 30,3 | 35,2 |
| Độ ẩm (%) | **đo thật** (DHT11) | 64 | 75,5 | 80 |
| CO2 (ppm) | **mô phỏng trong firmware** | 380 | 649 | 1.046 |

Nhận xét:
- Diễn biến hợp lý với thực tế: bụi thấp buổi chiều (TB giờ PM2.5 ≈ 24 lúc 15h), tăng mạnh 17h–19h
  (cao nhất TB giờ ≈ 45 lúc 19h, giờ tan tầm/nấu ăn), giảm dần về khuya; nhiệt độ giảm và độ ẩm tăng về đêm.
- Các điểm bất thường đều giải thích được:
  - 14:06: PM2.5 tăng vọt 13 µg/m³ trong 30 s. Đây là lúc nhóm **đốt thử để test cảnh báo**.
  - 17:46–17:47: nhiệt độ nhảy 3,4 °C, độ ẩm 9% rồi trở lại bình thường. Nhiều khả năng node bị cầm lên, di chuyển
    hoặc ở gần nguồn nhiệt trong chốc lát (chưa xác nhận với Đạt), không phải lỗi cảm biến.
- **Độ ẩm bị kẹt ở 80%** từ khoảng 00:00 trở đi (đúng 80,0 suốt hơn 2 giờ). Nhiều khả năng DHT11 đã bão hoà
  ở độ ẩm cao (cảm biến rẻ, sai số ±5%), không phải độ ẩm thật dừng ở 80%. Cần ghi vào phần hạn chế.
- PM2.5 là số nguyên (PMS5003 trả số nguyên); độ ẩm DHT11 có bước 1%.

## 3. Kiến trúc mô hình và cách huấn luyện
- Loại mô hình: **LSTM** (`build_lstm_model` trong `ai/train_model.py`, chạy với `--model_type lstm`).
  Code CNN-LSTM (`--model_type cnn_lstm`) đã có nhưng **chưa huấn luyện/đánh giá** (Task C7.1).
- Kiến trúc (đọc lại từ file `model/lstm_model.keras`):

| Lớp | Đầu ra | Số tham số |
|---|---|---|
| Input | (24, 5) | – |
| LSTM(64, return_sequences=True) | (24, 64) | 17.920 |
| LSTM(32) | (32) | 12.416 |
| Dense(32, ReLU) | (32) | 1.056 |
| Dense(24) | (24) | 792 |
| **Tổng** | | **32.184** |

- Tiền xử lý (`prepare_dataset` trong `ai/preprocess.py`): làm sạch, nội suy giá trị thiếu, trung bình theo giờ;
  chia theo thời gian **70% train / 15% validation / 15% test** (không xáo trộn); `MinMaxScaler` 0–1
  **chỉ fit trên phần train**, rồi lưu thành `model/scaler.pkl` (+ bản sao `ai/model/scaler.pkl`).
- Số cửa sổ: train 456, validation 62, **test 61**.
- Optimizer / Loss: Adam / MSE; `batch_size=32`; tối đa 50 epoch, **EarlyStopping (patience = 5)**,
  giữ trọng số tốt nhất trên validation.
- `predict.py` nạp **đúng** `scaler.pkl` này (không fit lại), lấy 24 giờ gần nhất từ Backend, dự báo 24 giờ và
  gửi về `POST /api/forecasts`; chạy tự động mỗi giờ bằng Windows Scheduled Task `PBL4-AirQuality-Predict`.

## 4. Kết quả đánh giá (tập Test mô phỏng, 61 cửa sổ × 24 giờ)

| Mô hình | MAE (µg/m³) | RMSE (µg/m³) | MAPE (%) |
|---|---|---|---|
| Baseline Persistence (lấy giá trị giờ cuối, lặp cho 24 giờ) | 8,66 | 10,77 | 26,96% |
| LSTM v1 cũ (bản trước PR #23, chỉ ghi lại để so sánh) | 8,34 | 9,73 | 29,10% |
| **LSTM 5 đặc trưng (đang dùng)** | **5,67** | **6,58** | **18,99%** |

- So với baseline, mô hình đang dùng giảm MAE **~35%** (8,66 → 5,67), RMSE **~39%** (10,77 → 6,58),
  MAPE **~8 điểm %** (26,96% → 18,99%). Bản v1 cũ chỉ hơn baseline một chút và còn kém hơn về MAPE.
- MAE theo bước dự báo: giờ thứ 1 ≈ **4,83**, giờ 6 ≈ 5,05, giờ 12 ≈ 5,90, giờ 24 ≈ 5,87 µg/m³.
  Dự báo càng xa thì sai số càng tăng, nhưng tăng chậm.
- **Chưa đánh giá được trên dữ liệu thật:** mới có 12,7 giờ liên tục, chưa đủ 48 giờ để tạo một cửa sổ đánh giá
  (24 giờ vào + 24 giờ ra). Script `ai/evaluate_real.py` đã sẵn sàng; chạy lại khi node có ≥ 3 ngày dữ liệu liên tục.
- Cách tái lập số trên: nạp `model/lstm_model.keras`, gọi `prepare_dataset(mock_readings.csv, 24, 24)`,
  dự báo `X_test`, dùng `evaluate()` và `persistence_baseline()` trong `train_model.py`.

## 5. Công thức tính AQI từ PM2.5
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
- **Huấn luyện và đánh giá hoàn toàn trên dữ liệu mô phỏng.** Kết quả mục 4 cho biết mô hình học được quy luật
  của dữ liệu mô phỏng, chưa chứng minh được độ chính xác với không khí thật.
- **CO2 lệch miền giữa lúc train và lúc chạy thật.** CO2 trong dữ liệu train nằm trong 441–609 ppm, còn CO2 mô phỏng
  trong firmware dao động 380–1.046 ppm (600 ± 400 theo chu kỳ 60 phút, cộng nhiễu, chặn dưới ở 380). Trung bình theo giờ
  của dữ liệu thật là **635–737 ppm**, cao hơn mức lớn nhất mô hình từng thấy, nên sau chuẩn hoá ra **1,24–1,78**
  (ngoài khoảng 0–1). Thử trên tập test, chỉ thay CO2 thành 650 ppm: dự báo PM2.5 **cao lên trung bình ~4,3 µg/m³**
  (MAE 5,67 → 9,82); thay thành 740 ppm thì cao lên ~6 µg/m³ (MAE 12,0).
  Đây là một nguyên nhân khiến dự báo trên Dashboard thường **cao hơn số đo thực tế**.
- Cần dữ liệu lịch sử 24 giờ gần nhất. Khi node mới chạy lại, `predict.py` phải dùng cả dữ liệu cũ hoặc có
  khoảng trống, nên dự báo các giờ đầu kém tin cậy.
- PMS5003 đo cao hơn thực tế khi độ ẩm cao (> ~75%) do hạt bụi hút ẩm; DHT11 đứng ở 80% độ ẩm về đêm (mục 2.2).
- Không ngoại suy tốt cho tình huống bất thường (cháy, pháo hoa, đốt rác sát cảm biến…).

## 7. Kế hoạch cải thiện
- **Sửa lệch CO2** (ưu tiên, việc nhỏ), chọn một trong hai:
  (a) bỏ `co2` khỏi `FEATURE_COLUMNS` vì CO2 đang là mô phỏng ở cả hai phía, rồi train lại với 4 đặc trưng; hoặc
  (b) cho `generate_mock_data.py` sinh CO2 giống firmware, rồi train lại. Sau đó cập nhật lại mục 3–4.
- Thu thập dữ liệu thật ≥ 3–7 ngày liên tục, chạy `evaluate_real.py`, rồi fine-tune/huấn luyện lại trên dữ liệu thật.
- Huấn luyện CNN-LSTM (Task C7.1) và so sánh với LSTM + baseline trong cùng một bảng.
- Bổ sung dữ liệu khí tượng từ nguồn mở; thử Transformer/Attention nếu có thời gian.

## 8. Thống kê và đánh giá chất lượng dữ liệu mô phỏng (Task C4.2)
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
