/*
  PBL4 - Node cảm biến chất lượng không khí (ESP32)
  Đọc thật: nhiệt độ/độ ẩm (DHT11)
  Mô phỏng (không dùng cảm biến thật do giới hạn ngân sách): PM2.5/PM10, CO2
    - Xem lý do & giới hạn trong iot/mqtt_data_contract.md và báo cáo, mục "Giới hạn đề tài"
  Gửi dữ liệu qua MQTT theo định dạng trong iot/mqtt_data_contract.md

  Thư viện cần cài (Arduino IDE > Library Manager):
    - PubSubClient      (MQTT)
    - ArduinoJson        (đóng gói JSON)
    - DHT sensor library (Adafruit)

  Đây là bộ khung (skeleton) - cần chỉnh sửa theo linh kiện & chân cắm thực tế.
*/

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <DHT.h>

// ====== CẤU HÌNH THIẾT BỊ - CHỈNH THEO TỪNG NODE ======
const char* DEVICE_ID       = "node-01";
const char* WIFI_SSID       = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD   = "YOUR_WIFI_PASSWORD";
const char* MQTT_BROKER     = "192.168.1.100";   // IP máy chạy Mosquitto
const int   MQTT_PORT       = 1883;
const int   READ_INTERVAL_MS = 30000;  // đọc cảm biến mỗi 30s
const int   SEND_INTERVAL_MS = 300000; // gửi lên server mỗi 5 phút

// ====== CHÂN CẮM - CHỈNH THEO SƠ ĐỒ ĐẤU NỐI THỰC TẾ ======
#define DHTPIN   4
#define DHTTYPE  DHT11
DHT dht(DHTPIN, DHTTYPE);

WiFiClient espClient;
PubSubClient mqttClient(espClient);

char mqttTopic[64];

// Bộ đệm dữ liệu cục bộ khi mất mạng (mảng vòng đơn giản)
#define BUFFER_SIZE 50
String dataBuffer[BUFFER_SIZE];
int bufferHead = 0;
int bufferCount = 0;

unsigned long lastReadTime = 0;
unsigned long lastSendTime = 0;

// Giá trị đọc/mô phỏng gần nhất
float latestPM25 = NAN, latestPM10 = NAN;
int   latestCO2  = -1;
float latestTemp = NAN, latestHumidity = NAN;

// Giá trị nền dùng để random-walk cho dữ liệu mô phỏng (giữ trạng thái giữa các lần đọc)
float mockPM25Baseline = 25.0;  // µg/m3, điển hình đô thị VN
float mockCO2Baseline  = 420.0; // ppm, mức nền ngoài trời

void setupWiFi() {
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Đang kết nối WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi đã kết nối, IP: " + WiFi.localIP().toString());
}

void reconnectMQTT() {
  while (!mqttClient.connected()) {
    Serial.println("Đang kết nối MQTT broker...");
    String clientId = String("esp32-") + DEVICE_ID;
    if (mqttClient.connect(clientId.c_str())) {
      Serial.println("Đã kết nối MQTT.");
    } else {
      Serial.println("Kết nối MQTT thất bại, thử lại sau 5s.");
      delay(5000);
    }
  }
}

// ====== MÔ PHỎNG PM2.5/PM10 (KHÔNG dùng cảm biến PMS5003 thật) ======
// Lý do: cắt giảm ngân sách đề tài - xem "Giới hạn đề tài" trong báo cáo.
// Thuật toán: random walk quanh 1 giá trị nền + thỉnh thoảng có "đợt tăng đột biến"
// để dữ liệu có hình dạng gần giống thật, thay vì random thuần (dễ làm hỏng việc train AI).
// Giữ nguyên tên hàm readPMS5003() để không phải sửa readAllSensors() hay các tài liệu khác.
bool readPMS5003(float &pm25, float &pm10) {
  mockPM25Baseline += random(-30, 31) / 10.0;                  // bước đi ngẫu nhiên nhỏ (~-3.0 .. +3.0)
  if (random(0, 1000) < 5) mockPM25Baseline += random(15, 40); // ~0.5%/lần đọc: đợt tăng đột biến (giả lập ô nhiễm)
  mockPM25Baseline = constrain(mockPM25Baseline, 5.0, 150.0);

  pm25 = mockPM25Baseline;
  pm10 = mockPM25Baseline * (1.3 + random(0, 50) / 100.0);     // PM10 luôn >= PM2.5 (hệ số 1.3-1.8)
  return true; // luôn thành công vì là dữ liệu mô phỏng, không phụ thuộc phần cứng
}

