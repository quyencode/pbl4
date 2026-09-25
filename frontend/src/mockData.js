// Dữ liệu mẫu (mock) dùng khi backend chưa chạy - Task D2.2, Tuần 2
// Mục đích: cho phép xem trước giao diện Dashboard ngay cả khi
// backend/Docker chưa bật, không phải chờ có dữ liệu thật mới thấy layout.

export const MOCK_LATEST = {
  device_id: "node-01",
  aqi: 55,
  pm25: 32.4,
  pm10: 48.1,
  co2: 610,
  temperature: 29.2,
  humidity: 68,
  timestamp: new Date().toISOString(),
};

// 24 điểm dữ liệu giả lập theo giờ gần nhất, dao động nhẹ quanh mức PM2.5 trung bình
export const MOCK_HISTORY = Array.from({ length: 24 }, (_, i) => {
  const t = new Date(Date.now() - (23 - i) * 60 * 60 * 1000);
  return {
    timestamp: t.toISOString(),
    pm25: Math.round((25 + 15 * Math.sin(i / 4) + Math.random() * 5) * 10) / 10,
  };
});
