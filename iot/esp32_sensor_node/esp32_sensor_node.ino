/*
  PBL4 - Node cảm biến chất lượng không khí (ESP32)
  Đọc: PM2.5/PM10 (PMS5003 thật + fallback mô phỏng), CO2 (mô phỏng), DHT11 (thật)
  Gửi dữ liệu qua MQTT theo định dạng trong iot/mqtt_data_contract.md

  Thư viện cần cài (Arduino IDE > Library Manager):
    - PubSubClient       (Nick O'Leary)
    - ArduinoJson        (Benoit Blanchon)
    - DHT sensor library (Adafruit)
    - Adafruit Unified Sensor
    - PMS                (Mariusz Kacki)
    - MHZ19              (Jonathan Dempsey)

  Chân cắm:
    - PMS5003 : RX=16, TX=17 (UART1)
    - MH-Z19B : RX=25, TX=26 (UART2) - chưa dùng, mô phỏng CO2
    - DHT11   : DATA=GPIO4
*/

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <DHT.h>
#include <PMS.h>
#include <MHZ19.h>
#include <time.h>

// ====== CẤU HÌNH THIẾT BỊ - CHỈNH THEO TỪNG NODE ======
const char* DEVICE_ID       = "node-01";
const char* WIFI_SSID       = "YOUR_WIFI_SSID";      // <-- SỬA
const char* WIFI_PASSWORD   = "YOUR_WIFI_PASSWORD";  // <-- SỬA
const char* MQTT_BROKER     = "192.168.1.100";       // <-- SỬA (IP máy Mosquitto)
const int   MQTT_PORT       = 1883;
const int   READ_INTERVAL_MS = 30000;   // đọc cảm biến mỗi 30s
const int   SEND_INTERVAL_MS = 300000;  // gửi lên server mỗi 5 phút (Task A3.1)

// ====== CHÂN CẮM ======
#define DHTPIN   4
#define DHTTYPE  DHT11
DHT dht(DHTPIN, DHTTYPE);

HardwareSerial PMSSerial(1);
HardwareSerial CO2Serial(2);

PMS pms(PMSSerial);
PMS::DATA pmsData;

MHZ19 mhz;   // Chưa dùng, để sẵn cho sau này

WiFiClient espClient;
PubSubClient mqttClient(espClient);

char mqttTopic[64];

// ====== BUFFER OFFLINE (Task A4.2 chuẩn bị) ======
#define BUFFER_SIZE 50
String dataBuffer[BUFFER_SIZE];
int bufferHead = 0;
int bufferCount = 0;

unsigned long lastReadTime = 0;
unsigned long lastSendTime = 0;

// ====== GIÁ TRỊ ĐỌC GẦN NHẤT ======
float latestPM25 = NAN, latestPM10 = NAN;
int   latestCO2  = -1;
float latestTemp = NAN, latestHumidity = NAN;

// ====== CỜ ĐÁNH DẤU PMS5003 CÓ SẴN HAY KHÔNG ======
bool pmsAvailable = false;
unsigned long pmsMissingSince = 0;   // Thời điểm bắt đầu không thấy PMS
#define PMS_TIMEOUT_MS 60000          // 60s không đọc được -> coi như chưa cắm

// ====== HÀM LẤY TIMESTAMP ISO-8601 ======
String getISOTimestamp() {
  time_t now;
  struct tm timeinfo;
  time(&now);
  localtime_r(&now, &timeinfo);

  char buf[25];
  strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%S", &timeinfo);
  return String(buf);
}

// ====== WIFI + NTP ======
void setupWiFi() {
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Đang kết nối WiFi");
  int retry = 0;
  while (WiFi.status() != WL_CONNECTED && retry < 40) {
    delay(500);
    Serial.print(".");
    retry++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi đã kết nối, IP: " + WiFi.localIP().toString());

    configTime(7 * 3600, 0, "pool.ntp.org", "time.nist.gov");
    Serial.print("Đang đồng bộ NTP");
    struct tm timeinfo;
    int ntpRetry = 0;
    while (!getLocalTime(&timeinfo) && ntpRetry < 20) {
      delay(500);
      Serial.print(".");
      ntpRetry++;
    }
    Serial.println("\nGiờ hiện tại: " + getISOTimestamp());
  } else {
    Serial.println("\nWiFi kết nối thất bại!");
  }
}

