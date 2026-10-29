const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function getLatestReadingForDevice(deviceId) {
  const res = await fetch(`${API_BASE_URL}/api/readings/latest`);
  if (!res.ok) throw new Error("Không lấy được dữ liệu mới nhất");
  const data = await res.json();
  const items = data.items || [];
  // /api/readings/latest trả về bản ghi mới nhất của MỌI node (xem mqtt_data_contract.md)
  // -> Dashboard chỉ hiển thị 1 node nên phải tự lọc đúng device_id ở đây.
  return items.find((item) => item.device_id === deviceId) || null;
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

// Lấy số đo từ một thời điểm trở đi (dùng cho biểu đồ 24 giờ qua + dự báo)
export async function getReadingsSince(deviceId, fromDate, limit = 5000) {
  const params = new URLSearchParams({ device_id: deviceId, from: fromDate.toISOString(), limit });
  const res = await fetch(`${API_BASE_URL}/api/readings?${params}`);
  if (!res.ok) throw new Error("Không lấy được dữ liệu 24 giờ qua");
  return res.json();
}

// ---------- Cảnh báo (định dạng xem iot/mqtt_data_contract.md mục 2.7, 2.8) ----------

// Trả null nếu Backend chưa có API này (404) để Dashboard tự phát hiện vượt ngưỡng thay thế
export async function getAlerts(deviceId, limit = 20) {
  const params = new URLSearchParams({ device_id: deviceId, limit });
  const res = await fetch(`${API_BASE_URL}/api/alerts?${params}`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error("Không lấy được danh sách cảnh báo");
  const data = await res.json();
  return data.items || [];
}

export async function getAlertConfig(deviceId) {
  const params = new URLSearchParams({ device_id: deviceId });
  const res = await fetch(`${API_BASE_URL}/api/alerts/config?${params}`);
  if (!res.ok) throw new Error("Không lấy được ngưỡng cảnh báo");
  return res.json();
}

export async function saveAlertConfig(config) {
  const res = await fetch(`${API_BASE_URL}/api/alerts/config`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  if (!res.ok) throw new Error("Không lưu được ngưỡng cảnh báo");
  return res.json();
}
