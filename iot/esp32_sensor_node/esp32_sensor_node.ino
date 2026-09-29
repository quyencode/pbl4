/*
  PBL4 - Node cảm biến chất lượng không khí (ESP32)
  Đọc thật: nhiệt độ/độ ẩm (DHT11), PM2.5/PM10 (PMS5003)
  Mô phỏng (không dùng cảm biến thật): CO2
  Fallback: nếu PMS5003 chưa cắm/chưa về hàng, PM2.5/PM10 tạm dùng dữ liệu mô phỏng
    để không đứt luồng dữ liệu — tự chuyển sang đọc thật ngay khi cảm biến có tín hiệu
    (xem readAllSensors()).
    - Xem chi tiết trong iot/mqtt_data_contract.md
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

// PMS5003 giao tiếp UART (9600 baud) — dùng UART1 của ESP32
#define PMS_RX_PIN 16   // nối vào chân TX của PMS5003
#define PMS_TX_PIN 17   // nối vào chân RX của PMS5003 (không bắt buộc nếu chỉ đọc)
HardwareSerial pmsSerial(1);

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
float mockPM25Baseline = 25.0;  // µg/m3 — CHỈ dùng khi PMS5003 chưa cắm/chưa về hàng (xem readAllSensors())
float mockCO2Baseline  = 420.0; // ppm, mức nền ngoài trời — CO2 luôn mô phỏng (chưa mua MH-Z19B)

// true kể từ lần đầu tiên đọc được frame PMS5003 hợp lệ -> từ đó luôn ưu tiên dữ liệu thật,
// không bao giờ quay lại dùng mock nữa (tránh dữ liệu "nhảy" giữa thật/ảo khi cắm cảm biến xong)
bool pmsHardwareDetected = false;

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

// ====== ĐỌC PMS5003 THẬT (UART) ======
// Frame PMS5003: 32 byte, bắt đầu bằng 0x42 0x4D, có checksum ở 2 byte cuối.
// Lấy PM2.5/PM10 ở giá trị "atmospheric environment" (byte 12-13, 14-15).
// Lưu ý: PMS5003 cần ~30s làm nóng sau khi cấp nguồn thì số liệu mới ổn định.
bool readPMS5003(float &pm25, float &pm10) {
  if (pmsSerial.available() < 32) return false; // chưa đủ dữ liệu, chờ vòng đọc sau

  if (pmsSerial.peek() != 0x42) {
    pmsSerial.read(); // byte rác, bỏ đi để đồng bộ lại khung
    return false;
  }

  uint8_t buf[32];
  pmsSerial.readBytes(buf, 32);

  if (buf[0] != 0x42 || buf[1] != 0x4D) return false;

  uint16_t checksum = 0;
  for (int i = 0; i < 30; i++) checksum += buf[i];
  uint16_t checksumRecv = (buf[30] << 8) | buf[31];
  if (checksum != checksumRecv) return false; // frame lỗi, bỏ qua lần đọc này

  pm25 = (buf[12] << 8) | buf[13];
  pm10 = (buf[14] << 8) | buf[15];
  return true;
}

// ====== MÔ PHỎNG CO2 (KHÔNG dùng cảm biến MH-Z19B thật) ======
// Random walk quanh 1 giá trị nền, có thêm dao động nhẹ theo giờ trong ngày
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
    pmsHardwareDetected = true; // đã có ít nhất 1 lần đọc thật -> từ nay luôn ưu tiên đọc thật
  } else if (!pmsHardwareDetected) {
    // PMS5003 chưa cắm/chưa về hàng -> tạm sinh dữ liệu mô phỏng để không đứt luồng dữ liệu
    // (cùng thuật toán random-walk như bản mô phỏng cũ), sẽ tự ngừng ngay khi cắm cảm biến thật
    mockPM25Baseline += random(-30, 31) / 10.0;
    if (random(0, 1000) < 5) mockPM25Baseline += random(15, 40);
    mockPM25Baseline = constrain(mockPM25Baseline, 5.0, 150.0);
    latestPM25 = mockPM25Baseline;
    latestPM10 = mockPM25Baseline * (1.3 + random(0, 50) / 100.0);
  }
  // nếu đã pmsHardwareDetected=true mà lần đọc này lỗi tạm thời (frame rác/thiếu byte) thì
  // giữ nguyên latestPM25/latestPM10 gần nhất, không rơi về mock nữa

  int co2;
  if (readMHZ19B(co2)) {
    latestCO2 = co2;
  }

  float t = dht.readTemperature();
  float h = dht.readHumidity();
  if (!isnan(t)) latestTemp = t;
  if (!isnan(h)) latestHumidity = h;

  Serial.printf("PM2.5=%.1f PM10=%.1f CO2=%d T=%.1f H=%.1f (PM/PM10: %s | CO2 la du lieu mo phong)\n",
                latestPM25, latestPM10, latestCO2, latestTemp, latestHumidity,
                pmsHardwareDetected ? "that" : "mo phong tam (cho PMS5003)");
}

String buildPayload() {
  StaticJsonDocument<256> doc;
  doc["device_id"] = DEVICE_ID;
  doc["pm25"] = isnan(latestPM25) ? nullptr : latestPM25;   // PMS5003 thật (hoặc mô phỏng tạm nếu chưa cắm - xem readAllSensors())
  doc["pm10"] = isnan(latestPM10) ? nullptr : latestPM10;   // PMS5003 thật (hoặc mô phỏng tạm nếu chưa cắm - xem readAllSensors())
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
  pmsSerial.begin(9600, SERIAL_8N1, PMS_RX_PIN, PMS_TX_PIN);
  randomSeed(analogRead(0)); // hạt giống ngẫu nhiên cho dữ liệu mô phỏng CO2 (chân bỏ trống, không đấu gì)

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