// ====== MQTT RECONNECT (Task A3.1) ======
void reconnectMQTT() {
  int retry = 0;
  while (!mqttClient.connected() && retry < 5) {
    Serial.println("Đang kết nối MQTT broker...");
    String clientId = String("esp32-") + DEVICE_ID;
    if (mqttClient.connect(clientId.c_str())) {
      Serial.println("Đã kết nối MQTT.");
      // Gửi bù buffer ngay khi kết nối lại (Task A4.2)
      flushBuffer();
    } else {
      Serial.print("Kết nối MQTT thất bại, rc=");
      Serial.println(mqttClient.state());
      delay(5000);
      retry++;
    }
  }
}

// ====== MÔ PHỎNG CO2 (380-2000 ppm) ======
int simulateCO2() {
  static unsigned long startTime = 0;
  if (startTime == 0) startTime = millis();

  float t = (millis() - startTime) / 1000.0 / 60.0;  // phút
  float base = 600 + 400 * sin(t * 2 * PI / 60);      // chu kỳ 60 phút
  int noise = random(-50, 50);
  int co2 = (int)(base + noise);

  if (co2 < 380) co2 = 380;
  if (co2 > 2000) co2 = 2000;
  return co2;
}

// ====== MÔ PHỎNG PM2.5/PM10 (khi chưa có PMS5003) ======
float simulatePM25() {
  static unsigned long startTime = 0;
  if (startTime == 0) startTime = millis();

  float t = (millis() - startTime) / 1000.0 / 60.0;
  float base = 25 + 15 * sin(t * 2 * PI / 120);  // chu kỳ 2 giờ
  int noise = random(-5, 5);
  float pm = base + noise;
  if (pm < 5) pm = 5;
  return pm;
}

// ====== ĐỌC CẢM BIẾN ======
bool readPMS5003(float &pm25, float &pm10) {
  if (pms.read(pmsData)) {
    pm25 = pmsData.PM_AE_UG_2_5;
    pm10 = pmsData.PM_AE_UG_10_0;
    return true;
  }
  return false;
}

void readAllSensors() {
  // --- PMS5003: đọc thật, fallback mô phỏng ---
  float pm25, pm10;
  if (readPMS5003(pm25, pm10)) {
    latestPM25 = pm25;
    latestPM10 = pm10;
    if (!pmsAvailable) {
      Serial.println(">>> PMS5003 đã có, chuyển sang đọc thật <<<");
      pmsAvailable = true;
    }
    pmsMissingSince = 0;
  } else {
    if (pmsAvailable) {
      if (pmsMissingSince == 0) pmsMissingSince = millis();
      if (millis() - pmsMissingSince > PMS_TIMEOUT_MS) {
        Serial.println(">>> PMS5003 mất kết nối, chuyển sang mô phỏng <<<");
        pmsAvailable = false;
      }
    }
    if (!pmsAvailable) {
      latestPM25 = simulatePM25();
      latestPM10 = latestPM25 * 1.5;
    }
  }

  // --- CO2: mô phỏng (MH-Z19B chưa có) ---
  latestCO2 = simulateCO2();

  // --- DHT11: đọc thật ---
  float t = dht.readTemperature();
  float h = dht.readHumidity();
  if (!isnan(t)) latestTemp = t;
  if (!isnan(h)) latestHumidity = h;

  // In log
  Serial.printf("PM2.5=%.1f PM10=%.1f CO2=%d T=%.1f H=%.1f (PMS:%s)\n",
                latestPM25, latestPM10, latestCO2, latestTemp, latestHumidity,
                pmsAvailable ? "THAT" : "MO_PHONG");
}

