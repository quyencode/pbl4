/*
  PBL4 - Node cảm biến chất lượng không khí (ESP32)
  Đọc: PM2.5/PM10 (PMS5003 thật), CO2 (mô phỏng), DHT11 (thật)
  Hiển thị lên LCD I2C 1602
  Gửi dữ liệu qua MQTT theo định dạng trong iot/mqtt_data_contract.md

  Thư viện cần cài:
    - PubSubClient, ArduinoJson, DHT sensor library, Adafruit Unified Sensor
    - PMS (Mariusz Kacki), MHZ19
    - LiquidCrystal I2C

  Chân cắm:
    - PMS5003 : TX của PMS -> GPIO16 (RX ESP32), RX của PMS -> GPIO17 (TX ESP32), cấp 5V
    - MH-Z19B : RX=25, TX=26 (UART2) - chưa có cảm biến, CO2 đang mô phỏng
    - DHT11   : DATA=GPIO4
    - LCD I2C : SDA=GPIO21, SCL=GPIO22
*/

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <DHT.h>
#include <PMS.h>
#include <MHZ19.h>
#include <time.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// ====== CẤU HÌNH THIẾT BỊ ======
const char* DEVICE_ID        = "node-01";
const char* WIFI_SSID        = "Imou-B97E14";      // <-- tên Wi-Fi (KHÔNG commit giá trị thật lên GitHub)
const char* WIFI_PASSWORD    = "Kd6dG464";  // <-- mật khẩu Wi-Fi (KHÔNG commit giá trị thật lên GitHub)
const char* MQTT_BROKER      = "192.168.10.2";        // <-- IP máy chạy Docker/Mosquitto (máy Quyến), xem bằng ipconfig
const int   MQTT_PORT        = 1883;
const unsigned long READ_INTERVAL_MS = 10000;   // đọc cảm biến mỗi 30s
const unsigned long SEND_INTERVAL_MS = 30000;  // gửi lên server mỗi 5 phút (demo: đổi tạm thành 30000)
const unsigned long PMS_TIMEOUT_MS   = 10000;   // quá 10s không nhận frame PMS -> coi như lỗi

// ====== CHÂN CẮM ======
#define DHTPIN   4
#define DHTTYPE  DHT11
DHT dht(DHTPIN, DHTTYPE);

HardwareSerial PMSSerial(1);
HardwareSerial CO2Serial(2);

PMS pms(PMSSerial);
PMS::DATA pmsData;

MHZ19 mhz;

// ====== LCD I2C ======
LiquidCrystal_I2C lcd(0x27, 16, 2);  // Đổi 0x27 thành 0x3F nếu màn không hiện chữ

WiFiClient espClient;
PubSubClient mqttClient(espClient);

char mqttTopic[64];

// ====== BUFFER OFFLINE ======
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

// ====== PMS5003 ======
unsigned long lastPMSFrame = 0;   // thời điểm nhận frame hợp lệ gần nhất

// ====== HÀM LẤY TIMESTAMP ======
// Gửi kèm múi giờ +07:00 để Backend hiểu đúng giờ Việt Nam
// (không có múi giờ thì Backend coi là UTC -> dữ liệu bị lệch 7 tiếng).
// Chưa đồng bộ được NTP thì trả chuỗi rỗng -> không gửi timestamp, Backend tự dùng giờ nhận.
String getISOTimestamp() {
  time_t now;
  struct tm timeinfo;
  time(&now);
  localtime_r(&now, &timeinfo);
  if (timeinfo.tm_year + 1900 < 2024) return "";   // vẫn là giờ mặc định 1970 -> chưa có giờ thật
  char buf[32];
  strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%S+07:00", &timeinfo);
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
    String ts = getISOTimestamp();
    Serial.println("\nGiờ hiện tại: " + (ts.length() > 0 ? ts : String("chưa đồng bộ được NTP")));
  } else {
    Serial.println("\nWiFi kết nối thất bại!");
  }
}

// ====== BUFFER OFFLINE ======
void bufferPush(const String &payload) {
  dataBuffer[(bufferHead + bufferCount) % BUFFER_SIZE] = payload;
  if (bufferCount < BUFFER_SIZE) {
    bufferCount++;
  } else {
    bufferHead = (bufferHead + 1) % BUFFER_SIZE;  // đầy -> bỏ bản ghi cũ nhất
  }
  Serial.printf("Buffer đang giữ %d bản ghi\n", bufferCount);
}

void flushBuffer() {
  while (bufferCount > 0 && mqttClient.connected()) {
    String payload = dataBuffer[bufferHead];
    if (mqttClient.publish(mqttTopic, payload.c_str())) {
      bufferHead = (bufferHead + 1) % BUFFER_SIZE;
      bufferCount--;
      Serial.println(">>> Gửi bù 1 bản ghi từ buffer <<<");
    } else {
      break;
    }
  }
}

// ====== MQTT RECONNECT ======
void reconnectMQTT() {
  int retry = 0;
  while (!mqttClient.connected() && retry < 5) {
    Serial.println("Đang kết nối MQTT broker...");
    String clientId = String("esp32-") + DEVICE_ID;
    if (mqttClient.connect(clientId.c_str())) {
      Serial.println("Đã kết nối MQTT.");
      flushBuffer(); // Gửi bù dữ liệu tồn đọng ngay khi kết nối lại
    } else {
      Serial.print("Kết nối MQTT thất bại, rc=");
      Serial.println(mqttClient.state());
      delay(5000);
      retry++;
    }
  }
}

