-- PBL4 - Giám sát & Dự báo Chất lượng Không khí
-- Schema PostgreSQL: dữ liệu quan hệ (node, người dùng, ngưỡng cảnh báo)
-- Dữ liệu đo lường theo thời gian (readings) được lưu ở InfluxDB, KHÔNG ở đây.

CREATE TABLE IF NOT EXISTS devices (
    device_id       VARCHAR(50) PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    location        VARCHAR(200),
    latitude        DOUBLE PRECISION,
    longitude       DOUBLE PRECISION,
    installed_at    TIMESTAMP DEFAULT NOW(),
    is_active       BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    email           VARCHAR(150) UNIQUE NOT NULL,
    full_name       VARCHAR(100),
    password_hash   VARCHAR(255) NOT NULL,
    role            VARCHAR(20) DEFAULT 'viewer',  -- 'admin' | 'viewer'
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS alert_configs (
    id              SERIAL PRIMARY KEY,
    device_id       VARCHAR(50) REFERENCES devices(device_id) ON DELETE CASCADE,
    pm25_threshold  DOUBLE PRECISION DEFAULT 55.0,
    aqi_threshold   DOUBLE PRECISION DEFAULT 100.0,
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS alert_events (
    id              SERIAL PRIMARY KEY,
    device_id       VARCHAR(50) REFERENCES devices(device_id) ON DELETE CASCADE,
    metric          VARCHAR(20) NOT NULL,   -- 'pm25' | 'aqi'
    value           DOUBLE PRECISION NOT NULL,
    threshold       DOUBLE PRECISION NOT NULL,
    triggered_at    TIMESTAMP DEFAULT NOW(),
    acknowledged    BOOLEAN DEFAULT FALSE
);

-- Bảng lưu tóm tắt các lần chạy dự báo (chi tiết từng điểm dự báo có thể lưu
-- ở InfluxDB hoặc bảng con forecast_points, tuỳ nhóm quyết định khi triển khai)
CREATE TABLE IF NOT EXISTS forecast_runs (
    id              SERIAL PRIMARY KEY,
    device_id       VARCHAR(50) REFERENCES devices(device_id) ON DELETE CASCADE,
    generated_at    TIMESTAMP NOT NULL,
    horizon_hours   INT NOT NULL,
    model_version   VARCHAR(50),
    mae             DOUBLE PRECISION,
    rmse            DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS forecast_points (
    id              SERIAL PRIMARY KEY,
    forecast_run_id INT REFERENCES forecast_runs(id) ON DELETE CASCADE,
    timestamp       TIMESTAMP NOT NULL,
    aqi             DOUBLE PRECISION,
    pm25            DOUBLE PRECISION
);

-- Dữ liệu mẫu để test nhanh khi chưa có node thật
INSERT INTO devices (device_id, name, location, is_active)
VALUES ('node-01', 'Node thử nghiệm 1', 'Phòng Lab', TRUE)
ON CONFLICT (device_id) DO NOTHING;

INSERT INTO alert_configs (device_id, pm25_threshold, aqi_threshold)
VALUES ('node-01', 55.0, 100.0)
ON CONFLICT DO NOTHING;
