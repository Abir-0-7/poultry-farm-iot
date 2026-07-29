#include <WiFi.h>
#include <Firebase_ESP_Client.h>
#include <DHT.h>
#include <MQ135.h>
#include <Wire.h>
#include <RTClib.h>
#include <time.h>
#include "addons/TokenHelper.h"
#include "addons/RTDBHelper.h"
#include "fuzzy_logic.h"
#include "acoustic_detector.h"
#include "dynamic_profile.h"

// ==================== CONFIGURATION ====================
#define WIFI_SSID "ISMAIL"
#define WIFI_PASSWORD "asima1998"
#define FIREBASE_HOST "https://poultry-monitor-9294e-default-rtdb.firebaseio.com/"
#define FIREBASE_API_KEY "AIzaSyCCBViJKpt1tgTCwLkr_-JkusbvlicSLMY"
#define FLOCK_SIZE 5000
#define FLOCK_START_DAY 1

// ==================== PIN DEFINITIONS ====================
#define DHT22_PIN 4
#define MQ135_PIN 34
#define EXHAUST_FAN_PIN 25
#define HEATER_PIN 26
#define MIC_PIN 32
#define RED_LED_PIN 14
#define GREEN_LED_PIN 12
#define BUZZER_PIN 27
#define RTC_SDA 21
#define RTC_SCL 22

// ==================== SENSOR OBJECTS ====================
DHT dht(DHT22_PIN, DHT22);
MQ135 mq135(MQ135_PIN);
FuzzyLogic fuzzyController;
AcousticDetector acousticDetector(MIC_PIN);
DynamicProfile climateProfile(FLOCK_SIZE, FLOCK_START_DAY);
RTC_DS3231 rtc;

// ==================== FIREBASE OBJECTS ====================
FirebaseData fbdoStream;
FirebaseData fbdo;
FirebaseAuth auth;
FirebaseConfig config;

// ==================== GLOBAL VARIABLES ====================
unsigned long lastReadTime = 0;
unsigned long lastPumpPrimeTime = 0;
const unsigned long READ_INTERVAL = 2000;       // 2 seconds sensor read
const unsigned long FIREBASE_INTERVAL = 10000;  // 10 seconds Firebase push
const unsigned long BLINK_INTERVAL = 500;       // LED blink

float temperature = 0.0;
float humidity = 0.0;
float ammoniaPPM = 0.0;
int comfortScore = 0;
int fanSpeed = 0;
bool heaterState = false;
bool distressDetected = false;
float distressConfidence = 0.0;
int currentFlockDay = 1;
String systemStatus = "NORMAL";

// ==================== WIFI + FIREBASE SETUP ====================
void connectWiFi() {
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to Wi-Fi");
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWi-Fi connected");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\nWi-Fi connection failed – running offline");
  }
}

void setupFirebase() {
  config.api_key = FIREBASE_API_KEY;
  config.database_url = FIREBASE_HOST;
  config.token_status_callback = tokenStatusCallback;
  Firebase.begin(&config, &auth);
  Firebase.reconnectWiFi(true);
  Serial.println("Firebase configured");
}

