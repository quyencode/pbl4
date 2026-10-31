"""
Backend API - PBL4 Giám sát & Dự báo Chất lượng Không khí
Chạy dev: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
Tài liệu API tự sinh tại: http://localhost:8000/docs

Các endpoint dưới đây khớp với iot/mqtt_data_contract.md - KHÔNG đổi
định dạng field mà không cập nhật lại contract và báo cả nhóm.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from influxdb_client import InfluxDBClient

from app.schemas import (
    SensorReading,
    ReadingsResponse,
    LatestReadingsResponse,
    ForecastSubmission,
    AlertConfig,
)
from app.mqtt_subscriber import (
    INFLUXDB_BUCKET,
    INFLUXDB_ORG,
    INFLUXDB_TOKEN,
    INFLUXDB_URL,
    _parse_timestamp,
    set_reading_listener,
    set_alert_listener,
    stop_mqtt_listener,
    start_mqtt_listener,
)
from app.aqi import pm25_to_aqi
from app import postgres_db

# Hiện log INFO của app (vd "Stored sensor reading for node-01", "Connected to MQTT broker") trong cửa sổ uvicorn
logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s - %(message)s")
logger = logging.getLogger(__name__)
_influx_client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
_mqtt_client = None

app = FastAPI(title="PBL4 Air Quality API", version="0.1.0")

# Cho phép Frontend (chạy port khác, ví dụ Vite 5173) gọi API khi dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: giới hạn lại domain thật khi deploy
    allow_methods=["*"],
    allow_headers=["*"],
)

# Danh sách kết nối WebSocket đang mở, để đẩy dữ liệu realtime
active_connections: List[WebSocket] = []

# Dự báo và cấu hình cảnh báo được lưu thật trong PostgreSQL - xem app/postgres_db.py


@app.on_event("startup")
async def on_startup():
    # Bật MQTT subscriber chạy nền cùng lúc với API
    global _mqtt_client
    loop = asyncio.get_running_loop()

    def forward_to_websocket(data: dict) -> None:
        # Được gọi từ thread paho-mqtt -> chuyển sang event loop của FastAPI
        try:
            reading = _reading_from_payload(data)
        except Exception:
            logger.exception("Cannot build realtime reading from payload %r", data)
            return
        asyncio.run_coroutine_threadsafe(broadcast_reading(reading), loop)

    def forward_alert_to_websocket(alert: dict) -> None:
        asyncio.run_coroutine_threadsafe(broadcast_message(alert), loop)

    set_reading_listener(forward_to_websocket)
    set_alert_listener(forward_alert_to_websocket)
    _mqtt_client = start_mqtt_listener()


@app.on_event("shutdown")
def on_shutdown():
    set_reading_listener(None)
    set_alert_listener(None)
    stop_mqtt_listener(_mqtt_client)
    _influx_client.close()


@app.get("/health")
def health_check():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


@app.get("/api/readings", response_model=ReadingsResponse)
def get_readings(
    device_id: str,
    from_: Optional[datetime] = Query(default=None, alias="from"),
    to: Optional[datetime] = None,
    limit: int = Query(default=1000, ge=1, le=10000),
):
    """Return a node's stored readings, oldest first, with optional time bounds."""
    if from_ and to and _as_utc(from_) >= _as_utc(to):
        raise HTTPException(status_code=422, detail="from must be earlier than to")

    start = _flux_time(from_) if from_ else "0"
    stop = _flux_time(to) if to else None
    query = (
        f'from(bucket: {json.dumps(INFLUXDB_BUCKET)}) '
        f'|> range(start: {start}' + (f", stop: {stop}" if stop else "") + ")\n"
        '|> filter(fn: (r) => r._measurement == "air_quality")\n'
        f'|> filter(fn: (r) => r.device_id == {json.dumps(device_id)})\n'
        '|> pivot(rowKey: ["_time", "device_id"], columnKey: ["_field"], valueColumn: "_value")\n'
        '|> sort(columns: ["_time"], desc: true)\n'
        f"|> limit(n: {limit})\n"
        '|> sort(columns: ["_time"], desc: false)'
    )
    try:
        records = _influx_client.query_api().query(query, org=INFLUXDB_ORG)
        items = [_reading_from_record(record.values) for table in records for record in table.records]
    except Exception as exc:
        logger.exception("InfluxDB query failed for device %s", device_id)
        raise HTTPException(status_code=503, detail="Reading storage is temporarily unavailable") from exc
    return ReadingsResponse(device_id=device_id, items=items)


