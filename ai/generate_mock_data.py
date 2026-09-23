"""
Sinh dữ liệu cảm biến giả lập (mock) cho khối AI - Task C1.1, Tuần 1.
Tạo 30 ngày dữ liệu, tần suất 1 điểm/giờ (720 điểm), có dao động ngày/đêm
hợp lý cho từng thông số, đúng cột theo iot/mqtt_data_contract.md.

Chạy: python generate_mock_data.py
Kết quả: mock_readings.csv
"""
import csv
import math
import random
from datetime import datetime, timedelta

random.seed(42)  # để kết quả tái lập được, ai chạy lại cũng ra cùng dữ liệu

N_DAYS = 30
START = datetime(2026, 8, 24, 0, 0, 0)
DEVICE_ID = "node-01"


def pm25_at(hour_of_day: float, day_factor: float) -> float:
    """PM2.5 cao hơn vào giờ cao điểm sáng/tối (giao thông), thấp về đêm khuya/trưa."""
    base = 28
    rush_hour = 18 * (math.exp(-((hour_of_day - 7) ** 2) / 6) + math.exp(-((hour_of_day - 19) ** 2) / 8))
    noise = random.gauss(0, 4)
    return max(5, base + rush_hour + day_factor + noise)


def co2_at(hour_of_day: float) -> int:
    """CO2 cao hơn ban đêm/sáng sớm (ít gió, hoạt động hô hấp tích tụ trong phòng kín)."""
    base = 480
    night_bump = 90 * math.exp(-((hour_of_day - 4) ** 2) / 10)
    noise = random.gauss(0, 15)
    return int(max(400, base + night_bump + noise))


def temp_at(hour_of_day: float, day_factor: float) -> float:
    """Nhiệt độ thấp nhất ~5h sáng, cao nhất ~14h chiều - dao động hình sin."""
    base = 27.5
    swing = 4.5 * math.sin((hour_of_day - 9) / 24 * 2 * math.pi)
    noise = random.gauss(0, 0.4)
    return round(base + swing + day_factor * 0.3 + noise, 1)


def humidity_at(hour_of_day: float) -> float:
    """Độ ẩm ngược pha với nhiệt độ - cao về đêm/sáng sớm, thấp buổi trưa."""
    base = 72
    swing = -12 * math.sin((hour_of_day - 9) / 24 * 2 * math.pi)
    noise = random.gauss(0, 2)
    return round(max(30, min(95, base + swing + noise)), 1)


def main():
    rows = []
    for day in range(N_DAYS):
        # mỗi vài ngày có 1-2 ngày ô nhiễm hơn hẳn (mô phỏng thời tiết đứng gió, nghịch nhiệt)
        day_factor = 12 if day % 7 in (2, 3) else random.uniform(-3, 3)

        for hour in range(24):
            ts = START + timedelta(days=day, hours=hour)
            pm25 = round(pm25_at(hour, day_factor), 1)
            pm10 = round(pm25 * random.uniform(1.4, 1.7), 1)  # PM10 luôn > PM2.5, tỉ lệ thực tế thường gặp
            co2 = co2_at(hour)
            temp = temp_at(hour, day_factor)
            hum = humidity_at(hour)

            # ~1.5% khả năng thiếu 1 giá trị ngẫu nhiên, mô phỏng lỗi đọc cảm biến thật
            if random.random() < 0.015:
                pm25 = ""
            if random.random() < 0.01:
                co2 = ""

            rows.append({
                "device_id": DEVICE_ID,
                "pm25": pm25,
                "pm10": pm10,
                "co2": co2,
                "temperature": temp,
                "humidity": hum,
                "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%S"),
            })

    with open("mock_readings.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["device_id", "pm25", "pm10", "co2", "temperature", "humidity", "timestamp"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Đã sinh {len(rows)} bản ghi ({N_DAYS} ngày x 24 giờ), lưu vào mock_readings.csv")


if __name__ == "__main__":
    main()
