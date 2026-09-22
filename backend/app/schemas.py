"""
Pydantic schemas - phải khớp với data contract ở iot/mqtt_data_contract.md
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class SensorReading(BaseModel):
    device_id: str
    pm25: Optional[float] = None
    pm10: Optional[float] = None
    co2: Optional[int] = None
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    timestamp: Optional[datetime] = None


class ReadingsResponse(BaseModel):
    device_id: str
    items: List[SensorReading]


class ForecastPoint(BaseModel):
    timestamp: datetime
    aqi: Optional[float] = None
    pm25: Optional[float] = None


class ForecastSubmission(BaseModel):
    device_id: str
    generated_at: datetime
    horizon_hours: int
    predictions: List[ForecastPoint]


class AlertConfig(BaseModel):
    device_id: str
    pm25_threshold: float = 55.0
    aqi_threshold: float = 100.0
