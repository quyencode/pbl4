import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine,
} from "recharts";
import {
  getLatestReadingForDevice, getReadingsHistory, getLatestForecast, connectLiveSocket,
  getReadingsSince, getAlerts, getAlertConfig, saveAlertConfig,
} from "./api.js";
import { MOCK_LATEST, MOCK_HISTORY, MOCK_FORECAST } from "./mockData.js";
import { unlockAlertSound, playAlertSound } from "./alertSound.js";
import "./App.css";

const DEFAULT_DEVICE_ID = "node-01";
const MAX_HISTORY_POINTS = 168; // khớp mặc định limit của getReadingsHistory
const HOUR_MS = 60 * 60 * 1000;
const FORECAST_REFRESH_MS = 5 * 60 * 1000; // tự lấy lại dự báo mới mỗi 5 phút
const FORECAST_STALE_MS = 2 * HOUR_MS;     // dự báo cũ hơn 2 giờ thì báo "đã cũ"
const SOUND_COOLDOWN_MS = 10 * 1000;       // không kêu dồn dập khi nhiều cảnh báo đến cùng lúc
const DEFAULT_ALERT_CONFIG = { pm25_threshold: 55, aqi_threshold: 100 };

const METRIC_LABEL = { pm25: "PM2.5", aqi: "AQI" };
const METRIC_UNIT = { pm25: " µg/m³", aqi: "" };

// Làm tròn số liệu hiển thị, giữ "—" khi chưa có dữ liệu
function formatNumber(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return Number(value).toFixed(digits);
}

// PostgreSQL lưu giờ dự báo dạng "không múi giờ" (thực chất là giờ UTC), ví dụ "2026-10-29T14:14:00".
// Trình duyệt sẽ hiểu nhầm thành giờ Việt Nam (lệch 7 tiếng) -> chuỗi nào thiếu múi giờ thì coi là UTC.
function toTime(value) {
  if (value === null || value === undefined) return NaN;
  if (typeof value === "string" && !/(z|[+-]\d{2}:?\d{2})$/i.test(value.trim())) {
    return new Date(value.trim().replace(" ", "T") + "Z").getTime();
  }
  return new Date(value).getTime();
}

function normalizeForecast(f) {
  if (!f) return f;
  const iso = (v) => {
    const t = toTime(v);
    return Number.isNaN(t) ? v : new Date(t).toISOString();
  };
  return {
    ...f,
    generated_at: iso(f.generated_at),
    predictions: (f.predictions || []).map((p) => ({ ...p, timestamp: iso(p.timestamp) })),
  };
}

// Gộp số đo thô (30 giây/lần) thành trung bình theo giờ để vẽ cạnh dự báo (1 điểm/giờ)
function hourlyAverage(readings) {
  const buckets = new Map();
  for (const r of readings) {
    if (r.pm25 === null || r.pm25 === undefined || !r.timestamp) continue;
    const t = toTime(r.timestamp);
    if (Number.isNaN(t)) continue;
    const key = Math.floor(t / HOUR_MS) * HOUR_MS;
    const b = buckets.get(key) || { sum: 0, n: 0 };
    b.sum += Number(r.pm25);
    b.n += 1;
    buckets.set(key, b);
  }
  return [...buckets.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([t, b]) => ({ t, pm25: Math.round((b.sum / b.n) * 10) / 10 }));
}

// Ghép PM2.5 thực tế 24 giờ qua và dự báo 24 giờ tới vào cùng một trục thời gian
function buildCombinedSeries(hourly, forecast) {
  const points = hourly.map((p) => ({ t: p.t, actual: p.pm25 }));
  const predicted = (forecast?.predictions || [])
    .map((p) => ({ t: new Date(p.timestamp).getTime(), forecast: p.pm25 }))
    .filter((p) => !Number.isNaN(p.t) && p.forecast !== null && p.forecast !== undefined);
  // Nối liền 2 đường: điểm thực tế cuối cùng cũng là điểm đầu của đường dự báo
  if (points.length && predicted.length && predicted[0].t > points[points.length - 1].t) {
    points[points.length - 1].forecast = points[points.length - 1].actual;
  }
  return [...points, ...predicted].sort((a, b) => a.t - b.t);
}