// ==================== SETUP ====================
void setup() {
  Serial.begin(115200);
  Serial.println("\n==============================");
  Serial.println("Poultry Farm IoT System v2.0");
  Serial.println("Cloud + Edge-AI Mode");
  Serial.println("==============================\n");

  // Pin modes
  pinMode(EXHAUST_FAN_PIN, OUTPUT);
  pinMode(HEATER_PIN, OUTPUT);
  pinMode(RED_LED_PIN, OUTPUT);
  pinMode(GREEN_LED_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);

  // Initial safe state
  digitalWrite(EXHAUST_FAN_PIN, LOW);
  digitalWrite(HEATER_PIN, LOW);
  digitalWrite(RED_LED_PIN, LOW);
  digitalWrite(GREEN_LED_PIN, HIGH);
  digitalWrite(BUZZER_PIN, LOW);

  // Initialize sensors
  dht.begin();
  Serial.println("DHT22 sensor initialized");

  // Initialize acoustic detector
  acousticDetector.begin();
  Serial.println("Acoustic detector initialized");

  // Initialize fuzzy logic
  fuzzyController.begin();
  Serial.println("Fuzzy logic controller initialized");

  // Initialize DS3231 RTC
  Wire.begin(RTC_SDA, RTC_SCL);
  if (rtc.begin()) {
    Serial.println("DS3231 RTC initialized");
    if (rtc.lostPower()) {
      Serial.println("RTC lost power – setting to compile time");
      rtc.adjust(DateTime(F(__DATE__), F(__TIME__)));
    }
  } else {
    Serial.println("DS3231 RTC not found – using NTP fallback");
  }

  // Connect to Wi-Fi and Firebase
  connectWiFi();
  if (WiFi.status() == WL_CONNECTED) {
    setupFirebase();
    // Sync time from NTP for accurate timestamps
    configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  }

  // Get current flock day from Firebase or use default
  currentFlockDay = FLOCK_START_DAY;
  if (WiFi.status() == WL_CONNECTED && Firebase.ready()) {
    if (Firebase.RTDB.getInt(&fbdo, "/config/flock_start_day")) {
      currentFlockDay = fbdo.intData();
    }
  }
  climateProfile.setFlockDay(currentFlockDay);

  Serial.println("System initialization complete\n");
}

// ==================== SENSOR READING ====================
void readSensors() {
  // Read DHT22
  temperature = dht.readTemperature();
  humidity = dht.readHumidity();
  if (isnan(temperature)) temperature = 0;
  if (isnan(humidity)) humidity = 0;

  // Read MQ135 for ammonia (calibrated approximate conversion)
  float rawRZero = mq135.getRZero();
  float rawCorrected = mq135.getCorrectedRZero(temperature, humidity);
  float resistance = mq135.getResistance();
  // Approximate NH3 in ppm using MQ135 characteristic curve
  ammoniaPPM = mq135.getPPM() * 0.1; // Rough NH₃ conversion

  if (ammoniaPPM < 0) ammoniaPPM = 0;
  if (ammoniaPPM > 100) ammoniaPPM = 100;

  // Acoustic distress detection
  distressDetected = acousticDetector.checkDistress();
  distressConfidence = acousticDetector.getConfidence();

  Serial.print("Temp: "); Serial.print(temperature);
  Serial.print("°C, Hum: "); Serial.print(humidity);
  Serial.print("%, NH3: "); Serial.print(ammoniaPPM);
  Serial.print("ppm, Distress: "); Serial.println(distressDetected ? "YES" : "NO");
}

// ==================== CONTROL LOGIC ====================
void applyControl() {
  // Get age-specific target temperature
  float targetTemp = climateProfile.getTargetTemperature();
  float tempTolerance = climateProfile.getTemperatureTolerance();

  // Run fuzzy logic to determine fan speed
  fuzzyController.setInputs(temperature, humidity, ammoniaPPM, targetTemp);
  fuzzyController.compute();
  fanSpeed = fuzzyController.getFanSpeed();

  // Heater control based on dynamic profile
  if (temperature < (targetTemp - tempTolerance)) {
    heaterState = true;
  } else if (temperature > (targetTemp + tempTolerance)) {
    heaterState = false;
  }

  // Apply outputs
  analogWrite(EXHAUST_FAN_PIN, fanSpeed);  // 0-255 PWM
  digitalWrite(HEATER_PIN, heaterState ? HIGH : LOW);

  // Compute comfort score
  comfortScore = fuzzyController.getComfortScore();

  // Handle distress alert
  if (distressDetected && distressConfidence > 0.7) {
    digitalWrite(RED_LED_PIN, HIGH);
    digitalWrite(BUZZER_PIN, HIGH);
    systemStatus = "DISTRESS_ALERT";
  } else {
    digitalWrite(RED_LED_PIN, LOW);
    digitalWrite(BUZZER_PIN, LOW);
    systemStatus = "NORMAL";
  }

  // Update LED indicators
  static unsigned long lastBlink = 0;
  if (millis() - lastBlink > BLINK_INTERVAL) {
    lastBlink = millis();
    digitalWrite(GREEN_LED_PIN, !digitalRead(GREEN_LED_PIN));
  }

  Serial.print("Target: "); Serial.print(targetTemp);
  Serial.print("°C, Fan: "); Serial.print(map(fanSpeed, 0, 255, 0, 100));
  Serial.print("%, Heater: "); Serial.print(heaterState ? "ON" : "OFF");
  Serial.print(", Comfort: "); Serial.print(comfortScore);
  Serial.println("%");
}

