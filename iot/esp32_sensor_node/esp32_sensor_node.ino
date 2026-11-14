/*
  PBL4 - Node cảm biến chất lượng không khí (ESP32)
  Đọc: PM2.5/PM10 (PMS5003 thật), CO2 (mô phỏng), DHT11 (thật)
  Hiển thị lên LCD I2C 1602: AQI và tên mức tính giống hệt Backend/Dashboard (US EPA 2024)
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
    - Cảnh báo: LED xanh=GPIO18, LED vàng=GPIO19, LED đỏ=GPIO23 (mỗi LED qua điện trở 220 ohm)
                Còi active 5V=GPIO27 qua transistor NPN S8050/2N2222 (điện trở 1k vào chân B)
                Nút tắt tiếng=GPIO13 (một chân vào GPIO13, chân kia vào GND)
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
const char* WIFI_SSID        = "Imou-B97E14";          // <-- điền tên Wi-Fi (KHÔNG commit giá trị thật lên GitHub)
const char* WIFI_PASSWORD    = "Kd6dG464";     // <-- điền mật khẩu Wi-Fi (KHÔNG commit giá trị thật lên GitHub)
const char* MQTT_BROKER      = "192.168.10.4";      // <-- IP máy chạy Docker/Mosquitto (máy Quyến), xem bằng ipconfig
const int   MQTT_PORT        = 1883;
const unsigned long READ_INTERVAL_MS = 10000;   // đọc cảm biến mỗi 10s (mỗi lần gửi luôn có số mới)
const unsigned long SEND_INTERVAL_MS = 30000;   // gửi lên server mỗi 30s (chế độ demo; chạy lâu dài nên để 300000 = 5 phút)
const unsigned long PMS_TIMEOUT_MS   = 10000;   // quá 10s không nhận frame PMS -> coi như lỗi
const unsigned long WIFI_RETRY_MS    = 30000;   // mất Wi-Fi: thử lại mỗi 30s (không chặn đèn/còi)
const unsigned long MQTT_RETRY_MS    = 30000;   // mất broker: thử lại mỗi 30s (mỗi lần thử có thể chặn ~3s)

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

// Bản ghi vừa gửi lên server - Dashboard hiển thị đúng bản ghi này, nên LCD cũng hiện theo nó
bool  hasSent  = false;
float sentPM25 = NAN, sentPM10 = NAN, sentTemp = NAN, sentHumidity = NAN;

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
  // Bật NTP ngay cả khi chưa có Wi-Fi: có mạng lúc nào thì tự đồng bộ giờ lúc đó
  configTime(7 * 3600, 0, "pool.ntp.org", "time.nist.gov");
  Serial.print("Đang kết nối WiFi");
  int retry = 0;
  while (WiFi.status() != WL_CONNECTED && retry < 40) {
    delay(500);
    Serial.print(".");
    retry++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi đã kết nối, IP: " + WiFi.localIP().toString());
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
// Mỗi lần gọi chỉ thử 1 lần, không delay, để đèn/còi vẫn chạy khi mất broker
void reconnectMQTT() {
  Serial.println("Đang kết nối MQTT broker...");
  String clientId = String("esp32-") + DEVICE_ID;
  if (mqttClient.connect(clientId.c_str())) {
    Serial.println("Đã kết nối MQTT.");
    flushBuffer(); // Gửi bù dữ liệu tồn đọng ngay khi kết nối lại
  } else {
    Serial.print("Kết nối MQTT thất bại, rc=");
    Serial.println(mqttClient.state());
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

// ====== AQI THEO US EPA 2024 (giống hệt backend/app/aqi.py) ======
const double AQI_BP[6][4] = {   // PM2.5 thấp, PM2.5 cao, AQI thấp, AQI cao
  {0.0,   9.0,   0,   50},
  {9.1,   35.4,  51,  100},
  {35.5,  55.4,  101, 150},
  {55.5,  125.4, 151, 200},
  {125.5, 225.4, 201, 300},
  {225.5, 325.4, 301, 500},
};

// Làm tròn giống hàm round() của Python (đúng 0.5 thì làm tròn về số chẵn)
long roundHalfEven(double x) {
  double f = floor(x);
  double d = x - f;
  if (d > 0.5) return (long)f + 1;
  if (d < 0.5) return (long)f;
  return ((long)f % 2 == 0) ? (long)f : (long)f + 1;
}

// Trả -1 nếu không có số đo hợp lệ
int pm25ToAQI(float pm25) {
  if (isnan(pm25) || pm25 < 0) return -1;
  double v = round((double)pm25 * 10000.0) / 10000.0;        // số JSON gửi lên server (bỏ sai số float)
  v = floor(round(v * 10.0 * 1e6) / 1e6) / 10.0;            // EPA cắt về 1 chữ số thập phân, như Backend
  for (int i = 0; i < 6; i++) {
    if (v <= AQI_BP[i][1]) {
      if (v < AQI_BP[i][0]) v = AQI_BP[i][0];      // khoảng hở giữa hai mức (vd 9.05)
      double a = (AQI_BP[i][3] - AQI_BP[i][2]) / (AQI_BP[i][1] - AQI_BP[i][0]) * (v - AQI_BP[i][0]) + AQI_BP[i][2];
      return (int)roundHalfEven(a);
    }
  }
  return 500;
}

// Tên mức theo AQI, cùng ranh giới với Dashboard (không dấu vì LCD 1602 không hiện được tiếng Việt)
//   Tốt / Trung bình / Kém / Xấu / Rất xấu / Nguy hại
const char* aqiLabel(int aqi) {
  if (aqi < 0)    return "LOI";
  if (aqi <= 50)  return "TOT";
  if (aqi <= 100) return "TB";
  if (aqi <= 150) return "KEM";
  if (aqi <= 200) return "XAU";
  if (aqi <= 300) return "RAT XAU";
  return "NGUY HAI";
}

// ====== CẢNH BÁO ĐÈN + CÒI ======
// Ngưỡng theo PM2.5 (US EPA 2024, cùng bảng với Backend):
//   <= 35.4   : xanh     (Tốt / Trung bình)       - còi im
//   35.5-55.4 : vàng     (Kém, nhóm nhạy cảm)     - kêu 5 tiếng khi vừa chuyển sang
//   55.5-125.4: đỏ       (Xấu)                    - kêu 7 tiếng khi vừa chuyển sang
//   > 125.4   : đỏ nháy  (Rất xấu / Nguy hại)     - kêu 10 tiếng, lặp lại mỗi 60s
// Cứ 2 phút báo cáo 1 lần (Serial + LCD + còi nếu mức từ vàng trở lên).
// Dùng trung bình trượt 2 phút để đèn không chớp theo nhiễu, có trễ 2 ug/m3 khi hạ mức.
#define LED_GREEN   18
#define LED_YELLOW  19
#define LED_RED     23
#define BUZZER_PIN  27
#define BTN_MUTE    13

const int   AVG_SAMPLES   = 12;                       // 12 lần đọc x 10s = 2 phút
const float HYSTERESIS    = 2.0;                      // phải giảm thêm 2 ug/m3 dưới ngưỡng mới hạ mức
const float LEVEL_UPPER[] = {35.4, 55.4, 125.4};      // ranh giới giữa các mức 0|1|2|3
const unsigned long MUTE_MS          = 30UL * 60 * 1000;   // bấm nút: im 30 phút
const unsigned long SEVERE_REPEAT_MS = 60000;
const unsigned long REPORT_MS        = 120000UL;           // báo cáo định kỳ mỗi 2 phút
const int   QUIET_FROM_HOUR = 22, QUIET_TO_HOUR = 6;       // ban đêm chỉ bật đèn, không kêu

float pmHistory[AVG_SAMPLES];
int   pmCount = 0, pmIndex = 0;
int   alertLevel = -1;                                // -1: chưa có số đo / cảm biến lỗi
unsigned long muteUntil = 0, lastSevereBeep = 0;
int   beepsLeft = 0;
bool  buzzerOn = false;
unsigned long buzzerToggleAt = 0;
bool  btnPrev = HIGH;
unsigned long btnChangedAt = 0;
unsigned long lcdHoldUntil = 0;                       // giữ màn hình báo cáo 2 phút đến thời điểm này

const char* LEVEL_NAME[] = {"XANH", "VANG", "DO", "DO NHAY"};  // tên mức của ĐÈN (TB 2 phút), in ra Serial

void alarmSetup() {
  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_YELLOW, OUTPUT);
  pinMode(LED_RED, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(BTN_MUTE, INPUT_PULLUP);
  // Tự kiểm tra khi khởi động: sáng cả 3 đèn + kêu 1 tiếng
  digitalWrite(LED_GREEN, HIGH); digitalWrite(LED_YELLOW, HIGH); digitalWrite(LED_RED, HIGH);
  digitalWrite(BUZZER_PIN, HIGH); delay(200); digitalWrite(BUZZER_PIN, LOW); delay(600);
  digitalWrite(LED_GREEN, LOW); digitalWrite(LED_YELLOW, LOW); digitalWrite(LED_RED, LOW);
}

bool isQuietHours() {
  struct tm t;
  if (!getLocalTime(&t, 0)) return false;             // chưa có giờ thật thì không áp dụng
  return t.tm_hour >= QUIET_FROM_HOUR || t.tm_hour < QUIET_TO_HOUR;
}

// Số tiếng còi khi CHUYỂN LÊN từng mức: vàng=5, đỏ=7, đỏ nháy=10
int beepsForLevel(int level) {
  switch (level) {
    case 1: return 5;
    case 2: return 7;
    case 3: return 10;
    default: return 0;
  }
}

void beep(int times) {
  if (millis() < muteUntil || isQuietHours()) return;
  beepsLeft = times;
  buzzerOn = false;
  buzzerToggleAt = millis();
}

float averagePM25() {
  if (pmCount == 0) return NAN;
  float sum = 0;
  for (int i = 0; i < pmCount; i++) sum += pmHistory[i];
  return sum / pmCount;
}

int levelFor(float pm, int current) {
  int lv = 0;
  while (lv < 3 && pm > LEVEL_UPPER[lv]) lv++;
  // Trễ khi hạ mức: chỉ hạ khi đã thấp hơn ranh giới của mức hiện tại 2 ug/m3
  if (current > 0 && lv < current && pm > LEVEL_UPPER[current - 1] - HYSTERESIS) return current;
  return lv;
}

// Báo cáo định kỳ mỗi 2 phút: in Serial + hiện LCD (còi do hàm gọi quyết định)
void reportLevel(int level) {
  float avg = averagePM25();
  int avgAqi = pm25ToAQI(avg);
  Serial.printf("Mức cảnh báo: đèn %s (PM2.5 TB 2 phút = %.1f, AQI %d %s)\n",
                LEVEL_NAME[level], avg, avgAqi, aqiLabel(avgAqi));

  // LCD: hiện báo cáo ngay, lần cập nhật 10s kế tiếp sẽ trả về màn hình thường
  char l0[17], l1[17];
  snprintf(l0, sizeof(l0), "TB2P:%-11s", aqiLabel(avgAqi));
  snprintf(l1, sizeof(l1), "AQI%-3d PM %-6.1f", avgAqi, avg);
  lcd.setCursor(0, 0); lcd.print(l0);
  lcd.setCursor(0, 1); lcd.print(l1);
  lcdHoldUntil = millis() + 9000;   // giữ ~9s, lần đọc 10s kế tiếp mới về màn thường
}

// Gọi sau mỗi lần đọc cảm biến (10s)
void updateAlertLevel() {
  if (isnan(latestPM25)) {                 // cảm biến lỗi: xoá lịch sử, chuyển sang trạng thái lỗi
    pmCount = 0; pmIndex = 0; alertLevel = -1;
    return;
  }
  pmHistory[pmIndex] = latestPM25;
  pmIndex = (pmIndex + 1) % AVG_SAMPLES;
  if (pmCount < AVG_SAMPLES) pmCount++;

  int newLevel = levelFor(averagePM25(), alertLevel < 0 ? 0 : alertLevel);
  if (alertLevel >= 0 && newLevel > alertLevel) {     // chỉ kêu khi chất lượng xấu đi
    beep(beepsForLevel(newLevel));
    if (newLevel == 3) lastSevereBeep = millis();
  }
  if (alertLevel < 0 && newLevel >= 2) {             // vừa có số đo đã ở mức đỏ trở lên
    beep(7);
    lastSevereBeep = millis();
  }

  static unsigned long lastReport = 0;
  bool changed = (newLevel != alertLevel);
  if (changed || millis() - lastReport >= REPORT_MS) {   // đổi mức thì báo ngay, còn lại 2 phút báo 1 lần
    lastReport = millis();
    reportLevel(newLevel);
    if (!changed && newLevel >= 1) {                     // đến hạn 2 phút mà mức không đổi: còi kêu theo mức
      beep(beepsForLevel(newLevel));
      if (newLevel == 3) lastSevereBeep = millis();      // tránh kêu đúp với lần nhắc 60s
    }
  }
  alertLevel = newLevel;
}

// Gọi liên tục trong loop: điều khiển đèn, còi, nút tắt tiếng (không dùng delay)
void alarmLoop() {
  unsigned long now = millis();

  // Nút tắt tiếng (chống dội 50ms): bấm -> im 30 phút; đang im mà bấm -> bật lại
  bool btn = digitalRead(BTN_MUTE);
  if (btn != btnPrev && now - btnChangedAt > 50) {
    btnChangedAt = now;
    btnPrev = btn;
    if (btn == LOW) {
      if (now < muteUntil) { muteUntil = 0; Serial.println("Bật lại còi"); }
      else { muteUntil = now + MUTE_MS; beepsLeft = 0; Serial.println("Tắt tiếng 30 phút"); }
    }
  }

  // Đèn: vàng nháy = chưa có số đo / cảm biến lỗi; đỏ nháy = rất xấu
  bool blink = (now / 500) % 2;
  digitalWrite(LED_GREEN,  alertLevel == 0);
  digitalWrite(LED_YELLOW, alertLevel == 1 || (alertLevel < 0 && blink));
  digitalWrite(LED_RED,    alertLevel == 2 || (alertLevel == 3 && blink));

  // Mức rất xấu: nhắc lại mỗi 60s (10 tiếng)
  if (alertLevel == 3 && now - lastSevereBeep >= SEVERE_REPEAT_MS) {
    lastSevereBeep = now;
    beep(10);
  }

  // Còi: mỗi tiếng kêu 150ms, nghỉ 150ms
  if (beepsLeft > 0 && (long)(now - buzzerToggleAt) >= 0) {
    buzzerOn = !buzzerOn;
    digitalWrite(BUZZER_PIN, buzzerOn ? HIGH : LOW);
    if (!buzzerOn) beepsLeft--;
    buzzerToggleAt = now + 150;
  }
  if (beepsLeft == 0 && buzzerOn) {
    buzzerOn = false;
    digitalWrite(BUZZER_PIN, LOW);
  }
}

// ====== HIỂN THỊ LÊN LCD ======
// Màn thường hiện ĐÚNG bản ghi vừa gửi lên server, với AQI và tên mức tính giống hệt Backend,
// nên LCD và Dashboard luôn cùng số AQI, cùng mức. Chưa gửi lần nào thì hiện số vừa đọc.
//   Dòng 1: AQI:117 KEM       (thêm "IM" khi đang tắt tiếng)
//   Dòng 2: PM:42 T:31 H:70%
void updateLCD() {
  if (millis() < lcdHoldUntil) return;   // đang hiện báo cáo 2 phút

  float pm  = hasSent ? sentPM25     : latestPM25;
  float tmp = hasSent ? sentTemp     : latestTemp;
  float hum = hasSent ? sentHumidity : latestHumidity;
  int aqi = pm25ToAQI(pm);

  char l0[17], l1[17], a[5], p[5], tt[4], hh[4];
  if (aqi < 0) strcpy(a, "--"); else snprintf(a, sizeof(a), "%d", aqi);
  if (isnan(pm))  strcpy(p, "--");  else snprintf(p, sizeof(p), "%.0f", pm);
  if (isnan(tmp)) strcpy(tt, "--"); else snprintf(tt, sizeof(tt), "%.0f", tmp);
  if (isnan(hum)) strcpy(hh, "--"); else snprintf(hh, sizeof(hh), "%.0f", hum);

  snprintf(l0, sizeof(l0), "AQI:%s %s%s", a, aqiLabel(aqi), millis() < muteUntil ? " IM" : "");
  snprintf(l1, sizeof(l1), "PM:%s T:%s H:%s%%", p, tt, hh);

  lcd.setCursor(0, 0); lcd.print(l0); for (int i = strlen(l0); i < 16; i++) lcd.print(' ');
  lcd.setCursor(0, 1); lcd.print(l1); for (int i = strlen(l1); i < 16; i++) lcd.print(' ');
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

  alarmSetup();

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
    alarmLoop(); // đèn vàng nháy trong lúc chờ (chưa có số đo)
    delay(10);
  }
}

// ====== LOOP ======
void loop() {
  pollPMS();   // luôn đọc PMS5003 đầu tiên, liên tục

  alarmLoop(); // đèn, còi, nút tắt tiếng - chạy cả khi mất mạng

  unsigned long now = millis();

  // Duy trì WiFi & MQTT (giới hạn tần suất thử lại để không chặn cảnh báo)
  static unsigned long lastWifiTry = 0, lastMqttTry = 0;
  if (WiFi.status() != WL_CONNECTED) {
    if (now - lastWifiTry >= WIFI_RETRY_MS) {
      lastWifiTry = now;
      Serial.println("Mất WiFi, đang thử kết nối lại...");
      WiFi.disconnect();
      WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    }
  } else if (!mqttClient.connected()) {
    if (now - lastMqttTry >= MQTT_RETRY_MS) { lastMqttTry = now; reconnectMQTT(); }
  }
  mqttClient.loop();

  // Đọc cảm biến & cập nhật LCD
  if (now - lastReadTime >= READ_INTERVAL_MS) {
    lastReadTime = now;
    readAllSensors();
    updateAlertLevel();
    updateLCD();   // nếu vừa có báo cáo 2 phút thì updateLCD() tự giữ màn báo cáo
  }

  // Gửi dữ liệu MQTT định kỳ
  if (now - lastSendTime >= SEND_INTERVAL_MS) {
    lastSendTime = now;
    String payload = buildPayload();
    hasSent = true;
    sentPM25 = latestPM25; sentPM10 = latestPM10; sentTemp = latestTemp; sentHumidity = latestHumidity;
    updateLCD();   // LCD đổi cùng lúc với Dashboard

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
