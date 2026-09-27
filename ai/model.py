import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.callbacks import EarlyStopping

def create_sequences(scaled_data, seq_length=24):
    """
    Task C2.3: Tạo các chuỗi dữ liệu (X, y) cho mô hình LSTM.
    - seq_length: Số bước thời gian lịch sử dùng để dự báo (mặc định 24 giờ qua).
    """
    X, y = [], []
    for i in range(seq_length, len(scaled_data)):
        X.append(scaled_data[i - seq_length:i, 0])
        y.append(scaled_data[i, 0])
        
    X = np.array(X)
    y = np.array(y)
    
    # Reshape X thành dạng 3D cho LSTM: [samples, time_steps, features]
    X = np.reshape(X, (X.shape[0], X.shape[1], 1))
    return X, y

def build_lstm_model(seq_length=1):
    """
    Task C2.4: Xây dựng kiến trúc mô hình LSTM.
    """
    model = Sequential([
        LSTM(50, return_sequences=True, input_shape=(seq_length, 1)),
        Dropout(0.2),
        LSTM(50, return_sequences=False),
        Dropout(0.2),
        Dense(25),
        Dense(1)
    ])
    
    model.compile(optimizer='adam', loss='mean_squared_error')
    return model

if __name__ == "__main__":
    # Test thử việc tạo sequence và compile mô hình từ dữ liệu tiền xử lý
    from preprocess import load_and_preprocess_data
    
    file_path = "ai/data/mock_readings.csv"
    _, scaled_data, _ = load_and_preprocess_data(file_path)
    
    SEQ_LENGTH = 24
    X, y = create_sequences(scaled_data, seq_length=SEQ_LENGTH)
    print(f"Kích thước tập X train: {X.shape}")
    print(f"Kích thước tập y train: {y.shape}")
    
    model = build_lstm_model(seq_length=SEQ_LENGTH)
    model.summary()