"""Subscribe to sensor readings and persist valid messages in InfluxDB."""
from __future__ import annotations

import json
import logging
import math
import os
from datetime import datetime, timezone
from threading import Event
from typing import Any

import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

logger = logging.getLogger(__name__)

MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
MQTT_TOPIC_PREFIX = os.getenv("MQTT_TOPIC_PREFIX", "sensors").strip("/")
MQTT_TOPIC = f"{MQTT_TOPIC_PREFIX}/+/data"

INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "devtoken12345")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "pbl4")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "air_quality")

SENSOR_FIELDS = ("pm25", "pm10", "co2", "temperature", "humidity")
FLOAT_FIELDS = ("pm25", "pm10", "temperature", "humidity")

_influx_client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
_write_api = _influx_client.write_api(write_options=SYNCHRONOUS)


def _parse_timestamp(value: Any) -> datetime | None:
    """Parse contract timestamps; naive ISO-8601 values are treated as UTC."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("timestamp must be an ISO-8601 string")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _is_finite_number(value: int | float) -> bool:
    try:
        return math.isfinite(value)
    except (OverflowError, TypeError):
        return False


def validate_payload(data: Any) -> bool:
    """Validate the required device identifier and any supplied contract fields."""
    if not isinstance(data, dict):
        return False

    device_id = data.get("device_id")
    if not isinstance(device_id, str) or not device_id.strip():
        return False

    for field in FLOAT_FIELDS:
        value = data.get(field)
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not _is_finite_number(value)
        ):
            return False

    co2 = data.get("co2")
    if co2 is not None and (isinstance(co2, bool) or not isinstance(co2, int)):
        return False

    try:
        _parse_timestamp(data.get("timestamp"))
    except (TypeError, ValueError, OverflowError):
        return False
    return True


def write_to_influx(data: dict[str, Any]) -> None:
    """Write one contract reading; raise on invalid data or InfluxDB errors."""
    if not validate_payload(data):
        raise ValueError("payload does not match the sensor data contract")

    fields = {name: data.get(name) for name in SENSOR_FIELDS if data.get(name) is not None}
    if not fields:
        raise ValueError("payload has no non-null sensor values to store")

    point = Point("air_quality").tag("device_id", data["device_id"].strip())
    for name, value in fields.items():
        point = point.field(name, value)

    timestamp = _parse_timestamp(data.get("timestamp"))
    point = point.time(timestamp or datetime.now(timezone.utc))
    _write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=point)


def on_connect(client: mqtt.Client, userdata: Any, flags: Any, rc: int) -> None:
    if rc == 0:
        result, _mid = client.subscribe(MQTT_TOPIC, qos=1)
        if result == mqtt.MQTT_ERR_SUCCESS:
            logger.info("Connected to MQTT broker; subscribed to %s", MQTT_TOPIC)
        else:
            logger.error("Could not subscribe to %s (MQTT error %s)", MQTT_TOPIC, result)
    else:
        logger.error("MQTT connection failed (return code %s)", rc)


def on_disconnect(client: mqtt.Client, userdata: Any, rc: int) -> None:
    if rc == 0:
        logger.info("Disconnected cleanly from MQTT broker")
    else:
        logger.warning("Unexpected MQTT disconnect (return code %s); reconnecting", rc)


def on_message(client: mqtt.Client, userdata: Any, msg: Any) -> None:
    try:
        data = json.loads(msg.payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        logger.warning("Ignoring non-JSON MQTT payload on %s: %r", msg.topic, msg.payload)
        return

    if not validate_payload(data):
        logger.warning("Ignoring invalid sensor payload on %s: %r", msg.topic, data)
        return

    topic_parts = msg.topic.split("/")
    if len(topic_parts) == 3 and topic_parts[0] == MQTT_TOPIC_PREFIX and topic_parts[2] == "data":
        topic_device_id = topic_parts[1]
        if data["device_id"].strip() != topic_device_id:
            logger.warning(
                "Ignoring payload whose device_id %r does not match topic device %r",
                data["device_id"],
                topic_device_id,
            )
            return

    if not any(data.get(field) is not None for field in SENSOR_FIELDS):
        logger.warning("Ignoring sensor payload without sensor values on %s", msg.topic)
        return

    try:
        write_to_influx(data)
    except Exception:
        logger.exception("Failed to write sensor payload from %s to InfluxDB", data["device_id"])
        return
    logger.info("Stored sensor reading for %s", data["device_id"])


def start_mqtt_listener() -> mqtt.Client:
    """Connect and start the MQTT network loop in the background."""
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.connect_async(MQTT_BROKER_HOST, MQTT_BROKER_PORT, keepalive=60)
    client.loop_start()
    return client


def stop_mqtt_listener(client: mqtt.Client | None) -> None:
    """Stop the MQTT network loop and release the shared InfluxDB resources."""
    if client is not None:
        client.loop_stop()
        client.disconnect()
    _write_api.close()
    _influx_client.close()


if __name__ == "__main__":
    listener = start_mqtt_listener()
    logger.info("MQTT subscriber running on %s:%s; press Ctrl+C to stop", MQTT_BROKER_HOST, MQTT_BROKER_PORT)
    try:
        Event().wait()
    except KeyboardInterrupt:
        logger.info("Stopping MQTT subscriber")
    finally:
        listener.loop_stop()
        listener.disconnect()
        _influx_client.close()
