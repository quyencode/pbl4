import React, { useEffect, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { getLatestReadingForDevice, getReadingsHistory, getLatestForecast, connectLiveSocket } from "./api.js";
import { MOCK_LATEST, MOCK_HISTORY } from "./mockData.js";

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

  return (
    <div style={{ fontFamily: "sans-serif", maxWidth: 960, margin: "0 auto", padding: 24 }}>
      <h1>Giám sát &amp; Dự báo Chất lượng Không khí </h1>

      {loading && <p>Đang tải dữ liệu…</p>}

      {usingMock && (
        <p style={{ color: "#b45309", background: "#fffbeb", padding: "8px 12px", borderRadius: 6 }}>
          Đang hiển thị dữ liệu mẫu (backend chưa chạy). Chạy <code>docker compose up -d</code> để xem dữ liệu thật.
        </p>
      )}

      {!usingMock && noRealDataYet && (
        <p style={{ color: "#1d4ed8", background: "#eff6ff", padding: "8px 12px", borderRadius: 6 }}>
          Đã kết nối API thật nhưng chưa có dữ liệu cho node <code>{DEFAULT_DEVICE_ID}</code> — kiểm tra xem node
          cảm biến và MQTT subscriber đã publish/ghi dữ liệu chưa.
        </p>
      )}

      <section style={{ display: "flex", flexWrap: "wrap", gap: 16, marginBottom: 32 }}>
        <StatCard
          title="AQI hiện tại"
          value={formatNumber(latest?.aqi, 0)}
          hint={latest && latest.aqi == null ? "Chờ Backend/AI tính AQI (chưa có trong /api/readings)" : undefined}
        />
        <StatCard title="PM2.5 (µg/m³)" value={formatNumber(latest?.pm25, 1)} />
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

function StatCard({ title, value, hint }) {
  return (
    <div
      style={{
        flex: "1 1 160px",
        minWidth: 160,
        border: "1px solid #e5e7eb",
        borderRadius: 8,
        padding: 16,
      }}
    >
      <div style={{ fontSize: 13, color: "#6b7280" }}>{title}</div>
      <div style={{ fontSize: 28, fontWeight: 600 }}>{value}</div>
      {hint && <div style={{ fontSize: 11, color: "#9ca3af", marginTop: 4 }}>{hint}</div>}
    </div>
  );
}
