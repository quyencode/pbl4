"""
Tiền xử lý dữ liệu chuỗi thời gian: làm sạch, chuẩn hoá, tạo sliding window
để đưa vào mô hình LSTM/CNN-LSTM.
"""
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

FEATURE_COLUMNS = ["pm25", "pm10", "co2", "temperature", "humidity"]
TARGET_COLUMN = "pm25"  # đổi thành "aqi" nếu đã tính sẵn cột AQI


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Loại bản ghi thiếu target, nội suy tuyến tính các cột số còn thiếu."""
    df = df.copy()
    df = df.dropna(subset=[TARGET_COLUMN])
    df[FEATURE_COLUMNS] = df[FEATURE_COLUMNS].interpolate(limit_direction="both")
    return df


def resample_hourly(df: pd.DataFrame) -> pd.DataFrame:
    """Đưa dữ liệu về tần suất 1 giờ/điểm (trung bình) để đồng bộ nhịp dự báo."""
    df = df.set_index("timestamp")
    hourly = df[FEATURE_COLUMNS].resample("1H").mean()
    hourly = hourly.interpolate(limit_direction="both")
    return hourly.reset_index()


def make_sliding_windows(data: np.ndarray, window_size: int, horizon: int, target_idx: int):
    """
    Tạo tập (X, y) kiểu sliding window cho bài toán dự báo chuỗi thời gian.
    - window_size: số bước thời gian trong quá khứ dùng làm đầu vào
    - horizon: số bước thời gian cần dự báo (vd: 24 = dự báo 24h tới)
    - target_idx: chỉ số cột mục tiêu trong `data`
    """
    X, y = [], []
    for i in range(len(data) - window_size - horizon + 1):
        X.append(data[i : i + window_size])
        y.append(data[i + window_size : i + window_size + horizon, target_idx])
    return np.array(X), np.array(y)


def prepare_dataset(df: pd.DataFrame, window_size: int = 24, horizon: int = 24):
    """Pipeline đầy đủ: clean -> resample -> scale -> sliding window."""
    df = clean_data(df)
    df = resample_hourly(df)

    scaler = MinMaxScaler()
    scaled = scaler.fit_transform(df[FEATURE_COLUMNS])

    target_idx = FEATURE_COLUMNS.index(TARGET_COLUMN)
    X, y = make_sliding_windows(scaled, window_size, horizon, target_idx)

    n = len(X)
    train_end = int(n * 0.70)
    val_end = int(n * 0.85)

    splits = {
        "X_train": X[:train_end], "y_train": y[:train_end],
        "X_val": X[train_end:val_end], "y_val": y[train_end:val_end],
        "X_test": X[val_end:], "y_test": y[val_end:],
    }
    return splits, scaler


if __name__ == "__main__":
    df = pd.read_csv("data/readings.csv", parse_dates=["timestamp"])
    splits, scaler = prepare_dataset(df)
    for name, arr in splits.items():
        print(name, arr.shape)
