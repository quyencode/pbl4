"""
MQTT Subscriber - nhận dữ liệu từ các node cảm biến và ghi vào InfluxDB.
Chạy độc lập (process riêng) hoặc gọi start_mqtt_listener() lúc khởi động FastAPI.

Topic subscribe: sensors/+/data  (dấu '+' khớp mọi device_id)
"""
import json
import os
import logging
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mqtt_subscriber")

MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", 1883))
MQTT_TOPIC = os.getenv("MQTT_TOPIC_PREFIX", "sensors") + "/+/data"

INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "devtoken12345")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "pbl4")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "air_quality")

_influx_client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
_write_api = _influx_client.write_api(write_options=SYNCHRONOUS)


def validate_payload(data: dict) -> bool:
    """Kiểm tra tối thiểu dữ liệu hợp lệ trước khi ghi DB - TODO: mở rộng theo nhu cầu."""
    if "device_id" not in data:
        return False
    numeric_fields = ["pm25", "pm10", "co2", "temperature", "humidity"]
    return any(field in data and data[field] is not None for field in numeric_fields)


def write_to_influx(data: dict) -> None:
    point = Point("air_quality").tag("device_id", data["device_id"])

    for field in ["pm25", "pm10", "co2", "temperature", "humidity"]:
        if data.get(field) is not None:
            point = point.field(field, float(data[field]))

    ts = data.get("timestamp")
    if ts:
        try:
            point = point.time(datetime.fromisoformat(ts.replace("Z", "+00:00")))
        except ValueError:
            point = point.time(datetime.now(timezone.utc))
    else:
        point = point.time(datetime.now(timezone.utc))

    _write_api.write(bucket=INFLUXDB_BUCKET, record=point)


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info("Đã kết nối MQTT broker, subscribe topic: %s", MQTT_TOPIC)
        client.subscribe(MQTT_TOPIC, qos=1)
    else:
        logger.error("Kết nối MQTT thất bại, mã lỗi: %s", rc)


def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
    except json.JSONDecodeError:
        logger.warning("Payload không phải JSON hợp lệ: %s", msg.payload)
        return

    if not validate_payload(data):
        logger.warning("Payload thiếu dữ liệu bắt buộc: %s", data)
        return

    try:
        write_to_influx(data)
        logger.info("Đã ghi dữ liệu node %s vào InfluxDB", data["device_id"])
        # TODO: kiểm tra ngưỡng cảnh báo (alert_configs trong PostgreSQL) và
        # tạo alert_event / gửi qua WebSocket nếu vượt ngưỡng.
    except Exception:
        logger.exception("Lỗi khi ghi dữ liệu vào InfluxDB")


def start_mqtt_listener() -> mqtt.Client:
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, keepalive=60)
    client.loop_start()  # chạy nền, không block
    return client


if __name__ == "__main__":
    client = start_mqtt_listener()
    logger.info("MQTT subscriber đang chạy... Ctrl+C để dừng.")
    try:
        while True:
            pass
    except KeyboardInterrupt:
        client.loop_stop()
