import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler

def load_and_preprocess_data(file_path):
    # Đọc dữ liệu từ file CSV mẫu
    df = pd.read_csv(file_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    
    # Lấy các cột giá trị cần dự báo (ví dụ: pm25)
    data = df[['pm25']].values
    
    # Chuẩn hóa dữ liệu về khoảng [0, 1]
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled_data = scaler.fit_transform(data)
    
    return df, scaled_data, scaler

if __name__ == "__main__":
    file_path = "ai/data/mock_readings.csv"
    df, scaled_data, scaler = load_and_preprocess_data(file_path)
    print("Tải và tiền xử lý dữ liệu thành công! Tổng số bản ghi:", len(df))