// Các chỉ số đang vượt ngưỡng ở bản ghi hiện tại
function exceededMetrics(reading, config) {
  if (!reading) return [];
  const out = [];
  if (reading.pm25 != null && Number(reading.pm25) >= config.pm25_threshold)
    out.push({ metric: "pm25", value: Number(reading.pm25), threshold: config.pm25_threshold });
  if (reading.aqi != null && Number(reading.aqi) >= config.aqi_threshold)
    out.push({ metric: "aqi", value: Number(reading.aqi), threshold: config.aqi_threshold });
  return out;
}

export default function App() {
  const [latest, setLatest] = useState(null);
  const [history, setHistory] = useState([]);
  const [recent24h, setRecent24h] = useState([]);
  const [forecast, setForecast] = useState(null);
  const [forecastIsMock, setForecastIsMock] = useState(false);
  const [loading, setLoading] = useState(true);
  const [usingMock, setUsingMock] = useState(false);
  const [noRealDataYet, setNoRealDataYet] = useState(false);

  // ----- Cảnh báo -----
  const [alertConfig, setAlertConfig] = useState(DEFAULT_ALERT_CONFIG);
  const [configDraft, setConfigDraft] = useState(DEFAULT_ALERT_CONFIG);
  const [configStatus, setConfigStatus] = useState("");
  const [alerts, setAlerts] = useState([]);
  const [backendAlerts, setBackendAlerts] = useState(null); // null: chưa biết, false: Backend chưa có /api/alerts
  const [soundOn, setSoundOn] = useState(false);
  const [testAlert, setTestAlert] = useState(null);
  const soundOnRef = useRef(false);
  const lastSoundAtRef = useRef(0);
  const wasExceededRef = useRef(false);

  function notifySound() {
    const now = Date.now();
    if (!soundOnRef.current || now - lastSoundAtRef.current < SOUND_COOLDOWN_MS) return;
    lastSoundAtRef.current = now;
    playAlertSound();
  }

  function addAlert(alert) {
    setAlerts((prev) => (prev.some((a) => a.id === alert.id) ? prev : [alert, ...prev].slice(0, 20)));
  }

  useEffect(() => {
    let cancelled = false;

    async function loadInitialData() {
      const [latestResult, historyResult, recentResult] = await Promise.allSettled([
        getLatestReadingForDevice(DEFAULT_DEVICE_ID),
        getReadingsHistory(DEFAULT_DEVICE_ID),
        getReadingsSince(DEFAULT_DEVICE_ID, new Date(Date.now() - 24 * HOUR_MS)),
      ]);

      if (cancelled) return;

      if (latestResult.status === "fulfilled") {
        if (latestResult.value) {
          setLatest(latestResult.value);
        } else {
          // API thật đã trả lời (không lỗi) nhưng chưa có bản ghi nào cho node này
          setNoRealDataYet(true);
        }
      } else {
        console.warn("Không gọi được API /readings/latest, dùng dữ liệu mẫu:", latestResult.reason?.message);
        setLatest(MOCK_LATEST);
        setUsingMock(true);
      }

      if (historyResult.status === "fulfilled") {
        const items = historyResult.value.items || [];
        if (items.length > 0) {
          setHistory(items);
        } else {
          setNoRealDataYet(true);
        }
      } else {
        console.warn("Không gọi được API /readings, dùng dữ liệu mẫu:", historyResult.reason?.message);
        setHistory(MOCK_HISTORY);
        setUsingMock(true);
      }

      if (recentResult.status === "fulfilled") {
        setRecent24h(recentResult.value.items || []);
      } else {
        setRecent24h(MOCK_HISTORY);
      }

      setLoading(false);
    }

    async function loadForecast() {
      try {
        const f = await getLatestForecast(DEFAULT_DEVICE_ID);
        if (cancelled) return;
        setForecast(normalizeForecast(f));
        setForecastIsMock(false);
      } catch {
        // Backend chưa chạy -> dùng dự báo mẫu để vẫn xem được biểu đồ
        if (cancelled) return;
        setForecast(MOCK_FORECAST);
        setForecastIsMock(true);
      }
    }

    loadInitialData();
    loadForecast();
    const forecastTimer = setInterval(loadForecast, FORECAST_REFRESH_MS);

    getAlertConfig(DEFAULT_DEVICE_ID)
      .then((cfg) => {
        if (cancelled || !cfg) return;
        const next = { pm25_threshold: Number(cfg.pm25_threshold), aqi_threshold: Number(cfg.aqi_threshold) };
        setAlertConfig(next);
        setConfigDraft(next);
      })
      .catch(() => {});

    getAlerts(DEFAULT_DEVICE_ID)
      .then((items) => {
        if (cancelled) return;
        if (items === null) {
          setBackendAlerts(false); // Backend chưa có API -> Dashboard tự phát hiện vượt ngưỡng
        } else {
          setBackendAlerts(true);
          setAlerts(items);
        }
      })
      .catch(() => !cancelled && setBackendAlerts(false));

    // Realtime: message có "type": "alert" là cảnh báo, không có "type" là số đo mới
    // (xem iot/mqtt_data_contract.md mục 2.6, 2.7) - chỉ xử lý đúng node đang xem.
    const socket = connectLiveSocket((data) => {
      if (data.device_id !== DEFAULT_DEVICE_ID) return;
      if (data.type === "alert") {
        setBackendAlerts(true);
        addAlert(data);
        notifySound();
        return;
      }
      setLatest(data);
      setUsingMock(false);
      setNoRealDataYet(false);
      setHistory((prev) => [...prev.slice(-(MAX_HISTORY_POINTS - 1)), data]);
      const cutoff = Date.now() - 24 * HOUR_MS;
      setRecent24h((prev) => [...prev.filter((r) => toTime(r.timestamp) >= cutoff), data]);
    });
    socket.onerror = () => {
      // Backend/WS chưa chạy -> bỏ qua, không phải lỗi hiển thị
    };

    return () => {
      cancelled = true;
      clearInterval(forecastTimer);
      socket.close();
    };
  }, []);

  // Phát hiện vượt ngưỡng ngay trên Dashboard (để banner hiện tức thì).
  // Nếu Backend chưa có /api/alerts thì Dashboard tự ghi vào danh sách cảnh báo.
  const exceeded = exceededMetrics(usingMock ? null : latest, alertConfig);
  useEffect(() => {
    const isExceeded = exceeded.length > 0;
    if (isExceeded && !wasExceededRef.current) {
      if (backendAlerts !== true) {
        const when = latest?.timestamp || new Date().toISOString();
        exceeded.forEach((e) =>
          addAlert({ id: `local-${e.metric}-${when}`, device_id: DEFAULT_DEVICE_ID, ...e, triggered_at: when, local: true }),
        );
      }
      notifySound();
    }
    wasExceededRef.current = isExceeded;
  }, [latest, alertConfig, backendAlerts]); // eslint-disable-line react-hooks/exhaustive-deps

  function toggleSound() {
    if (soundOn) {
      setSoundOn(false);
      soundOnRef.current = false;
      return;
    }
    if (unlockAlertSound()) {
      setSoundOn(true);
      soundOnRef.current = true;
      playAlertSound(); // kêu thử 1 lần để biết loa đang bật
    }
  }

  function runTestAlert() {
    const value = Math.round((alertConfig.pm25_threshold + 7) * 10) / 10;
    setTestAlert({ metric: "pm25", value, threshold: alertConfig.pm25_threshold });
    lastSoundAtRef.current = 0;
    notifySound();
    setTimeout(() => setTestAlert(null), 10000);
  }

  async function submitConfig(event) {
    event.preventDefault();
    const next = {
      pm25_threshold: Number(configDraft.pm25_threshold),
      aqi_threshold: Number(configDraft.aqi_threshold),
    };
    if (!(next.pm25_threshold > 0) || !(next.aqi_threshold > 0)) {
      setConfigStatus("Ngưỡng phải là số lớn hơn 0.");
      return;
    }
    setConfigStatus("Đang lưu…");
    try {
      await saveAlertConfig({ device_id: DEFAULT_DEVICE_ID, ...next });
      setAlertConfig(next);
      setConfigStatus("Đã lưu ngưỡng mới.");
    } catch {
      setAlertConfig(next); // vẫn áp dụng trên Dashboard để thử, báo rõ là chưa lưu được
      setConfigStatus("Chưa lưu được lên Backend (đang áp dụng tạm trên trang này).");
    }
  }

  const isLive = Boolean(latest) && !usingMock;
  const level = aqiLevel(latest?.aqi);
  const nowMs = Date.now();
  const nextForecast = forecast?.predictions?.find((p) => new Date(p.timestamp).getTime() > nowMs) || forecast?.predictions?.[0];
  const hourly = useMemo(() => hourlyAverage(recent24h), [recent24h]);
  const series = useMemo(() => buildCombinedSeries(hourly, forecast), [hourly, forecast]);
  const forecastAt = forecast?.generated_at ? new Date(forecast.generated_at) : null;
  const forecastStale = forecastAt && nowMs - forecastAt.getTime() > FORECAST_STALE_MS;
  const bannerItems = testAlert ? [testAlert] : exceeded;

  return (
    <div className="page">
      <div className="sun-glow" aria-hidden="true" />
      <div className="cloud cloud--1" aria-hidden="true" />
      <div className="cloud cloud--2" aria-hidden="true" />

      <div className="shell">
        <header className="app-header">
          <div className="app-header-text">
            <h1>
              Hôm nay không khí thế nào? <span className="header-emoji">🌞</span>
            </h1>
            <p className="app-subtitle">PBL4 · IoT cảm biến · AI dự báo · Realtime dashboard</p>
          </div>
          <div className="header-actions">
            <button type="button" className={`sound-toggle${soundOn ? " sound-toggle--on" : ""}`} onClick={toggleSound}>
              {soundOn ? "🔔 Âm thanh cảnh báo: bật" : "🔕 Bật âm thanh cảnh báo"}
            </button>
            <span className={`status-pill ${isLive ? "status-pill--live" : "status-pill--idle"}`}>
              <span className="status-dot" />
              {isLive ? "Đang hoạt động" : "Chưa có dữ liệu"}
            </span>
          </div>
        </header>

        {bannerItems.length > 0 && (
          <div className="banner banner--alert" role="alert">
            <span className="banner-icon">🚨</span>
            <span>
              <strong>Cảnh báo ô nhiễm{testAlert ? " (thử)" : ""}: </strong>
              {bannerItems
                .map((e) => `${METRIC_LABEL[e.metric]} ${formatNumber(e.value, e.metric === "aqi" ? 0 : 1)}${METRIC_UNIT[e.metric]} vượt ngưỡng ${formatNumber(e.threshold, 0)}`)
                .join(", ")}
              . Hạn chế ra ngoài, đóng cửa sổ, đeo khẩu trang khi cần.
            </span>
          </div>
        )}

        {loading && <p className="loading-text">Đang tải dữ liệu…</p>}

        {usingMock && (
          <div className="banner banner--warning">
            <span className="banner-icon">⚠️</span>
            <span>
              Đang hiển thị dữ liệu mẫu (backend chưa chạy). Chạy <code>docker compose up -d</code> để xem dữ liệu thật.
            </span>
          </div>
        )}

        {!usingMock && noRealDataYet && (
          <div className="banner banner--info">
            <span className="banner-icon">ℹ️</span>
            <span>
              Đã kết nối API thật nhưng chưa có dữ liệu cho node <code>{DEFAULT_DEVICE_ID}</code> — kiểm tra xem node
              cảm biến và MQTT subscriber đã publish/ghi dữ liệu chưa.
            </span>
          </div>
        )}

        <section className="overview">
          <div className="card aqi-panel">
            <div className="aqi-ring">
              <div className="aqi-ring-value">{formatNumber(latest?.aqi, 0)}</div>
              <div className="aqi-ring-label">Chỉ số AQI</div>
            </div>
            {level ? (
              <>
                <span className="aqi-level" style={{ background: level.bg, color: level.fg }}>
                  {level.label}
                </span>
                <p className="aqi-advice">{level.advice}</p>
              </>
            ) : (
              <p className="aqi-advice">{latest ? "Chưa có số đo PM2.5 để tính AQI." : "Đang chờ dữ liệu từ node cảm biến."}</p>
            )}
          </div>

          <div className="metric-grid">
            <MetricCard icon="leaf" label="PM2.5" value={formatNumber(latest?.pm25, 1)} unit="µg/m³" />
            <MetricCard icon="dust" label="PM10" value={formatNumber(latest?.pm10, 1)} unit="µg/m³" />
            <MetricCard icon="temp" label="Nhiệt độ" value={formatNumber(latest?.temperature, 1)} unit="°C" />
            <MetricCard icon="drop" label="Độ ẩm" value={formatNumber(latest?.humidity, 0)} unit="%" />
            <MetricCard icon="co2" label="CO₂" value={formatNumber(latest?.co2, 0)} unit="ppm" note="mô phỏng" />
            <MetricCard
              icon="pulse"
              label="Dự báo giờ tới"
              value={formatNumber(nextForecast?.pm25, 1)}
              unit="µg/m³"
              note={!nextForecast ? "chưa có dự báo" : nextForecast.aqi != null ? `AQI ${formatNumber(nextForecast.aqi, 0)}` : forecastIsMock ? "dự báo mẫu" : ""}
              tone="forecast"
            />
          </div>
        </section>

        <section className="card chart-card">
          <div className="chart-head">
            <h2 className="chart-title--forecast">PM2.5: 24 giờ qua và dự báo AI 24 giờ tới</h2>
            {forecastAt && (
              <span className={`forecast-meta${forecastStale ? " forecast-meta--stale" : ""}`}>
                {forecastIsMock ? "Dự báo mẫu" : `Dự báo lúc ${formatTime(forecastAt)}`}
                {forecastStale && !forecastIsMock ? " · đã cũ, chờ lần chạy mới" : ""}
              </span>
            )}
          </div>
          {series.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={series}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eef2ea" />
                <XAxis dataKey="t" type="number" scale="time" domain={[(min) => Math.min(min, nowMs), "dataMax"]} tickFormatter={formatHour} stroke="#84a06a" minTickGap={28} />
                <YAxis stroke="#84a06a" width={36} />
                <Tooltip labelFormatter={formatTime} formatter={(v) => `${formatNumber(v, 1)} µg/m³`} contentStyle={{ borderRadius: 14, border: "1px solid #fef3c7" }} />
                <Legend />
                <ReferenceLine x={nowMs} stroke="#94a3b8" strokeDasharray="4 4" label={{ value: "Bây giờ", position: "insideTopLeft", fill: "#64748b", fontSize: 11 }} />
                <ReferenceLine y={alertConfig.pm25_threshold} stroke="#dc2626" strokeDasharray="6 4" label={{ value: `Ngưỡng ${alertConfig.pm25_threshold}`, position: "insideTopRight", fill: "#dc2626", fontSize: 11 }} />
                <Line type="monotone" dataKey="actual" name="PM2.5 thực tế (TB theo giờ)" stroke="#65a30d" strokeWidth={3} dot={false} connectNulls />
                <Line type="monotone" dataKey="forecast" name="PM2.5 dự báo" stroke="#ca8a04" strokeWidth={3} strokeDasharray="7 5" dot={false} connectNulls />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <p className="empty-text">Chưa có dữ liệu 24 giờ qua và dự báo — chạy <code>ai/predict.py</code> để tạo dự báo đầu tiên.</p>
          )}
          {hourly.length === 0 && series.length > 0 && (
            <p className="empty-text">Chưa có số đo nào trong 24 giờ qua (node đang tắt?) — biểu đồ chỉ hiển thị phần dự báo.</p>
          )}
          {!forecast && series.length > 0 && (
            <p className="empty-text">Chưa có dự báo cho node này — chạy <code>ai/predict.py</code> để tạo dự báo đầu tiên.</p>
          )}
        </section>

        <section className="chart-row">
          <div className="card chart-card">
            <h2>Bụi mịn gần đây</h2>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={history}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eef2ea" />
                <XAxis dataKey="timestamp" hide />
                <YAxis stroke="#84a06a" width={36} />
                <Tooltip labelFormatter={formatTime} contentStyle={{ borderRadius: 14, border: "1px solid #ecfccb" }} />
                <Legend />
                <Line type="monotone" dataKey="pm25" name="PM2.5 (µg/m³)" stroke="#65a30d" strokeWidth={3} dot={false} />
                <Line type="monotone" dataKey="pm10" name="PM10 (µg/m³)" stroke="#a3a3a3" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="card chart-card">
            <h2 className="chart-title--climate">Nhiệt độ &amp; Độ ẩm</h2>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={history}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eef2ea" />
                <XAxis dataKey="timestamp" hide />
                <YAxis yAxisId="temp" stroke="#ea580c" unit="°C" width={48} domain={[(min) => Math.floor(min - 2), (max) => Math.ceil(max + 2)]} allowDecimals={false} />
                <YAxis yAxisId="hum" orientation="right" stroke="#0284c7" unit="%" width={56} domain={[0, 100]} />
                <Tooltip labelFormatter={formatTime} contentStyle={{ borderRadius: 14, border: "1px solid #e0f2fe" }} />
                <Legend />
                <Line yAxisId="temp" type="monotone" dataKey="temperature" name="Nhiệt độ (°C)" stroke="#ea580c" strokeWidth={2.5} dot={false} />
                <Line yAxisId="hum" type="monotone" dataKey="humidity" name="Độ ẩm (%)" stroke="#0284c7" strokeWidth={2.5} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>

        <section className="chart-row">
          <div className="card chart-card">
            <h2 className="chart-title--alert">Cảnh báo gần đây</h2>
            {alerts.length === 0 ? (
              <p className="empty-text">Chưa có cảnh báo nào — không khí chưa vượt ngưỡng.</p>
            ) : (
              <ul className="alert-list">
                {alerts.slice(0, 6).map((a) => (
                  <li key={a.id} className="alert-item">
                    <span className="alert-dot" />
                    <span className="alert-text">
                      <strong>{METRIC_LABEL[a.metric] || a.metric} {formatNumber(a.value, a.metric === "aqi" ? 0 : 1)}{METRIC_UNIT[a.metric] || ""}</strong>
                      {" "}vượt ngưỡng {formatNumber(a.threshold, 0)}
                    </span>
                    <span className="alert-time">{formatTime(a.triggered_at)}</span>
                  </li>
                ))}
              </ul>
            )}
            {backendAlerts === false && !usingMock && (
              <p className="hint-text">Backend chưa có API cảnh báo — danh sách đang do Dashboard tự ghi nhận.</p>
            )}
          </div>

          <form className="card chart-card alert-config" onSubmit={submitConfig}>
            <h2 className="chart-title--alert">Ngưỡng cảnh báo</h2>
            <label className="field">
              <span>PM2.5 (µg/m³)</span>
              <input type="number" min="1" step="0.1" value={configDraft.pm25_threshold}
                onChange={(e) => setConfigDraft((d) => ({ ...d, pm25_threshold: e.target.value }))} />
            </label>
            <label className="field">
              <span>AQI</span>
              <input type="number" min="1" step="1" value={configDraft.aqi_threshold}
                onChange={(e) => setConfigDraft((d) => ({ ...d, aqi_threshold: e.target.value }))} />
            </label>
            <p className="hint-text">Mặc định PM2.5 = 55 µg/m³ (mức "Xấu" theo US EPA), AQI = 100.</p>
            <div className="form-actions">
              <button type="submit" className="btn btn--primary">Lưu ngưỡng</button>
              <button type="button" className="btn" onClick={runTestAlert}>Thử cảnh báo</button>
            </div>
            {configStatus && <p className="hint-text">{configStatus}</p>}
          </form>
        </section>
      </div>
    </div>
  );
}

