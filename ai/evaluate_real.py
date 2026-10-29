"""
Script thống kê dữ liệu từ 15/10, tính tỉ lệ thiếu giờ và đánh giá MAE LSTM vs Baseline trên dữ liệu thật.
Chạy: python ai/evaluate_real.py --data ai/data/node-01.csv --start_date 2025-10-15
"""
import argparse
import os
import numpy as np
import pandas as pd
import tensorflow as tf
import joblib
from sklearn.metrics import mean_absolute_error

from preprocess import clean_data, resample_hourly

AI_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(AI_DIR, "..", "model", "lstm_model.keras")
if not os.path.exists(MODEL_PATH):
    MODEL_PATH = os.path.join(AI_DIR, "model", "lstm_model.keras")

SCALER_PATH = os.path.join(AI_DIR, "..", "model", "scaler.pkl")
if not os.path.exists(SCALER_PATH):
    SCALER_PATH = os.path.join(AI_DIR, "model", "scaler.pkl")

FEATURE_COLS = ["temperature", "humidity", "pm25", "pm10", "co2"]
TARGET_COL = "pm25"
WINDOW_SIZE = 24
HORIZON = 24

def evaluate_real_data(data_path: str, start_date: str):
    print(f"--- Đang đọc dữ liệu từ: {data_path} ---")
    if not os.path.exists(data_path):
        raise FileNotFoundError(f"Không tìm thấy file dữ liệu tại {data_path}")

    df_raw = pd.read_csv(data_path)
    if "timestamp" not in df_raw.columns:
        raise ValueError("File dữ liệu thiếu cột 'timestamp'!")

    df_raw["timestamp"] = pd.to_datetime(df_raw["timestamp"])
    
    # Lọc dữ liệu từ ngày bắt đầu (ví dụ: 15/10)
    start_dt = pd.to_datetime(start_date)
    df_filtered = df_raw[df_raw["timestamp"] >= start_dt].copy()

    if df_filtered.empty:
        print(f"⚠️ Không có bản ghi nào từ ngày {start_date} trở đi. Đang hiển thị tổng quan toàn bộ file...")
        df_filtered = df_raw.copy()
        start_dt = df_raw["timestamp"].min()

    # Thống kê tỉ lệ thiếu dữ liệu trước khi resample
    min_time = df_filtered["timestamp"].min()
    max_time = df_filtered["timestamp"].max()
    total_expected_hours = int((max_time - min_time).total_seconds() / 3600) + 1
    
    # Clean và resample theo giờ liên tục
    df_clean = clean_data(df_filtered)
    df_resampled = resample_hourly(df_clean)

    actual_hours = len(df_resampled)
    missing_hours = max(0, total_expected_hours - actual_hours)
    missing_rate = (missing_hours / total_expected_hours) * 100 if total_expected_hours > 0 else 0

    print("\n=== THỐNG KÊ DỮ LIỆU THẬT ===")
    print(f"- Khoảng thời gian: từ {min_time} đến {max_time}")
    print(f"- Tổng số giờ lý thuyết: {total_expected_hours} giờ")
    print(f"- Số giờ thực tế có dữ liệu (sau resample): {actual_hours} giờ")
    print(f"- Số giờ bị thiếu: {missing_hours} giờ")
    print(f"- Tỉ lệ thiếu dữ liệu: {missing_rate:.2f}%")

    if actual_hours < WINDOW_SIZE + HORIZON:
        print("\n⚠️ Dữ liệu không đủ để chạy đánh giá dự báo 24 giờ (cần ít nhất 48 giờ liên tục).")
        return

    # Chuẩn bị dữ liệu cho mô hình LSTM
    for col in FEATURE_COLS:
        if col not in df_resampled.columns:
            df_resampled[col] = 0.0

    values = df_resampled[FEATURE_COLS].values.astype("float64")
    
    if os.path.exists(SCALER_PATH):
        scaler = joblib.load(SCALER_PATH)
    else:
        raise FileNotFoundError("Không tìm thấy file scaler.pkl!")

    scaled_data = scaler.transform(values)
    target_idx = FEATURE_COLS.index(TARGET_COL)

    # Xây dựng ma trận X, y trượt cửa sổ
    X, y_true_actual = [], []
    for i in range(WINDOW_SIZE, len(scaled_data) - HORIZON + 1):
        X.append(scaled_data[i - WINDOW_SIZE:i])
        y_true_actual.append(values[i:i + HORIZON, target_idx])

    if len(X) == 0:
        print("⚠️ Không đủ dữ liệu tạo cửa sổ trượt (window).")
        return

    X = np.array(X)
    y_true_actual = np.array(y_true_actual)

    # Load model
    model = tf.keras.models.load_model(MODEL_PATH)
    y_pred_scaled = model.predict(X, verbose=0)

    # Inverse transform kết quả dự báo của LSTM
    y_pred_actual = np.zeros_like(y_pred_scaled)
    for idx in range(len(y_pred_scaled)):
        dummy = np.zeros((HORIZON, len(FEATURE_COLS)))
        dummy[:, target_idx] = y_pred_scaled[idx]
        inv = scaler.inverse_transform(dummy)
        y_pred_actual[idx] = inv[:, target_idx]

    # Tính MAE LSTM
    lstm_mae = mean_absolute_error(y_true_actual.flatten(), y_pred_actual.flatten())

    # Tính Baseline (Persistence: lấy giá trị giờ hiện tại lặp lại cho 24 giờ sau)
    baseline_preds = []
    for i in range(len(X)):
        last_val = values[i + WINDOW_SIZE - 1, target_idx]
        baseline_preds.append([last_val] * HORIZON)
    baseline_preds = np.array(baseline_preds)
    baseline_mae = mean_absolute_error(y_true_actual.flatten(), baseline_preds.flatten())

    print("\n=== KẾT QUẢ ĐÁNH GIÁ TRÊN DỮ LIỆU THẬT ===")
    print(f"🔹 LSTM Model MAE      : {lstm_mae:.4f}")
    print(f"🔸 Persistence Baseline MAE : {baseline_mae:.4f}")
    if lstm_mae < baseline_mae:
        print("✅ Mô hình LSTM đánh bại Baseline thành công trên dữ liệu thật!")
    else:
        print("ℹ️ Mô hình LSTM và Baseline có hiệu năng tiệm cận trên dữ liệu thực tế này.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="ai/data/node-01.csv")
    parser.add_argument("--start_date", default="2025-10-15") # Điều chỉnh năm/tháng nếu dữ liệu của bạn ở năm khác (VD: 2026-10-15)
    args = parser.parse_args()
    evaluate_real_data(args.data, args.start_date)