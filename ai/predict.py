"""
Service suy luận: lấy dữ liệu gần nhất (5 đặc trưng), chạy mô hình đa biến đã huấn luyện,
và gửi kết quả dự báo về Backend qua POST /api/forecasts.

Chạy thủ công (từ thư mục gốc repo): py -3.12 ai\\predict.py --device_id node-01
Chạy định kỳ: dùng cron / Task Scheduler gọi run_once() mỗi giờ.
"""
import argparse
import os
import joblib
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import requests
import tensorflow as tf
from sklearn.preprocessing import MinMaxScaler

from aqi import pm25_to_aqi
from fetch_data import fetch_readings
from preprocess import clean_data, resample_hourly, FEATURE_COLUMNS

AI_DIR = os.path.dirname(os.path.abspath(__file__))

BACKEND_API_BASE_URL = os.getenv("BACKEND_API_BASE_URL", "http://localhost:8000")
FORECAST_HORIZON_HOURS = int(os.getenv("FORECAST_HORIZON_HOURS", 24))
# Trỏ đúng đường dẫn mô hình đa biến (model/lstm_model.keras hoặc ai/model/lstm_model.keras)
MODEL_PATH = os.getenv("MODEL_PATH", os.path.join(AI_DIR, "..", "model", "lstm_model.keras"))
SCALER_PATH = os.getenv("SCALER_PATH", os.path.join(AI_DIR, "model", "scaler.pkl"))
TRAINING_DATA_PATH = os.getenv("TRAINING_DATA_PATH", os.path.join(AI_DIR, "data", "node-01.csv"))

# Danh sách 5 đặc trưng đầu vào tương ứng với mô hình đa biến
# Phải đúng thứ tự cột lúc train (preprocess.FEATURE_COLUMNS) vì scaler.pkl được fit theo thứ tự này
FEATURE_COLS = FEATURE_COLUMNS
TARGET_COL = "pm25"
WINDOW_SIZE = 24  # Số giờ lịch sử mô hình cần (24 bước thời gian)
FETCH_LIMIT = int(os.getenv("PREDICT_FETCH_LIMIT", 5000))  # 30 giây/bản ghi: 5000 ≈ 42 giờ, đủ cửa sổ 24 giờ


def load_model():
    return tf.keras.models.load_model(MODEL_PATH)


def load_scaler(recent_values: np.ndarray) -> MinMaxScaler:
    """Nạp đúng scaler đã được lưu lúc train (scaler.pkl) bằng joblib, tuyệt đối không fit lại nếu có sẵn."""
    if os.path.exists(SCALER_PATH):
        # Sử dụng joblib.load thay vì pickle để khớp với lúc train_model.py lưu file
        scaler = joblib.load(SCALER_PATH)
        return scaler

    if os.path.exists(TRAINING_DATA_PATH):
        df_train = resample_hourly(clean_data(pd.read_csv(TRAINING_DATA_PATH)))
        # Đảm bảo đủ các cột đặc trưng
        available_cols = [c for c in FEATURE_COLS if c in df_train.columns]
        scaler = MinMaxScaler(feature_range=(0, 1))
        scaler.fit(df_train[available_cols].values)
        return scaler

    raise FileNotFoundError("Không tìm thấy file scaler.pkl hoặc dữ liệu huấn luyện để chuẩn hóa 5 đặc trưng!")


def run_once(device_id: str):
    df = fetch_readings(device_id, limit=FETCH_LIMIT)
    if df is None or df.empty:
        print(f"Chưa có dữ liệu nào cho {device_id}, bỏ qua lần dự báo này.")
        return

    df = clean_data(df)
    df = resample_hourly(df)
    
    # Kiểm tra xem đủ 5 đặc trưng chưa, nếu thiếu cột nào có thể điền tạm bằng 0 hoặc xử lý phù hợp
    for col in FEATURE_COLS:
        if col not in df.columns:
            df[col] = 0.0

    if len(df) < WINDOW_SIZE:
        print(
            f"Chưa đủ dữ liệu để dự báo cho {device_id}: mới có {len(df)} giờ, "
            f"cần >= {WINDOW_SIZE} giờ liên tục."
        )
        return

    # Lấy 24 dòng gần nhất của 5 đặc trưng
    recent_data = df[FEATURE_COLS].values[-WINDOW_SIZE:].astype("float64")
    
    scaler = load_scaler(recent_data)
    scaled_window = scaler.transform(recent_data) # Chuẩn hóa 2D: (24, 5)

    model = load_model()
    
    # Reshape thành đầu vào mô hình: (batch_size=1, timesteps=24, features=5)
    X_input = scaled_window.reshape(1, WINDOW_SIZE, len(FEATURE_COLS))
    
    # Mô hình dự báo thẳng ra 24 giờ tiếp theo (Multi-output hoặc Dense layer trực tiếp)
    y_pred_scaled = model.predict(X_input, verbose=0)
    
    # Đảm bảo shape đầu ra là (24,) hoặc (1, 24) cho riêng cột PM2.5 hoặc nhiều cột
    y_pred_scaled = y_pred_scaled.reshape(-1)
    
    # Nếu scaler được fit trên 5 cột, cần tạo dummy array để inverse_transform chính xác cột pm25
    target_idx = FEATURE_COLS.index(TARGET_COL)
    if scaler.n_features_in_ == len(FEATURE_COLS):
        dummy = np.zeros((len(y_pred_scaled), len(FEATURE_COLS)))
        dummy[:, target_idx] = y_pred_scaled
        y_pred = scaler.inverse_transform(dummy)[:, target_idx]
    else:
        # Trường hợp scaler đơn biến cũ
        y_pred = y_pred_scaled

    # Nồng độ bụi không thể âm
    y_pred = np.clip(y_pred, 0, None)

    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    predictions = [
        {
            "timestamp": (now + timedelta(hours=i + 1)).isoformat(),
            "pm25": round(float(value), 1),
            "aqi": pm25_to_aqi(float(value)),
        }
        for i, value in enumerate(y_pred[:FORECAST_HORIZON_HOURS])
    ]

    payload = {
        "device_id": device_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "horizon_hours": FORECAST_HORIZON_HOURS,
        "predictions": predictions,
    }

    try:
        resp = requests.post(f"{BACKEND_API_BASE_URL}/api/forecasts", json=payload, timeout=30)
        resp.raise_for_status()
        print(
            f"Đã gửi dự báo cho {device_id}: {len(predictions)} điểm, "
            f"PM2.5 giờ tới ~{predictions[0]['pm25']} µg/m³ (AQI {predictions[0]['aqi']})."
        )
    except requests.exceptions.RequestException as e:
        print(f"Lỗi khi gửi kết quả dự báo về Backend: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--device_id", required=True)
    args = parser.parse_args()
    run_once(args.device_id)