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
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

import psycopg2
import psycopg2.extras

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.getenv("POSTGRES_USER", "aqi_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "aqi_pass")
POSTGRES_DB = os.getenv("POSTGRES_DB", "aqi_db")
ALERT_REPEAT_INTERVAL = timedelta(minutes=10)


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


def get_alert_thresholds(device_id: str) -> dict[str, float]:
    """Return configured thresholds, using contract defaults for an unconfigured device."""
    config = get_alert_config(device_id)
    if config:
        return {"pm25": float(config["pm25_threshold"]), "aqi": float(config["aqi_threshold"])}
    return {"pm25": 55.0, "aqi": 100.0}


def save_alert_event_if_due(
    device_id: str, metric: str, value: float, threshold: float, triggered_at: datetime,
    force: bool = False,
) -> Optional[dict]:
    """Persist a threshold crossing or a reminder at most once per ten minutes."""
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            _ensure_device(cur, device_id)
            cur.execute(
                "SELECT triggered_at FROM alert_events WHERE device_id = %s AND metric = %s "
                "ORDER BY triggered_at DESC LIMIT 1",
                (device_id, metric),
            )
            last = cur.fetchone()
            if not force and last and triggered_at - _as_utc(last["triggered_at"]) < ALERT_REPEAT_INTERVAL:
                return None
            cur.execute(
                "INSERT INTO alert_events (device_id, metric, value, threshold, triggered_at) "
                "VALUES (%s, %s, %s, %s, %s) "
                "RETURNING id, device_id, metric, value, threshold, triggered_at, acknowledged",
                (device_id, metric, value, threshold, triggered_at),
            )
            return dict(cur.fetchone())


def get_alert_events(device_id: str, limit: int = 20) -> list[dict]:
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, device_id, metric, value, threshold, triggered_at, acknowledged "
                "FROM alert_events WHERE device_id = %s ORDER BY triggered_at DESC, id DESC LIMIT %s",
                (device_id, limit),
            )
            rows = [dict(row) for row in cur.fetchall()]
            for row in rows:
                row["triggered_at"] = _as_utc(row["triggered_at"])
            return rows


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


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
