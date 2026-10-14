"""
Giả lập node ESP32 gửi dữ liệu qua MQTT - dùng để TEST/DEMO toàn bộ đường ống
MQTT -> Backend -> InfluxDB -> Dashboard -> AI khi node thật chưa sẵn sàng.

Gửi đúng topic "sensors/<device_id>/data" và đúng định dạng payload như node thật,
nên Backend xử lý y hệt (xem iot/mqtt_data_contract.md).

Cần chạy trước: docker compose up -d  +  Backend (uvicorn).

Cách dùng (từ thư mục gốc repo):
  1) Nạp nhanh lịch sử 48 giờ GẦN NHẤT (để Dashboard có biểu đồ và predict.py đủ dữ liệu):
       py -3.12 ai\\publish_mock_to_mqtt.py
  2) Giả lập node đang chạy: cứ 10 giây gửi 1 bản ghi mới (Dashboard tự cập nhật):
       py -3.12 ai\\publish_mock_to_mqtt.py --live
  3) Làm cả hai: nạp lịch sử rồi chạy live luôn:
       py -3.12 ai\\publish_mock_to_mqtt.py --hours 48 --live

LƯU Ý: dữ liệu này là GIẢ LẬP. Nếu node thật của Đạt cũng gửi với device_id
"node-01" thì hai nguồn sẽ lẫn vào nhau - khi đó dùng --device_id node-sim.
"""
import argparse
import json
import math
import os
import random
import time
from datetime import datetime, timedelta, timezone

import paho.mqtt.client as mqtt

MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
MQTT_TOPIC_PREFIX = os.getenv("MQTT_TOPIC_PREFIX", "sensors").strip("/")


def simulate_reading(device_id: str, ts: datetime) -> dict:
    """Sinh 1 bản ghi có quy luật theo giờ trong ngày (giờ Việt Nam), giống generate_mock_data.py."""
    hour = (ts.astimezone(timezone(timedelta(hours=7))).hour
            + ts.astimezone(timezone(timedelta(hours=7))).minute / 60)
    rush = math.exp(-((hour - 8) ** 2) / 3) + math.exp(-((hour - 18) ** 2) / 3)  # giờ cao điểm
    pm25 = max(3.0, 22 + 25 * rush + random.gauss(0, 3))
    pm10 = pm25 * random.uniform(1.4, 1.7)
    co2 = int(450 + 120 * math.exp(-((hour - 21) ** 2) / 8) + random.gauss(0, 15))
    temperature = 28 + 4 * math.sin((hour - 9) / 24 * 2 * math.pi) + random.gauss(0, 0.3)
    humidity = 72 - 12 * math.sin((hour - 9) / 24 * 2 * math.pi) + random.gauss(0, 1)
    return {
        "device_id": device_id,
        "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pm25": round(pm25, 1),
        "pm10": round(pm10, 1),
        "co2": co2,
        "temperature": round(temperature, 1),
        "humidity": round(humidity, 1),
    }


def connect() -> mqtt.Client:
    client = mqtt.Client()
    client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, keepalive=30)
    client.loop_start()
    return client


def publish(client: mqtt.Client, payload: dict) -> None:
    topic = f"{MQTT_TOPIC_PREFIX}/{payload['device_id']}/data"
    client.publish(topic, json.dumps(payload), qos=1).wait_for_publish()


def backfill(client: mqtt.Client, device_id: str, hours: int, step_minutes: int) -> None:
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    start = now - timedelta(hours=hours)
    total = hours * 60 // step_minutes
    for i in range(total):
        publish(client, simulate_reading(device_id, start + timedelta(minutes=step_minutes * (i + 1))))
        if (i + 1) % 100 == 0:
            print(f"  Đã gửi {i + 1}/{total} bản ghi lịch sử...")
        time.sleep(0.01)
    print(f"Xong: đã nạp {total} bản ghi ({hours} giờ gần nhất, {step_minutes} phút/bản ghi) cho {device_id}.")


def live(client: mqtt.Client, device_id: str, interval: float) -> None:
    print(f"Đang giả lập node {device_id}: gửi 1 bản ghi mỗi {interval:g} giây. Ctrl+C để dừng.")
    while True:
        payload = simulate_reading(device_id, datetime.now(timezone.utc))
        publish(client, payload)
        print(f"  {payload['timestamp']}  PM2.5={payload['pm25']}  T={payload['temperature']}  H={payload['humidity']}")
        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="Giả lập node cảm biến gửi MQTT")
    parser.add_argument("--device_id", default="node-01")
    parser.add_argument("--hours", type=int, default=None,
                        help="Số giờ lịch sử cần nạp (mặc định 48 nếu không dùng --live)")
    parser.add_argument("--step_minutes", type=int, default=5, help="Khoảng cách giữa 2 bản ghi lịch sử")
    parser.add_argument("--live", action="store_true", help="Gửi liên tục bản ghi mới theo thời gian thực")
    parser.add_argument("--interval", type=float, default=10, help="Số giây giữa 2 lần gửi ở chế độ --live")
    args = parser.parse_args()

    hours = args.hours if args.hours is not None else (0 if args.live else 48)

    client = connect()
    try:
        if hours > 0:
            backfill(client, args.device_id, hours, args.step_minutes)
        if args.live:
            live(client, args.device_id, args.interval)
    except KeyboardInterrupt:
        print("\nĐã dừng giả lập.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
