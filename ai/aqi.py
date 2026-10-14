"""Tính chỉ số AQI từ nồng độ PM2.5 theo chuẩn US EPA (bảng breakpoint cập nhật 2024).

predict.py dùng để điền trường "aqi" cho từng điểm dự báo, khớp với cách Backend
tính AQI cho dữ liệu đo.
Bản sao của backend/app/aqi.py - sửa bảng breakpoint thì sửa cả hai file.

Lưu ý: đây là AQI tính tức thời từ 1 giá trị PM2.5, không phải NowCast hay VN_AQI.
"""
from __future__ import annotations

import math
from typing import Optional

# (PM2.5 thấp, PM2.5 cao, AQI thấp, AQI cao) - đơn vị µg/m³
PM25_BREAKPOINTS = (
    (0.0, 9.0, 0, 50),
    (9.1, 35.4, 51, 100),
    (35.5, 55.4, 101, 150),
    (55.5, 125.4, 151, 200),
    (125.5, 225.4, 201, 300),
    (225.5, 325.4, 301, 500),
)


def pm25_to_aqi(pm25: Optional[float]) -> Optional[int]:
    """Đổi PM2.5 (µg/m³) sang AQI; trả None nếu không có số đo hợp lệ."""
    if pm25 is None or isinstance(pm25, bool):
        return None
    try:
        value = float(pm25)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value) or value < 0:
        return None

    # EPA cắt (truncate) về 1 chữ số thập phân trước khi tra bảng
    value = math.floor(round(value * 10, 6)) / 10
    if value > PM25_BREAKPOINTS[-1][1]:
        return 500

    for c_low, c_high, i_low, i_high in PM25_BREAKPOINTS:
        if value <= c_high:
            # Khoảng hở giữa hai mức (vd 9.05 sau khi cắt vẫn rơi vào mức dưới)
            value = max(value, c_low)
            return round((i_high - i_low) / (c_high - c_low) * (value - c_low) + i_low)
    return 500