@app.get("/api/readings/latest", response_model=LatestReadingsResponse)
def get_latest_readings():
    """Return the newest reading for every device that has data."""
    query = (
        f'from(bucket: {json.dumps(INFLUXDB_BUCKET)}) |> range(start: 0)\n'
        '|> filter(fn: (r) => r._measurement == "air_quality")\n'
        '|> pivot(rowKey: ["_time", "device_id"], columnKey: ["_field"], valueColumn: "_value")\n'
        '|> group(columns: ["device_id"])\n'
        '|> sort(columns: ["_time"], desc: true)\n'
        '|> limit(n: 1)'
    )
    try:
        records = _influx_client.query_api().query(query, org=INFLUXDB_ORG)
        items = [_reading_from_record(record.values) for table in records for record in table.records]
    except Exception as exc:
        logger.exception("InfluxDB latest-readings query failed")
        raise HTTPException(status_code=503, detail="Reading storage is temporarily unavailable") from exc
    return LatestReadingsResponse(items=items)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _flux_time(value: datetime) -> str:
    return _as_utc(value).isoformat().replace("+00:00", "Z")


def _reading_from_record(values: dict) -> SensorReading:
    pm25 = values.get("pm25")
    return SensorReading(
        device_id=values["device_id"],
        timestamp=values.get("_time"),
        pm25=pm25,
        pm10=values.get("pm10"),
        co2=values.get("co2"),
        temperature=values.get("temperature"),
        humidity=values.get("humidity"),
        aqi=pm25_to_aqi(pm25),
    )


def _reading_from_payload(data: dict) -> SensorReading:
    """Dựng SensorReading từ payload MQTT vừa ghi, cùng định dạng 1 item của /api/readings."""
    pm25 = data.get("pm25")
    return SensorReading(
        device_id=data["device_id"].strip(),
        timestamp=_parse_timestamp(data.get("timestamp")) or datetime.now(timezone.utc),
        pm25=pm25,
        pm10=data.get("pm10"),
        co2=data.get("co2"),
        temperature=data.get("temperature"),
        humidity=data.get("humidity"),
        aqi=pm25_to_aqi(pm25),
    )


@app.post("/api/forecasts")
def submit_forecast(forecast: ForecastSubmission):
    """Khối AI gọi endpoint này sau mỗi lần chạy dự báo."""
    postgres_db.save_forecast(
        device_id=forecast.device_id,
        generated_at=forecast.generated_at,
        horizon_hours=forecast.horizon_hours,
        predictions=[p.dict() for p in forecast.predictions],
    )
    return {"status": "received", "device_id": forecast.device_id}


@app.get("/api/forecasts/latest")
def get_latest_forecast(device_id: str):
    forecast = postgres_db.get_latest_forecast(device_id)
    if not forecast:
        raise HTTPException(status_code=404, detail="Chưa có dự báo cho node này")
    return forecast


@app.get("/api/alerts/config", response_model=AlertConfig)
def get_alert_config(device_id: str):
    config = postgres_db.get_alert_config(device_id)
    if not config:
        # Node chưa từng cấu hình ngưỡng -> trả về mặc định (chưa lưu vào DB)
        return AlertConfig(device_id=device_id)
    return AlertConfig(**config)


@app.post("/api/alerts/config")
def set_alert_config(config: AlertConfig):
    saved = postgres_db.upsert_alert_config(
        device_id=config.device_id,
        pm25_threshold=config.pm25_threshold,
        aqi_threshold=config.aqi_threshold,
    )
    return {"status": "saved", "config": saved}


@app.get("/api/alerts")
def get_alerts(
    device_id: str,
    limit: int = Query(default=20, ge=1, le=500),
):
    """Return the newest persisted alerts for one device (empty list when none exist)."""
    try:
        items = postgres_db.get_alert_events(device_id, limit)
    except Exception as exc:
        logger.exception("PostgreSQL alert query failed for device %s", device_id)
        raise HTTPException(status_code=503, detail="Alert storage is temporarily unavailable") from exc
    return {"device_id": device_id, "items": items}


@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    """Đẩy dữ liệu realtime cho Dashboard. mqtt_subscriber gọi broadcast_reading()
    (qua on_startup) ngay sau mỗi lần ghi InfluxDB thành công."""
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            await websocket.receive_text()  # giữ kết nối; client không cần gửi gì
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in active_connections:
            active_connections.remove(websocket)


async def broadcast_reading(reading: SensorReading):
    """Gửi 1 bản ghi mới tới mọi Dashboard đang mở /ws/live."""
    # mode="json" để datetime thành chuỗi ISO-8601 (send_json không tự đổi được)
    await broadcast_message(reading.model_dump(mode="json"))


async def broadcast_message(message: dict):
    """Send a JSON message (reading or alert) to connected dashboards."""
    for connection in list(active_connections):
        try:
            await connection.send_json(message)
        except Exception:
            if connection in active_connections:
                active_connections.remove(connection)
