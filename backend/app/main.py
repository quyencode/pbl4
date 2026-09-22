"""
Backend API - PBL4 Giám sát & Dự báo Chất lượng Không khí
Chạy dev: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
Tài liệu API tự sinh tại: http://localhost:8000/docs

Các endpoint dưới đây khớp với iot/mqtt_data_contract.md - KHÔNG đổi
định dạng field mà không cập nhật lại contract và báo cả nhóm.
"""
import os
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.schemas import (
    SensorReading,
    ReadingsResponse,
    ForecastSubmission,
    AlertConfig,
)
from app.mqtt_subscriber import start_mqtt_listener

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

# In-memory store tạm cho dự báo mới nhất theo device_id (demo/dev only)
# TODO: thay bằng lưu thật ở PostgreSQL (bảng forecast_runs/forecast_points)
_latest_forecasts: dict = {}


@app.on_event("startup")
def on_startup():
    # Bật MQTT subscriber chạy nền cùng lúc với API
    start_mqtt_listener()


@app.get("/health")
def health_check():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


@app.get("/api/readings", response_model=ReadingsResponse)
def get_readings(
    device_id: str,
    from_: Optional[str] = None,
    to: Optional[str] = None,
    limit: int = 1000,
):
    """
    Lấy dữ liệu lịch sử của một node - dùng cho huấn luyện AI và biểu đồ lịch sử.
    TODO: truy vấn InfluxDB (Flux query) theo device_id/khoảng thời gian, hiện
    trả về mảng rỗng làm khung sườn.
    """
    # TODO: query_api = influx_client.query_api(); flux query theo from_/to/limit
    return ReadingsResponse(device_id=device_id, items=[])


@app.get("/api/readings/latest")
def get_latest_readings():
    """Bản ghi mới nhất của MỌI node - dùng cho màn hình chính Dashboard."""
    # TODO: query InfluxDB lấy last() theo từng device_id
    return {"items": []}


@app.post("/api/forecasts")
def submit_forecast(forecast: ForecastSubmission):
    """Khối AI gọi endpoint này sau mỗi lần chạy dự báo."""
    _latest_forecasts[forecast.device_id] = forecast.dict()
    # TODO: lưu vào PostgreSQL (forecast_runs + forecast_points)
    return {"status": "received", "device_id": forecast.device_id}


@app.get("/api/forecasts/latest")
def get_latest_forecast(device_id: str):
    forecast = _latest_forecasts.get(device_id)
    if not forecast:
        raise HTTPException(status_code=404, detail="Chưa có dự báo cho node này")
    return forecast


@app.get("/api/alerts/config", response_model=AlertConfig)
def get_alert_config(device_id: str):
    # TODO: đọc từ bảng alert_configs trong PostgreSQL
    return AlertConfig(device_id=device_id)


@app.post("/api/alerts/config")
def set_alert_config(config: AlertConfig):
    # TODO: upsert vào bảng alert_configs trong PostgreSQL
    return {"status": "saved", "config": config}


@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    """Đẩy dữ liệu realtime cho Dashboard. Gọi broadcast_reading() từ
    mqtt_subscriber khi có dữ liệu mới (cần nối thêm event loop / queue)."""
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            await websocket.receive_text()  # giữ kết nối; client không cần gửi gì
    except WebSocketDisconnect:
        active_connections.remove(websocket)


async def broadcast_reading(reading: SensorReading):
    """TODO: gọi hàm này từ mqtt_subscriber (qua asyncio queue) mỗi khi có
    dữ liệu mới, để đẩy realtime tới mọi client đang mở dashboard."""
    for connection in list(active_connections):
        try:
            await connection.send_json(reading.dict())
        except Exception:
            active_connections.remove(connection)