// ====== MÔ PHỎNG CO2 (chưa có MH-Z19B) ======
int simulateCO2() {
  static unsigned long startTime = 0;
  if (startTime == 0) startTime = millis();
  float t = (millis() - startTime) / 1000.0 / 60.0;
  float base = 600 + 400 * sin(t * 2 * PI / 60);
  int noise = random(-50, 50);
  int co2 = (int)(base + noise);
  if (co2 < 380) co2 = 380;
  if (co2 > 2000) co2 = 2000;
  return co2;
}

// ====== ĐỌC PMS5003 (gọi liên tục trong loop) ======
void pollPMS() {
  if (pms.read(pmsData)) {
    latestPM25 = pmsData.PM_AE_UG_2_5;
    latestPM10 = pmsData.PM_AE_UG_10_0;
    lastPMSFrame = millis();
  }
}

// ====== ĐỌC CÁC CẢM BIẾN CÒN LẠI ======
void readAllSensors() {
  latestCO2 = simulateCO2();

  float t = dht.readTemperature();
  float h = dht.readHumidity();
  if (!isnan(t)) latestTemp = t;
  if (!isnan(h)) latestHumidity = h;

  bool pmsOk = (lastPMSFrame != 0) && (millis() - lastPMSFrame < PMS_TIMEOUT_MS);
  if (!pmsOk) {
    Serial.println("!!! Không nhận được dữ liệu từ PMS5003 - kiểm tra dây !!!");
    // Không gửi lại số cũ như số mới -> gửi null cho tới khi PMS đọc lại được
    latestPM25 = NAN;
    latestPM10 = NAN;
  }

  Serial.printf("PM2.5=%.1f PM10=%.1f CO2=%d T=%.1f H=%.1f (PMS:%s)\n",
                latestPM25, latestPM10, latestCO2, latestTemp, latestHumidity,
                pmsOk ? "THAT" : "LOI");
}

// ====== HIỂN THỊ LÊN LCD ======
void updateLCD() {
  lcd.setCursor(0, 0);
  lcd.print("PM2.5:");
  if (isnan(latestPM25)) lcd.print("--");
  else lcd.print(latestPM25, 1);
  lcd.print("      ");

  lcd.setCursor(0, 1);
  lcd.print("T:");
  if (isnan(latestTemp)) lcd.print("--");
  else lcd.print(latestTemp, 1);
  lcd.print("C H:");
  if (isnan(latestHumidity)) lcd.print("--");
  else lcd.print(latestHumidity, 0);
  lcd.print("%  ");
}

// ====== BUILD JSON PAYLOAD ======
String buildPayload() {
  StaticJsonDocument<256> doc;
  doc["device_id"] = DEVICE_ID;

  String ts = getISOTimestamp();
  if (ts.length() > 0) doc["timestamp"] = ts;   // không có giờ thật thì bỏ trống, Backend tự gán

  if (isnan(latestPM25)) doc["pm25"] = nullptr; else doc["pm25"] = latestPM25;
  if (isnan(latestPM10)) doc["pm10"] = nullptr; else doc["pm10"] = latestPM10;
  if (latestCO2 > 0)     doc["co2"]  = latestCO2; else doc["co2"]  = nullptr;
  if (isnan(latestTemp)) doc["temperature"] = nullptr; else doc["temperature"] = latestTemp;
  if (isnan(latestHumidity)) doc["humidity"] = nullptr; else doc["humidity"] = latestHumidity;

  String payload;
  serializeJson(doc, payload);
  return payload;
}

// ====== SETUP ======
void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n=== ESP32 Sensor Node - PBL4 ===");

  // Khởi tạo LCD
  Wire.begin(21, 22);
  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("PBL4 - Node 01");

  // Khởi tạo cảm biến
  dht.begin();
  PMSSerial.begin(9600, SERIAL_8N1, 16, 17);
  pms.wakeUp();
  pms.activeMode();
  CO2Serial.begin(9600, SERIAL_8N1, 25, 26);
  mhz.begin(CO2Serial);
  mhz.autoCalibration(false);

  snprintf(mqttTopic, sizeof(mqttTopic), "sensors/%s/data", DEVICE_ID);
  Serial.print("MQTT topic: ");
  Serial.println(mqttTopic);
  Serial.print("MQTT broker: ");
  Serial.println(MQTT_BROKER);

  setupWiFi();
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);

  Serial.println("Chờ 30s warm-up cảm biến...");
  unsigned long warmupStart = millis();
  while (millis() - warmupStart < 30000) {
    pollPMS();   // vẫn đọc PMS trong lúc chờ để bộ đệm UART không bị tràn
    delay(10);
  }
}

// ====== LOOP ======
void loop() {
  pollPMS();   // luôn đọc PMS5003 đầu tiên, liên tục

  // Duy trì WiFi & MQTT
  if (WiFi.status() != WL_CONNECTED) setupWiFi();
  if (WiFi.status() == WL_CONNECTED && !mqttClient.connected()) reconnectMQTT();
  mqttClient.loop();

  unsigned long now = millis();

  // Đọc cảm biến & cập nhật LCD
  if (now - lastReadTime >= READ_INTERVAL_MS) {
    lastReadTime = now;
    readAllSensors();
    updateLCD();
  }

  // Gửi dữ liệu MQTT định kỳ
  if (now - lastSendTime >= SEND_INTERVAL_MS) {
    lastSendTime = now;
    String payload = buildPayload();

    Serial.println("=== JSON PAYLOAD ===");
    Serial.println(payload);
    Serial.println("====================");

    if (mqttClient.connected()) {
      flushBuffer(); // Gửi bù dữ liệu cũ (nếu có)
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
