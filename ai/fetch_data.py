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
        params["from_"] = from_
    if to:
        params["to"] = to

    resp = requests.get(f"{BACKEND_API_BASE_URL}/api/readings", params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    df = pd.DataFrame(data["items"])
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp")
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--device_id", required=True)
    parser.add_argument("--from_", default=None)
    parser.add_argument("--to", default=None)
    parser.add_argument("--out", default="data/readings.csv")
    args = parser.parse_args()

    df = fetch_readings(args.device_id, args.from_, args.to)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    df.to_csv(args.out, index=False)
    print(f"Đã lưu {len(df)} bản ghi vào {args.out}")