// ====== MÔ PHỎNG CO2 (KHÔNG dùng cảm biến MH-Z19B thật) ======
// Cùng lý do và thuật toán như trên, có thêm dao động nhẹ theo giờ trong ngày
// (giả lập CO2 tăng vào ban ngày do hoạt động/giao thông).
bool readMHZ19B(int &co2ppm) {
  float hourOfDay = millis() / 3600000.0;
  float dayCycle = sin(hourOfDay * 2 * PI / 24.0) * 40;
  mockCO2Baseline += random(-20, 21) + dayCycle * 0.05;
  if (random(0, 1000) < 5) mockCO2Baseline += random(150, 400); // đợt tăng đột biến
  mockCO2Baseline = constrain(mockCO2Baseline, 380.0, 2000.0);

  co2ppm = (int)mockCO2Baseline;
  return true;
}

void readAllSensors() {
  float pm25, pm10;
  if (readPMS5003(pm25, pm10)) {
    latestPM25 = pm25;
    latestPM10 = pm10;
  }

  int co2;
  if (readMHZ19B(co2)) {
    latestCO2 = co2;
  }

  float t = dht.readTemperature();
  float h = dht.readHumidity();
  if (!isnan(t)) latestTemp = t;
  if (!isnan(h)) latestHumidity = h;

  Serial.printf("PM2.5=%.1f PM10=%.1f CO2=%d T=%.1f H=%.1f (PM/CO2 la du lieu mo phong)\n",
                latestPM25, latestPM10, latestCO2, latestTemp, latestHumidity);
}

String buildPayload() {
  StaticJsonDocument<256> doc;
  doc["device_id"] = DEVICE_ID;
  doc["pm25"] = isnan(latestPM25) ? nullptr : latestPM25;   // mô phỏng - xem mqtt_data_contract.md
  doc["pm10"] = isnan(latestPM10) ? nullptr : latestPM10;   // mô phỏng - xem mqtt_data_contract.md
  doc["co2"] = latestCO2;                                    // mô phỏng - xem mqtt_data_contract.md
  doc["temperature"] = isnan(latestTemp) ? nullptr : latestTemp;
  doc["humidity"] = isnan(latestHumidity) ? nullptr : latestHumidity;
  // TODO: gắn timestamp thật (NTP) - hiện để backend tự gắn giờ nhận nếu thiếu
  doc["timestamp"] = "";

  String payload;
  serializeJson(doc, payload);
  return payload;
}

void bufferPush(const String &payload) {
  dataBuffer[(bufferHead + bufferCount) % BUFFER_SIZE] = payload;
  if (bufferCount < BUFFER_SIZE) {
    bufferCount++;
  } else {
    bufferHead = (bufferHead + 1) % BUFFER_SIZE; // ghi đè bản cũ nhất khi đầy
  }
}

void flushBuffer() {
  while (bufferCount > 0 && mqttClient.connected()) {
    String payload = dataBuffer[bufferHead];
    if (mqttClient.publish(mqttTopic, payload.c_str())) {
      bufferHead = (bufferHead + 1) % BUFFER_SIZE;
      bufferCount--;
    } else {
      break; // dừng nếu gửi lỗi, thử lại ở vòng lặp sau
    }
  }
}

void setup() {
  Serial.begin(115200);
  dht.begin();
  randomSeed(analogRead(0)); // hạt giống ngẫu nhiên cho dữ liệu mô phỏng PM/CO2 (chân bỏ trống, không đấu gì)

  snprintf(mqttTopic, sizeof(mqttTopic), "sensors/%s/data", DEVICE_ID);

  setupWiFi();
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    setupWiFi();
  }
  if (!mqttClient.connected()) {
    reconnectMQTT();
  }
  mqttClient.loop();

  unsigned long now = millis();

  if (now - lastReadTime >= READ_INTERVAL_MS) {
    lastReadTime = now;
    readAllSensors();
  }

  if (now - lastSendTime >= SEND_INTERVAL_MS) {
    lastSendTime = now;
    String payload = buildPayload();

    if (mqttClient.connected()) {
      flushBuffer(); // gửi bù dữ liệu tồn đọng trước
      mqttClient.publish(mqttTopic, payload.c_str());
      Serial.println("Đã gửi: " + payload);
    } else {
      bufferPush(payload); // mất mạng -> lưu vào bộ đệm
      Serial.println("Mất kết nối - đã lưu vào buffer.");
    }
  }
}