// Mức AQI theo thang US EPA (khớp backend/app/aqi.py), nhãn và khuyến nghị tiếng Việt
const AQI_LEVELS = [
  { max: 50, label: "Tốt", bg: "#dcfce7", fg: "#166534", advice: "Không khí trong lành, thoải mái hoạt động ngoài trời." },
  { max: 100, label: "Trung bình", bg: "#fef08a", fg: "#713f12", advice: "Chấp nhận được. Người nhạy cảm nên hạn chế ở ngoài trời lâu." },
  { max: 150, label: "Kém", bg: "#fed7aa", fg: "#7c2d12", advice: "Không tốt cho người nhạy cảm (trẻ nhỏ, người già, người bệnh hô hấp)." },
  { max: 200, label: "Xấu", bg: "#fecaca", fg: "#7f1d1d", advice: "Mọi người nên hạn chế ra ngoài, đeo khẩu trang khi cần thiết." },
  { max: 300, label: "Rất xấu", bg: "#e9d5ff", fg: "#581c87", advice: "Cảnh báo sức khoẻ: tránh hoạt động ngoài trời." },
  { max: Infinity, label: "Nguy hại", bg: "#fecdd3", fg: "#4c0519", advice: "Khẩn cấp: ở trong nhà, đóng cửa sổ." },
];

