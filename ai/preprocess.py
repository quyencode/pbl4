import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler

def clean_data(df):
    """
    Task C2.1: Loại bỏ bản ghi thiếu giá trị mục tiêu (target/pm25 hoặc AQI), 
    nội suy các cột số còn thiếu.
    """
    target_col = 'pm25' if 'pm25' in df.columns else df.columns[-1]
    
    # 1. Loại bỏ các dòng bị thiếu giá trị target
    df = df.dropna(subset=[target_col])
    
    # 2. Nội suy (interpolate) các giá trị số bị thiếu trong các cột còn lại
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df[numeric_cols] = df[numeric_cols].interpolate(method='linear').bfill().ffill()
    
    return df

def resample_hourly(df, time_col='timestamp'):
    """
    Task C2.1: Đưa dữ liệu về tần suất 1 giờ/điểm bằng cách lấy trung bình theo giờ.
    """
    if time_col in df.columns:
        df[time_col] = pd.to_datetime(df[time_col])
        df = df.set_index(time_col)
    
    # Chỉ lấy các cột số để resample trung bình, tránh lỗi TypeError với cột chuỗi/object
    df_numeric = df.select_dtypes(include=[np.number])
    df_resampled = df_numeric.resample('h').mean()
    
    # Nội suy lấp đầy nếu có khoảng giờ bị trống sau khi resample
    df_resampled = df_resampled.interpolate(method='linear').bfill().ffill()
    
    # Đưa cột timestamp trở lại thành cột bình thường
    df_resampled = df_resampled.reset_index()
    return df_resampled

def load_and_preprocess_data(file_path):
    """
    Task C2.2: Pipeline tổng hợp để load, làm sạch, resample và chuẩn hóa dữ liệu.
    """
    # Đọc dữ liệu từ file CSV mock
    df = pd.read_csv(file_path)
    
    # Bước 1: Làm sạch dữ liệu
    df_cleaned = clean_data(df)
    
    # Bước 2: Resample về tần suất 1 giờ
    df_resampled = resample_hourly(df_cleaned)
    
    # Lấy cột giá trị để huấn luyện (ví dụ: cột pm25 hoặc cột số đầu tiên)
    target_col = 'pm25' if 'pm25' in df_resampled.columns else df_resampled.select_dtypes(include=[np.number]).columns[0]
    data = df_resampled[[target_col]].values
    
    # Bước 3: Chuẩn hóa dữ liệu về khoảng [0, 1] cho LSTM
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled_data = scaler.fit_transform(data)
    
    return df_resampled, scaled_data, scaler

def make_sliding_windows(data, window_size=24, horizon=1):
    """
    Task C3.2: Tạo cửa sổ trượt cho dữ liệu chuỗi thời gian.
    - data: Mảng numpy đã được scale.
    - window_size: Số bước thời gian lịch sử (ví dụ: 24 giờ).
    - horizon: Số bước thời gian cần dự báo trước.
    """
    if len(data.shape) == 1:
        data = data.reshape(-1, 1)
        
    X, y = [], []
    n_samples = len(data)
    
    for i in range(window_size, n_samples - horizon + 1):
        # Lấy đoạn lịch sử làm đầu vào X
        X.append(data[i - window_size:i])
        # Lấy đoạn tương lai làm nhãn y
        y.append(data[i:i + horizon, 0])
        
    X = np.array(X)
    y = np.array(y)
    
    return X, y

if __name__ == "__main__":
    # Task C2.2 & C3.2: Test thử pipeline và hàm tạo cửa sổ trượt
    file_path = "ai/data/mock_readings.csv"
    print("Đang kiểm tra pipeline trên:", file_path)
    
    df_resampled, scaled_data, scaler = load_and_preprocess_data(file_path)
    
    print("\n--- 5 Dòng đầu tiên sau khi xử lý (head) ---")
    print(df_resampled.head())
    
    print("\n--- Thống kê mô tả (describe) ---")
    print(df_resampled.describe())
    
    # Kiểm tra NaN
    nan_count = df_resampled.isna().sum().sum()
    print(f"\nTổng số giá trị NaN còn lại: {nan_count} (Yêu cầu: 0)")
    
    # Test nhanh make_sliding_windows
    X_test, y_test = make_sliding_windows(scaled_data, window_size=24, horizon=1)
    print(f"\nTest X shape: {X_test.shape} (Kỳ vọng: (n, 24, 1))")
    print(f"Test y shape: {y_test.shape} (Kỳ vọng: (n, 1))")