import os
import pandas as pd

file_path = "ai/data/node-01.csv"

if not os.path.exists(file_path):
    print(f"Lỗi: Không tìm thấy file dữ liệu tại {file_path}. Hãy tạo file CSV trước!")
else:
    df = pd.read_csv(file_path)
    print("=== 1. THÔNG TIN TỔNG QUAN DỮ LIỆU ===")
    print(df.info())
    
    print("\n=== 2. KIỂM TRA TỶ LỆ THIẾU (NaN) ===")
    missing_rate = df.isnull().mean() * 100
    print(missing_rate)
    
    print("\n=== 3. KIỂM TRA OUTLIER (PHÂN BIỆT THẬT & MÔ PHỎNG) ===")
    # Nhóm số đo thật: temperature, humidity, pm25, pm10
    # Nhóm mô phỏng: co2
    columns_to_check = ['temperature', 'humidity', 'pm25', 'pm10', 'co2']
    for col in columns_to_check:
        if col in df.columns:
            min_val = df[col].min()
            max_val = df[col].max()
            mean_val = df[col].mean()
            print(f"- Cột [{col}]: Min = {min_val:.2f}, Max = {max_val:.2f}, Mean = {mean_val:.2f}")