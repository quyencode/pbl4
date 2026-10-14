import React, { useEffect, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { getLatestReadingForDevice, getReadingsHistory, getLatestForecast, connectLiveSocket } from "./api.js";
import { MOCK_LATEST, MOCK_HISTORY } from "./mockData.js";
import "./App.css";

const DEFAULT_DEVICE_ID = "node-01";
const MAX_HISTORY_POINTS = 168; // khớp mặc định limit của getReadingsHistory (7 ngày * 24h)

// Task D4.2: làm tròn số liệu hiển thị về 1 chữ số thập phân, giữ "—" khi chưa có dữ liệu
function formatNumber(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return Number(value).toFixed(digits);
}

export default function App() {
  const [latest, setLatest] = useState(null);
  const [history, setHistory] = useState([]);
  const [forecast, setForecast] = useState(null);
  const [loading, setLoading] = useState(true);
  const [usingMock, setUsingMock] = useState(false);
  const [noRealDataYet, setNoRealDataYet] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function loadInitialData() {
      const [latestResult, historyResult] = await Promise.allSettled([
        getLatestReadingForDevice(DEFAULT_DEVICE_ID),
        getReadingsHistory(DEFAULT_DEVICE_ID),
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

      setLoading(false);
    }

    loadInitialData();

    getLatestForecast(DEFAULT_DEVICE_ID)
      .then((f) => !cancelled && setForecast(f))
      .catch(() => {});

    // Realtime: mỗi message từ /ws/live có cùng cấu trúc 1 item của /api/readings,
    // kèm device_id (xem mqtt_data_contract.md) - chỉ cập nhật nếu đúng node đang xem.
    const socket = connectLiveSocket((data) => {
      if (data.device_id !== DEFAULT_DEVICE_ID) return;
      setLatest(data);
      setUsingMock(false);
      setNoRealDataYet(false);
      setHistory((prev) => [...prev.slice(-(MAX_HISTORY_POINTS - 1)), data]);
    });
    socket.onerror = () => {
      // Backend/WS chưa chạy -> bỏ qua, không phải lỗi hiển thị
    };

    return () => {
      cancelled = true;
      socket.close();
    };
  }, []);

  const isLive = Boolean(latest) && !usingMock;
  const level = aqiLevel(latest?.aqi);
  const nextForecast = forecast?.predictions?.[0];

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
          <span className={`status-pill ${isLive ? "status-pill--live" : "status-pill--idle"}`}>
            <span className="status-dot" />
            {isLive ? "Đang hoạt động" : "Chưa có dữ liệu"}
          </span>
        </header>

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
              note={nextForecast?.aqi != null ? `AQI ${nextForecast.aqi}` : "chưa có dự báo"}
              tone="forecast"
            />
          </div>
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
                <YAxis yAxisId="temp" stroke="#ea580c" unit="°C" width={48} domain={["dataMin - 2", "dataMax + 2"]} allowDecimals={false} />
                <YAxis yAxisId="hum" orientation="right" stroke="#0284c7" unit="%" width={56} domain={[0, 100]} />
                <Tooltip labelFormatter={formatTime} contentStyle={{ borderRadius: 14, border: "1px solid #e0f2fe" }} />
                <Legend />
                <Line yAxisId="temp" type="monotone" dataKey="temperature" name="Nhiệt độ (°C)" stroke="#ea580c" strokeWidth={2.5} dot={false} />
                <Line yAxisId="hum" type="monotone" dataKey="humidity" name="Độ ẩm (%)" stroke="#0284c7" strokeWidth={2.5} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>

        <section className="card chart-card">
          <h2 className="chart-title--forecast">Dự báo AI (24 giờ tới)</h2>
          {forecast ? (
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={forecast.predictions}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eef2ea" />
                <XAxis dataKey="timestamp" hide />
                <YAxis stroke="#84a06a" width={36} />
                <Tooltip labelFormatter={formatTime} contentStyle={{ borderRadius: 14, border: "1px solid #fef3c7" }} />
                <Legend />
                <Line type="monotone" dataKey="pm25" name="PM2.5 dự báo (µg/m³)" stroke="#ca8a04" strokeWidth={3} strokeDasharray="7 5" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <p className="empty-text">Chưa có dữ liệu dự báo — chạy <code>ai/predict.py</code> để tạo dự báo đầu tiên.</p>
          )}
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

// Hiển thị thời điểm trong tooltip biểu đồ theo giờ Việt Nam, ví dụ "16:45 14/10"
function formatTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("vi-VN", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit" });
}
