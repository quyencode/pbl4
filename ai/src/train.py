import numpy as np
import pandas as pd
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense
from preprocess import load_and_preprocess_data

def create_dataset(dataset, look_back=24):
    X, Y = [], []
    for i in range(len(dataset) - look_back):
        a = dataset[i:(i + look_back), 0]
        X.append(a)
        Y.append(dataset[i + look_back, 0])
    return np.array(X), np.array(Y)

def train_model():
    file_path = "ai/data/mock_readings.csv"
    _, scaled_data, scaler = load_and_preprocess_data(file_path)
    
    # Xử lý an toàn phòng trường hợp dữ liệu có giá trị NaN gây lỗi loss: nan
    scaled_data = np.nan_to_num(scaled_data)
    
    # Sử dụng 24 giờ trước để dự báo giờ tiếp theo
    look_back = 24
    X, y = create_dataset(scaled_data, look_back)
    
    # Reshape lại dữ liệu cho phù hợp với đầu vào của LSTM [samples, time steps, features]
    X = np.reshape(X, (X.shape[0], X.shape[1], 1))
    
    # Xây dựng mô hình LSTM đơn giản
    model = Sequential()
    model.add(LSTM(50, input_shape=(look_back, 1)))
    model.add(Dense(1))
    
    # Compile mô hình riêng biệt
    model.compile(loss='mean_squared_error', optimizer='adam')
    
    print("Đang huấn luyện mô hình LSTM...")
    model.fit(X, y, epochs=10, batch_size=16, verbose=1)
    
    # Lưu mô hình theo định dạng chuẩn .keras mới
    model.save("ai/data/lstm_model.keras")
    print("Huấn luyện và lưu mô hình thành công tại ai/data/lstm_model.keras!")

if __name__ == "__main__":
    train_model()