// ==================== FIREBASE UPLOAD ====================
void pushToFirebase() {
  if (WiFi.status() != WL_CONNECTED || !Firebase.ready()) return;

  FirebaseJson json;
  json.set("temperature", temperature);
  json.set("humidity", humidity);
  json.set("ammonia_ppm", ammoniaPPM);
  json.set("fan_speed", map(fanSpeed, 0, 255, 0, 100));
  json.set("heater_state", heaterState);
  json.set("comfort_score", comfortScore);
  json.set("distress_detected", distressDetected);
  json.set("distress_confidence", distressConfidence);
  json.set("flock_day", currentFlockDay);
  json.set("target_temp", climateProfile.getTargetTemperature());
  json.set("system_status", systemStatus);

  // Get timestamp from DS3231 RTC (fallback to NTP)
  char timeStr[30];
  if (rtc.begin()) {
    DateTime now = rtc.now();
    snprintf(timeStr, sizeof(timeStr), "%04d-%02d-%02dT%02d:%02d:%02dZ",
             now.year(), now.month(), now.day(),
             now.hour(), now.minute(), now.second());
  } else {
    struct tm timeinfo;
    if (getLocalTime(&timeinfo)) {
      strftime(timeStr, sizeof(timeStr), "%Y-%m-%dT%H:%M:%SZ", &timeinfo);
    } else {
      strcpy(timeStr, "2026-01-01T00:00:00Z");
    }
  }
  json.set("timestamp", timeStr);

  // Push to Firebase real-time data
  if (Firebase.RTDB.setJSON(&fbdo, "/live_data", &json)) {
    Serial.println("✓ Data pushed to Firebase");
  } else {
    Serial.print("Firebase push error: ");
    Serial.println(fbdo.errorReason());
  }

  // Also push to history array
  if (Firebase.RTDB.pushJSON(&fbdoStream, "/history", &json)) {
    Serial.println("✓ History entry added");
  }
}

// ==================== FIREBASE READS ====================
void checkFirebaseConfig() {
  if (WiFi.status() != WL_CONNECTED || !Firebase.ready()) return;

  // Check if flock day was updated remotely
  if (Firebase.RTDB.getInt(&fbdo, "/config/flock_start_day")) {
    int remoteDay = fbdo.intData();
    if (remoteDay != currentFlockDay) {
      currentFlockDay = remoteDay;
      climateProfile.setFlockDay(currentFlockDay);
      Serial.print("Flock day updated to: ");
      Serial.println(currentFlockDay);
    }
  }

  // Check for manual override
  if (Firebase.RTDB.getBool(&fbdo, "/config/manual_override")) {
    bool ovr = fbdo.boolData();
    if (ovr) {
      systemStatus = "MANUAL_OVERRIDE";
      Serial.println("Manual override active");
    }
  }
}

// ==================== MAIN LOOP ====================
void loop() {
  unsigned long now = millis();

  // Read sensors every 2 seconds
  if (now - lastReadTime >= READ_INTERVAL) {
    lastReadTime = now;
    readSensors();
    applyControl();
  }

  // Push to Firebase every 10 seconds
  if (now - lastPumpPrimeTime >= FIREBASE_INTERVAL) {
    lastPumpPrimeTime = now;
    pushToFirebase();
    checkFirebaseConfig();
  }

  // Update flock day incrementally (every 24 hours real-time, or manually)
  static unsigned long lastDayCheck = 0;
  if (now - lastDayCheck >= 86400000UL) { // 24 hours
    lastDayCheck = now;
    currentFlockDay++;
    climateProfile.setFlockDay(currentFlockDay);
    Serial.print("Flock day advanced to: ");
    Serial.println(currentFlockDay);
  }
}