"""
Huấn luyện mô hình dự báo AQI/PM2.5 (LSTM / CNN-LSTM).
Chạy: python train_model.py --data data/readings.csv --epochs 50

Đánh giá bằng MAE / RMSE / MAPE, so sánh với baseline Persistence
(dự báo = giữ nguyên giá trị hiện tại) như trong slide 16 của đề tài.
"""
import argparse
import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow.keras import layers, models
from sklearn.metrics import mean_absolute_error, mean_squared_error

from preprocess import prepare_dataset, FEATURE_COLUMNS


def build_lstm_model(window_size: int, n_features: int, horizon: int) -> tf.keras.Model:
    model = models.Sequential([
        layers.Input(shape=(window_size, n_features)),
        layers.LSTM(64, return_sequences=True),
        layers.LSTM(32),
        layers.Dense(32, activation="relu"),
        layers.Dense(horizon),  # dự báo `horizon` bước liên tiếp
    ])
    model.compile(optimizer="adam", loss="mse", metrics=["mae"])
    return model


def build_cnn_lstm_model(window_size: int, n_features: int, horizon: int) -> tf.keras.Model:
    model = models.Sequential([
        layers.Input(shape=(window_size, n_features)),
        layers.Conv1D(filters=32, kernel_size=3, activation="relu", padding="causal"),
        layers.MaxPooling1D(pool_size=2),
        layers.LSTM(32),
        layers.Dense(32, activation="relu"),
        layers.Dense(horizon),
    ])
    model.compile(optimizer="adam", loss="mse", metrics=["mae"])
    return model


def evaluate(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mape = np.mean(np.abs((y_true - y_pred) / np.clip(np.abs(y_true), 1e-6, None))) * 100
    return {"MAE": mae, "RMSE": rmse, "MAPE": mape}


def persistence_baseline(X_test: np.ndarray, horizon: int, target_idx: int) -> np.ndarray:
    """Baseline đơn giản: dự báo = giá trị đo gần nhất, lặp lại cho cả horizon."""
    last_values = X_test[:, -1, target_idx]
    return np.repeat(last_values[:, None], horizon, axis=1)


def main(data_path: str, window_size: int, horizon: int, epochs: int, model_type: str):
    df = pd.read_csv(data_path, parse_dates=["timestamp"])
    splits, scaler = prepare_dataset(df, window_size=window_size, horizon=horizon)

    n_features = len(FEATURE_COLUMNS)
    target_idx = FEATURE_COLUMNS.index("pm25")

    if model_type == "cnn_lstm":
        model = build_cnn_lstm_model(window_size, n_features, horizon)
    else:
        model = build_lstm_model(window_size, n_features, horizon)

    early_stop = tf.keras.callbacks.EarlyStopping(patience=5, restore_best_weights=True)

    model.fit(
        splits["X_train"], splits["y_train"],
        validation_data=(splits["X_val"], splits["y_val"]),
        epochs=epochs, batch_size=32, callbacks=[early_stop], verbose=1,
    )

    y_pred = model.predict(splits["X_test"])
    metrics_model = evaluate(splits["y_test"], y_pred)

    y_baseline = persistence_baseline(splits["X_test"], horizon, target_idx)
    metrics_baseline = evaluate(splits["y_test"], y_baseline)

    print("\n=== Kết quả đánh giá trên tập Test ===")
    print(f"{model_type}:  ", metrics_model)
    print("Baseline (Persistence):", metrics_baseline)

    import os
    os.makedirs("model", exist_ok=True)
    model.save(f"model/{model_type}_model.keras")
    print(f"\nĐã lưu mô hình vào model/{model_type}_model.keras")
    print("-> Cập nhật kết quả MAE/RMSE/MAPE vào ai/MODEL_CARD.md")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/readings.csv")
    parser.add_argument("--window_size", type=int, default=24)
    parser.add_argument("--horizon", type=int, default=24)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--model_type", choices=["lstm", "cnn_lstm"], default="lstm")
    args = parser.parse_args()

    main(args.data, args.window_size, args.horizon, args.epochs, args.model_type)
