"""
Service suy luận: lấy dữ liệu gần nhất, chạy mô hình đã huấn luyện,
và gửi kết quả dự báo về Backend qua POST /api/forecasts.

Chạy thủ công (từ thư mục gốc repo): py -3.12 ai\\predict.py --device_id node-01
Chạy định kỳ: dùng cron / Task Scheduler gọi run_once() mỗi giờ.

Mô hình hiện tại (ai/data/lstm_model.keras, train bằng ai/src/experiments/train_draft.py)
là LSTM đơn biến: đầu vào 24 giờ PM2.5 -> đầu ra PM2.5 của 1 giờ tiếp theo.
Để có dự báo 24 giờ, predict.py chạy mô hình lặp 24 lần (dự báo giờ thứ 1,
đưa kết quả vào cuối cửa sổ, dự báo giờ thứ 2, ...).
"""
import argparse
import os
import pickle
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import requests
import tensorflow as tf
from sklearn.preprocessing import MinMaxScaler

from aqi import pm25_to_aqi
from fetch_data import fetch_readings
from preprocess import clean_data, resample_hourly

AI_DIR = os.path.dirname(os.path.abspath(__file__))

BACKEND_API_BASE_URL = os.getenv("BACKEND_API_BASE_URL", "http://localhost:8000")
FORECAST_HORIZON_HOURS = int(os.getenv("FORECAST_HORIZON_HOURS", 24))
# Đường dẫn tính theo thư mục ai/ nên chạy từ đâu cũng được
MODEL_PATH = os.getenv("MODEL_PATH", os.path.join(AI_DIR, "data", "lstm_model.keras"))
SCALER_PATH = os.getenv("SCALER_PATH", os.path.join(AI_DIR, "data", "scaler.pkl"))
# Dữ liệu mô hình đã được train -> fit lại scaler giống hệt lúc train nếu chưa lưu scaler.pkl
TRAINING_DATA_PATH = os.getenv("TRAINING_DATA_PATH", os.path.join(AI_DIR, "data", "mock_readings.csv"))
TARGET_COL = "pm25"
WINDOW_SIZE = 24  # số giờ lịch sử mô hình cần
# Số bản ghi thô lấy về: node gửi 5 phút/lần -> 24 giờ ~ 288 bản ghi, lấy dư để chắc đủ
FETCH_LIMIT = int(os.getenv("PREDICT_FETCH_LIMIT", 2000))


def load_model():
    return tf.keras.models.load_model(MODEL_PATH)


def load_scaler(recent_values: np.ndarray) -> MinMaxScaler:
    """Lấy scaler cho cột PM2.5, ưu tiên đúng scaler đã dùng lúc train."""
    if os.path.exists(SCALER_PATH):
        with open(SCALER_PATH, "rb") as f:
            scaler = pickle.load(f)
        if getattr(scaler, "n_features_in_", 1) == 1:
            return scaler
        print(f"Cảnh báo: {SCALER_PATH} được fit trên nhiều cột, không khớp mô hình đơn biến -> bỏ qua.")

    if os.path.exists(TRAINING_DATA_PATH):
        # Tái tạo đúng bước chuẩn hoá trong load_and_preprocess_data() lúc train
        df_train = resample_hourly(clean_data(pd.read_csv(TRAINING_DATA_PATH)))
        scaler = MinMaxScaler(feature_range=(0, 1))
        scaler.fit(df_train[[TARGET_COL]].values)
        return scaler

    print("Cảnh báo: không có scaler.pkl lẫn dữ liệu train, fit tạm scaler trên dữ liệu gần nhất.")
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaler.fit(recent_values.reshape(-1, 1))
    return scaler


def forecast_recursive(model, scaled_window: np.ndarray, horizon: int) -> np.ndarray:
    """Dự báo nhiều giờ bằng mô hình 1 bước: mỗi dự báo được nối vào cửa sổ cho bước sau."""
    window = scaled_window.reshape(-1).astype("float32").tolist()
    outputs = []
    for _ in range(horizon):
        x = np.array(window[-WINDOW_SIZE:], dtype="float32").reshape(1, WINDOW_SIZE, 1)
        next_value = float(model.predict(x, verbose=0).reshape(-1)[0])
        outputs.append(next_value)
        window.append(next_value)
    return np.array(outputs).reshape(-1, 1)


def run_once(device_id: str):
    df = fetch_readings(device_id, limit=FETCH_LIMIT)
    if df is None or df.empty or TARGET_COL not in df.columns or df[TARGET_COL].notna().sum() == 0:
        print(f"Chưa có dữ liệu PM2.5 nào cho {device_id}, bỏ qua lần dự báo này.")
        return

    df = clean_data(df)
    df = resample_hourly(df)
    if len(df) < WINDOW_SIZE:
        print(
            f"Chưa đủ dữ liệu để dự báo cho {device_id}: mới có {len(df)} giờ, "
            f"cần >= {WINDOW_SIZE} giờ liên tục."
        )
        return

    recent = df[TARGET_COL].values[-WINDOW_SIZE:].astype("float64")
    scaler = load_scaler(df[TARGET_COL].values)
    scaled_window = scaler.transform(recent.reshape(-1, 1))

    model = load_model()
    y_pred_scaled = forecast_recursive(model, scaled_window, FORECAST_HORIZON_HOURS)
    # Nồng độ bụi không thể âm
    y_pred = np.clip(scaler.inverse_transform(y_pred_scaled).reshape(-1), 0, None)

    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    predictions = [
        {
            "timestamp": (now + timedelta(hours=i + 1)).isoformat(),
            "pm25": round(float(value), 1),
            "aqi": pm25_to_aqi(float(value)),
        }
        for i, value in enumerate(y_pred)
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
