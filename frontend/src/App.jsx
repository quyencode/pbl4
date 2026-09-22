import React, { useEffect, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { getLatestReadings, getReadingsHistory, getLatestForecast, connectLiveSocket } from "./api.js";

const DEFAULT_DEVICE_ID = "node-01";

export default function App() {
  const [latest, setLatest] = useState(null);
  const [history, setHistory] = useState([]);
  const [forecast, setForecast] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    // Tải dữ liệu ban đầu
    getLatestReadings().then(setLatest).catch((e) => setError(e.message));
    getReadingsHistory(DEFAULT_DEVICE_ID)
      .then((res) => setHistory(res.items))
      .catch((e) => setError(e.message));
    getLatestForecast(DEFAULT_DEVICE_ID).then(setForecast).catch(() => {});

    // Kết nối realtime - TODO: cập nhật `history`/`latest` khi có message mới
    const socket = connectLiveSocket((data) => {
      console.log("Dữ liệu realtime:", data);
      // TODO: setHistory((prev) => [...prev.slice(-167), data]);
    });
    return () => socket.close();
  }, []);

  return (
    <div style={{ fontFamily: "sans-serif", maxWidth: 960, margin: "0 auto", padding: 24 }}>
      <h1>Giám sát &amp; Dự báo Chất lượng Không khí</h1>

      {error && <p style={{ color: "red" }}>Lỗi: {error} (backend đã chạy chưa?)</p>}

      <section style={{ display: "flex", gap: 16, marginBottom: 32 }}>
        <StatCard title="AQI hiện tại" value={latest?.aqi ?? "—"} />
        <StatCard title="PM2.5 (µg/m³)" value={latest?.pm25 ?? "—"} />
        <StatCard title="Trạng thái" value={latest ? "Đang hoạt động" : "Chưa có dữ liệu"} />
      </section>

      <section style={{ marginBottom: 32 }}>
        <h2>Xu hướng AQI / PM2.5 (lịch sử)</h2>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={history}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="timestamp" hide />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="pm25" name="PM2.5 thực tế" stroke="#2563eb" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </section>

      <section>
        <h2>Dự báo AI (24 giờ tới)</h2>
        {forecast ? (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={forecast.predictions}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="timestamp" hide />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="pm25" name="PM2.5 dự báo" stroke="#dc2626" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <p>Chưa có dữ liệu dự báo — chạy `ai/predict.py` để tạo dự báo đầu tiên.</p>
        )}
      </section>
    </div>
  );
}

function StatCard({ title, value }) {
  return (
    <div style={{ flex: 1, border: "1px solid #e5e7eb", borderRadius: 8, padding: 16 }}>
      <div style={{ fontSize: 13, color: "#6b7280" }}>{title}</div>
      <div style={{ fontSize: 28, fontWeight: 600 }}>{value}</div>
    </div>
  );
}
