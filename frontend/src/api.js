const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function getLatestReadings() {
  const res = await fetch(`${API_BASE_URL}/api/readings/latest`);
  if (!res.ok) throw new Error("Không lấy được dữ liệu mới nhất");
  return res.json();
}

export async function getReadingsHistory(deviceId, limit = 168) {
  const params = new URLSearchParams({ device_id: deviceId, limit });
  const res = await fetch(`${API_BASE_URL}/api/readings?${params}`);
  if (!res.ok) throw new Error("Không lấy được dữ liệu lịch sử");
  return res.json();
}

export async function getLatestForecast(deviceId) {
  const params = new URLSearchParams({ device_id: deviceId });
  const res = await fetch(`${API_BASE_URL}/api/forecasts/latest?${params}`);
  if (!res.ok) return null; // có thể chưa có dự báo nào
  return res.json();
}

export function connectLiveSocket(onMessage) {
  const wsUrl = API_BASE_URL.replace(/^http/, "ws") + "/ws/live";
  const socket = new WebSocket(wsUrl);
  socket.onmessage = (event) => onMessage(JSON.parse(event.data));
  return socket;
}
