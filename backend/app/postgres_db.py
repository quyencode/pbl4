"""Kết nối PostgreSQL: lưu alert_configs và forecast_runs/forecast_points.

Dữ liệu đo lường theo thời gian (readings) KHÔNG lưu ở đây - xem
mqtt_subscriber.py / main.py (InfluxDB). File này chỉ phụ trách dữ liệu quan
hệ: cấu hình ngưỡng cảnh báo và lịch sử các lần chạy dự báo của khối AI,
đúng theo schema trong database/init_postgres.sql.

Lưu ý: bảng alert_configs trong init_postgres.sql không có ràng buộc UNIQUE
trên device_id, nên không dùng được "ON CONFLICT (device_id) DO UPDATE" -
hàm upsert_alert_config bên dưới tự kiểm tra record đã tồn tại chưa (SELECT
rồi UPDATE/INSERT) thay vì dựa vào constraint.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Optional

import psycopg2
import psycopg2.extras

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.getenv("POSTGRES_USER", "aqi_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "aqi_pass")
POSTGRES_DB = os.getenv("POSTGRES_DB", "aqi_db")


@contextmanager
def _get_conn():
    conn = psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        dbname=POSTGRES_DB,
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _ensure_device(cur, device_id: str) -> None:
    """Đảm bảo device_id đã có trong bảng devices, vì alert_configs/forecast_runs
    đều tham chiếu devices(device_id) qua FOREIGN KEY."""
    cur.execute(
        "INSERT INTO devices (device_id, name) VALUES (%s, %s) "
        "ON CONFLICT (device_id) DO NOTHING",
        (device_id, device_id),
    )


def get_alert_config(device_id: str) -> Optional[dict]:
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT device_id, pm25_threshold, aqi_threshold "
                "FROM alert_configs WHERE device_id = %s "
                "ORDER BY updated_at DESC LIMIT 1",
                (device_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def upsert_alert_config(device_id: str, pm25_threshold: float, aqi_threshold: float) -> dict:
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            _ensure_device(cur, device_id)
            cur.execute("SELECT id FROM alert_configs WHERE device_id = %s", (device_id,))
            existing = cur.fetchone()
            if existing:
                cur.execute(
                    "UPDATE alert_configs "
                    "SET pm25_threshold = %s, aqi_threshold = %s, updated_at = NOW() "
                    "WHERE id = %s "
                    "RETURNING device_id, pm25_threshold, aqi_threshold",
                    (pm25_threshold, aqi_threshold, existing["id"]),
                )
            else:
                cur.execute(
                    "INSERT INTO alert_configs (device_id, pm25_threshold, aqi_threshold) "
                    "VALUES (%s, %s, %s) "
                    "RETURNING device_id, pm25_threshold, aqi_threshold",
                    (device_id, pm25_threshold, aqi_threshold),
                )
            return dict(cur.fetchone())


def save_forecast(
    device_id: str,
    generated_at: datetime,
    horizon_hours: int,
    predictions: list[dict[str, Any]],
) -> None:
    """Lưu 1 lần chạy dự báo: 1 dòng forecast_runs + N dòng forecast_points."""
    with _get_conn() as conn:
        with conn.cursor() as cur:
            _ensure_device(cur, device_id)
            cur.execute(
                "INSERT INTO forecast_runs (device_id, generated_at, horizon_hours) "
                "VALUES (%s, %s, %s) RETURNING id",
                (device_id, generated_at, horizon_hours),
            )
            forecast_run_id = cur.fetchone()[0]

            if predictions:
                psycopg2.extras.execute_values(
                    cur,
                    "INSERT INTO forecast_points (forecast_run_id, timestamp, aqi, pm25) VALUES %s",
                    [
                        (forecast_run_id, p["timestamp"], p.get("aqi"), p.get("pm25"))
                        for p in predictions
                    ],
                )


def get_latest_forecast(device_id: str) -> Optional[dict]:
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, device_id, generated_at, horizon_hours "
                "FROM forecast_runs WHERE device_id = %s "
                "ORDER BY generated_at DESC LIMIT 1",
                (device_id,),
            )
            run = cur.fetchone()
            if not run:
                return None

            cur.execute(
                "SELECT timestamp, aqi, pm25 FROM forecast_points "
                "WHERE forecast_run_id = %s ORDER BY timestamp ASC",
                (run["id"],),
            )
            points = [dict(r) for r in cur.fetchall()]

            return {
                "device_id": run["device_id"],
                "generated_at": run["generated_at"],
                "horizon_hours": run["horizon_hours"],
                "predictions": points,
            }
