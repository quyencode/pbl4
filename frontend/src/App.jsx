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

        <section className="aqi-ring-wrap">
          <div className="aqi-ring">
            <div className="aqi-ring-value">{formatNumber(latest?.aqi, 0)}</div>
            <div className="aqi-ring-label">Chỉ số AQI</div>
          </div>
          {latest && latest.aqi == null && (
            <p className="aqi-ring-hint">Chờ Backend/AI tính AQI (chưa có trong /api/readings)</p>
          )}
        </section>

        <section className="mini-stat-row">
          <StatCard icon="🌿" label="PM2.5 (µg/m³)" value={formatNumber(latest?.pm25, 1)} />
          <StatCard
            icon={isLive ? "✅" : "⏳"}
            label="Trạng thái"
            value={latest ? "Đang hoạt động" : "Chưa có dữ liệu"}
          />
        </section>

        <section className="card chart-card">
          <h2>Xu hướng tuần này (AQI / PM2.5)</h2>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={history}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eef2ea" />
              <XAxis dataKey="timestamp" hide />
              <YAxis stroke="#84a06a" />
              <Tooltip contentStyle={{ borderRadius: 14, border: "1px solid #ecfccb" }} />
              <Legend />
              <Line type="monotone" dataKey="pm25" name="PM2.5 thực tế" stroke="#65a30d" strokeWidth={3} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </section>

        <section className="card chart-card">
          <h2 className="chart-title--forecast">Dự báo AI (24 giờ tới)</h2>
          {forecast ? (
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={forecast.predictions}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eef2ea" />
                <XAxis dataKey="timestamp" hide />
                <YAxis stroke="#84a06a" />
                <Tooltip contentStyle={{ borderRadius: 14, border: "1px solid #fef3c7" }} />
                <Legend />
                <Line type="monotone" dataKey="pm25" name="PM2.5 dự báo" stroke="#eab308" strokeWidth={3} strokeDasharray="7 5" dot={false} />
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

function StatCard({ icon, label, value }) {
  return (
    <div className="mini-stat">
      <span className="mini-stat-icon">{icon}</span>
      <div>
        <div className="mini-stat-label">{label}</div>
        <div className="mini-stat-value">{value}</div>
      </div>
    </div>
  );
}