// ====== BUILD JSON PAYLOAD (đã sửa lỗi compile) ======
String buildPayload() {
  StaticJsonDocument<256> doc;

  doc["device_id"] = DEVICE_ID;
  doc["timestamp"] = getISOTimestamp();

  // PM2.5
  if (isnan(latestPM25)) {
    doc["pm25"] = nullptr;
  } else {
    doc["pm25"] = latestPM25;
  }

  // PM10
  if (isnan(latestPM10)) {
    doc["pm10"] = nullptr;
  } else {
    doc["pm10"] = latestPM10;
  }

  // CO2
  if (latestCO2 > 0) {
    doc["co2"] = latestCO2;
  } else {
    doc["co2"] = nullptr;
  }

  // Temperature
  if (isnan(latestTemp)) {
    doc["temperature"] = nullptr;
  } else {
    doc["temperature"] = latestTemp;
  }

  // Humidity
  if (isnan(latestHumidity)) {
    doc["humidity"] = nullptr;
  } else {
    doc["humidity"] = latestHumidity;
  }

  String payload;
  serializeJson(doc, payload);
  return payload;
}

// ====== BUFFER OFFLINE (Task A4.2) ======
void bufferPush(const String &payload) {
  dataBuffer[(bufferHead + bufferCount) % BUFFER_SIZE] = payload;
  if (bufferCount < BUFFER_SIZE) {
    bufferCount++;
  } else {
    bufferHead = (bufferHead + 1) % BUFFER_SIZE;
  }
}

void flushBuffer() {
  while (bufferCount > 0 && mqttClient.connected()) {
    String payload = dataBuffer[bufferHead];
    if (mqttClient.publish(mqttTopic, payload.c_str())) {
      bufferHead = (bufferHead + 1) % BUFFER_SIZE;
      bufferCount--;
    } else {
      break;
    }
  }
}

// ====== SETUP ======
void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n=== ESP32 Sensor Node - PBL4 Task A3.1 ===");

  // Khởi tạo cảm biến
  dht.begin();
  PMSSerial.begin(9600, SERIAL_8N1, 16, 17);
  CO2Serial.begin(9600, SERIAL_8N1, 25, 26);
  mhz.begin(CO2Serial);
  mhz.autoCalibration(false);

  snprintf(mqttTopic, sizeof(mqttTopic), "sensors/%s/data", DEVICE_ID);
  Serial.print("MQTT topic: ");
  Serial.println(mqttTopic);

  setupWiFi();

  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);

  Serial.println("Chờ 30s warm-up cảm biến...");
  delay(30000);
}

// ====== LOOP (Task A3.1) ======
void loop() {
  // --- Duy trì WiFi ---
  if (WiFi.status() != WL_CONNECTED) {
    setupWiFi();
  }

  // --- Duy trì MQTT (Task A3.1: reconnect tự động) ---
  if (!mqttClient.connected()) {
    reconnectMQTT();
  }
  mqttClient.loop();

  unsigned long now = millis();

  // --- Đọc cảm biến mỗi 30s ---
  if (now - lastReadTime >= READ_INTERVAL_MS) {
    lastReadTime = now;
    readAllSensors();
  }

  // --- Gửi MQTT mỗi 5 phút (Task A3.1) ---
  if (now - lastSendTime >= SEND_INTERVAL_MS) {
    lastSendTime = now;
    String payload = buildPayload();

    Serial.println("=== JSON PAYLOAD ===");
    Serial.println(payload);
    Serial.println("====================");

    if (mqttClient.connected()) {
      if (mqttClient.publish(mqttTopic, payload.c_str())) {
        Serial.println(">>> Đã publish MQTT thành công <<<");
      } else {
        Serial.println(">>> Publish thất bại - lưu vào buffer <<<");
        bufferPush(payload);
      }
    } else {
      Serial.println(">>> Mất kết nối MQTT - lưu vào buffer <<<");
      bufferPush(payload);
    }
  }
}