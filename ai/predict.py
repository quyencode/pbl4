"""
Service suy luận: định kỳ lấy dữ liệu gần nhất, chạy mô hình đã huấn luyện,
và gửi kết quả dự báo về Backend qua POST /api/forecasts.

Chạy thủ công: python predict.py --device_id node-01
Chạy định kỳ: dùng cron / APScheduler gọi run_once() mỗi FORECAST_INTERVAL_MINUTES.
"""
import argparse
import os
import pickle
from datetime import datetime, timedelta

import numpy as np
import requests
import tensorflow as tf

from fetch_data import fetch_readings
from preprocess import clean_data, resample_hourly

BACKEND_API_BASE_URL = os.getenv("BACKEND_API_BASE_URL", "http://localhost:8000")
FORECAST_HORIZON_HOURS = int(os.getenv("FORECAST_HORIZON_HOURS", 24))
# Cập nhật đường dẫn model khớp với thực tế đã lưu ở thư mục ai/data/
MODEL_PATH = os.getenv("MODEL_PATH", "ai/data/lstm_model.keras")
SCALER_PATH = os.getenv("SCALER_PATH", "ai/data/scaler.pkl")
WINDOW_SIZE = 24


def load_model():
    return tf.keras.models.load_model(MODEL_PATH)


def run_once(device_id: str):
    df = fetch_readings(device_id, limit=WINDOW_SIZE * 3)
    if df is None or df.empty or len(df) < WINDOW_SIZE:
        print(f"Chưa đủ dữ liệu để dự báo cho {device_id} (cần >= {WINDOW_SIZE} điểm).")
        return

    df = clean_data(df)
    df = resample_hourly(df)

    # Xác định các cột tính năng (feature columns) từ DataFrame số
    feature_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if not feature_cols:
        print("Không tìm thấy cột dữ liệu số nào để dự báo.")
        return

    # Sử dụng lại scaler đã fit lúc huấn luyện được lưu qua pickle/joblib
    if os.path.exists(SCALER_PATH):
        with open(SCALER_PATH, "rb") as f:
            scaler = pickle.load(f)
        scaled = scaler.transform(df[feature_cols])
    else:
        # Fallback nếu chưa lưu scaler (chỉ dùng tạm thời)
        print("Cảnh báo: Không tìm thấy scaler đã lưu, tiến hành fit_transform mới.")
        from sklearn.preprocessing import MinMaxScaler
        scaler = MinMaxScaler()
        scaled = scaler.fit_transform(df[feature_cols])

    window = scaled[-WINDOW_SIZE:]
    X = np.expand_dims(window, axis=0)  # shape (1, window_size, n_features)

    model = load_model()
    y_pred_scaled = model.predict(X)[0]  # shape (horizon,)

    # Giải chuẩn hoá riêng cho cột target (pm25 hoặc cột đầu tiên)
    target_col = 'pm25' if 'pm25' in feature_cols else feature_cols[0]
    target_idx = feature_cols.index(target_col)
    
    dummy = np.zeros((len(y_pred_scaled), len(feature_cols)))
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

    try:
        resp = requests.post(f"{BACKEND_API_BASE_URL}/api/forecasts", json=payload, timeout=30)
        resp.raise_for_status()
        print(f"Đã gửi dự báo cho {device_id}: {len(predictions)} điểm.")
    except requests.exceptions.RequestException as e:
        print(f"Lỗi khi gửi kết quả dự báo về Backend: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--device_id", required=True)
    args = parser.parse_args()
    run_once(args.device_id)