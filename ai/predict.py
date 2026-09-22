"""
Service suy luận: định kỳ lấy dữ liệu gần nhất, chạy mô hình đã huấn luyện,
và gửi kết quả dự báo về Backend qua POST /api/forecasts.

Chạy thủ công: python predict.py --device_id node-01
Chạy định kỳ: dùng cron / APScheduler gọi run_once() mỗi FORECAST_INTERVAL_MINUTES.
"""
import argparse
import os
from datetime import datetime, timedelta

import numpy as np
import requests
import tensorflow as tf

from fetch_data import fetch_readings
from preprocess import clean_data, resample_hourly, FEATURE_COLUMNS

BACKEND_API_BASE_URL = os.getenv("BACKEND_API_BASE_URL", "http://localhost:8000")
FORECAST_HORIZON_HOURS = int(os.getenv("FORECAST_HORIZON_HOURS", 24))
MODEL_PATH = os.getenv("MODEL_PATH", "model/lstm_model.keras")
WINDOW_SIZE = 24


def load_model():
    return tf.keras.models.load_model(MODEL_PATH)


def run_once(device_id: str):
    df = fetch_readings(device_id, limit=WINDOW_SIZE * 3)
    if df.empty or len(df) < WINDOW_SIZE:
        print(f"Chưa đủ dữ liệu để dự báo cho {device_id} (cần >= {WINDOW_SIZE} điểm).")
        return

    df = clean_data(df)
    df = resample_hourly(df)

    # TODO: dùng LẠI scaler đã fit lúc huấn luyện (lưu bằng joblib) thay vì fit mới,
    # để đảm bảo cùng phép scale giữa train và inference.
    from sklearn.preprocessing import MinMaxScaler
    scaler = MinMaxScaler()
    scaled = scaler.fit_transform(df[FEATURE_COLUMNS])

    window = scaled[-WINDOW_SIZE:]
    X = np.expand_dims(window, axis=0)  # shape (1, window_size, n_features)

    model = load_model()
    y_pred_scaled = model.predict(X)[0]  # shape (horizon,)

    # Giải chuẩn hoá riêng cho cột target (pm25) - đơn giản hoá bằng inverse trên
    # bản sao vector đủ số cột để dùng scaler.inverse_transform
    target_idx = FEATURE_COLUMNS.index("pm25")
    dummy = np.zeros((len(y_pred_scaled), len(FEATURE_COLUMNS)))
    dummy[:, target_idx] = y_pred_scaled
    y_pred = scaler.inverse_transform(dummy)[:, target_idx]

    now = datetime.utcnow()
    predictions = [
        {
            "timestamp": (now + timedelta(hours=i + 1)).isoformat(),
            "pm25": float(y_pred[i]),
            "aqi": None,  # TODO: tính AQI từ pm25 theo công thức chuẩn (EPA breakpoints)
        }
        for i in range(len(y_pred))
    ]

    payload = {
        "device_id": device_id,
        "generated_at": now.isoformat(),
        "horizon_hours": FORECAST_HORIZON_HOURS,
        "predictions": predictions,
    }

    resp = requests.post(f"{BACKEND_API_BASE_URL}/api/forecasts", json=payload, timeout=30)
    resp.raise_for_status()
    print(f"Đã gửi dự báo cho {device_id}: {len(predictions)} điểm.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--device_id", required=True)
    args = parser.parse_args()
    run_once(args.device_id)
