"""
Lấy dữ liệu lịch sử từ Backend API (GET /api/readings) để phục vụ huấn luyện.
Chạy: python fetch_data.py --device_id node-01 --out data/node-01.csv
"""
import argparse
import os
import requests
import pandas as pd

BACKEND_API_BASE_URL = os.getenv("BACKEND_API_BASE_URL", "http://localhost:8000")


def fetch_readings(device_id: str, from_: str = None, to: str = None, limit: int = 5000) -> pd.DataFrame:
    params = {"device_id": device_id, "limit": limit}
    if from_:
        params["from"] = from_  # Backend nhận tham số tên "from"
    if to:
        params["to"] = to

    try:
        # Cố gắng lấy dữ liệu từ Backend API
        resp = requests.get(f"{BACKEND_API_BASE_URL}/api/readings", params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        
        # Xử lý cấu trúc dữ liệu trả về từ API
        items = data["items"] if isinstance(data, dict) and "items" in data else data
        df = pd.DataFrame(items)
    except Exception as e:
        print(f"[Fallback] Không thể kết nối Backend API ({e}), đang chuyển sang đọc file CSV cục bộ...")
        
        # Đường dẫn dự phòng đọc từ thư mục data local
        local_path = os.path.join(os.path.dirname(__file__), "data", f"{device_id}.csv")
        if not os.path.exists(local_path):
            local_path = os.path.join(os.path.dirname(__file__), "data", "node-01.csv")
            
        if os.path.exists(local_path):
            df = pd.read_csv(local_path)
        else:
            raise FileNotFoundError(f"Không tìm thấy file dữ liệu cục bộ cho thiết bị {device_id} tại {local_path}")

    if not df.empty and "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp")
        
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--device_id", required=True)
    parser.add_argument("--from_", default=None)
    parser.add_argument("--to", default=None)
    parser.add_argument("--out", default="data/node-01.csv")
    args = parser.parse_args()

    df = fetch_readings(args.device_id, args.from_, args.to)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    df.to_csv(args.out, index=False)
    print(f"Đã lưu {len(df)} bản ghi vào {args.out}")