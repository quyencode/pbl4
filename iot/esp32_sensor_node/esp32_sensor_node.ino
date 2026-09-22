/*
  PBL4 - Node cảm biến chất lượng không khí (ESP32)
  Đọc: PM2.5/PM10 (PMS5003), CO2 (MH-Z19B), nhiệt độ/độ ẩm (DHT22)
  Gửi dữ liệu qua MQTT theo định dạng trong iot/mqtt_data_contract.md

  Thư viện cần cài (Arduino IDE > Library Manager):
    - PubSubClient      (MQTT)
    - ArduinoJson        (đóng gói JSON)
    - DHT sensor library (Adafruit)
    - SoftwareSerial hoặc HardwareSerial cho PMS5003 / MH-Z19B

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
#define DHTTYPE  DHT22
DHT dht(DHTPIN, DHTTYPE);

// PMS5003 và MH-Z19B dùng UART - khai báo Serial2 (RX=16, TX=17) làm ví dụ
HardwareSerial PMSSerial(1);
HardwareSerial CO2Serial(2);

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

// Giá trị đọc gần nhất
float latestPM25 = NAN, latestPM10 = NAN;
int   latestCO2  = -1;
float latestTemp = NAN, latestHumidity = NAN;

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

// TODO: thay bằng code đọc thật theo protocol của PMS5003 (UART, 32-byte frame)
bool readPMS5003(float &pm25, float &pm10) {
  // Khung sườn - cần cài đặt đọc & parse frame thật từ PMSSerial
  // Tham khảo datasheet PMS5003: mở đầu 0x42 0x4D, checksum cuối frame
  return false; // trả về true khi đọc thành công
}

// TODO: thay bằng code đọc thật theo protocol UART của MH-Z19B
bool readMHZ19B(int &co2ppm) {
  // Gửi lệnh đọc 0xFF 0x01 0x86 0x00 0x00 0x00 0x00 0x00 0x79 tới CO2Serial
  // rồi đọc 9 byte phản hồi và tính CO2 = byte[2]*256 + byte[3]
  return false;
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

  Serial.printf("PM2.5=%.1f PM10=%.1f CO2=%d T=%.1f H=%.1f\n",
                latestPM25, latestPM10, latestCO2, latestTemp, latestHumidity);
}

String buildPayload() {
  StaticJsonDocument<256> doc;
  doc["device_id"] = DEVICE_ID;
  doc["pm25"] = isnan(latestPM25) ? nullptr : latestPM25;
  doc["pm10"] = isnan(latestPM10) ? nullptr : latestPM10;
  doc["co2"] = latestCO2;
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
  PMSSerial.begin(9600, SERIAL_8N1, 16, 17);
  CO2Serial.begin(9600, SERIAL_8N1, 25, 26);

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