function aqiLevel(aqi) {
  if (aqi === null || aqi === undefined || Number.isNaN(Number(aqi))) return null;
  return AQI_LEVELS.find((lvl) => Number(aqi) <= lvl.max);
}

const ICON_PATHS = {
  leaf: <><path d="M5 19c0-8 6-14 14-14 0 8-6 14-14 14z" /><path d="M5 19l7-7" /></>,
  dust: <><circle cx="7" cy="8" r="1.6" /><circle cx="15" cy="6" r="1.2" /><circle cx="12" cy="13" r="2" /><circle cx="18" cy="15" r="1.4" /><circle cx="7" cy="17" r="1.2" /></>,
  temp: <><path d="M10 4a2 2 0 0 1 4 0v9.5a4 4 0 1 1-4 0z" /><path d="M12 10v6" /></>,
  drop: <path d="M12 3c3.5 4.5 6 8 6 11a6 6 0 0 1-12 0c0-3 2.5-6.5 6-11z" />,
  co2: <><circle cx="8" cy="12" r="4" /><circle cx="16" cy="9" r="3" /><circle cx="16.5" cy="16" r="2.5" /></>,
  pulse: <path d="M3 12h4l2-5 4 10 2-5h6" />,
};

function Icon({ name, color = "#4d7c0f" }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {ICON_PATHS[name]}
    </svg>
  );
}

function MetricCard({ icon, label, value, unit, note, tone }) {
  const forecastTone = tone === "forecast";
  return (
    <div className={`card metric-card${forecastTone ? " metric-card--forecast" : ""}`}>
      <div className="metric-head">
        <Icon name={icon} color={forecastTone ? "#a16207" : "#4d7c0f"} />
        <span className="metric-label">{label}</span>
      </div>
      <div>
        <span className="metric-value">{value}</span>
        {value !== "—" && <span className="metric-unit">{unit}</span>}
      </div>
      {note && <div className="metric-note">{note}</div>}
    </div>
  );
}

// Nhãn trục thời gian dạng "16:00"
function formatHour(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
}

// Hiển thị thời điểm trong tooltip biểu đồ theo giờ Việt Nam, ví dụ "16:45 14/10"
function formatTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("vi-VN", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit" });
}
