#include "fuzzy_logic.h"

FuzzyLogic::FuzzyLogic() {
  temperature = 0;
  humidity = 0;
  ammonia = 0;
  targetTemp = 33;
  fanSpeed = 0;
  comfortScore = 100;
}

void FuzzyLogic::begin() {
  // Initialize fuzzy logic parameters
  Serial.println("Fuzzy Logic Controller ready");
}

void FuzzyLogic::setInputs(float temp, float hum, float nh3, float targTemp) {
  temperature = temp;
  humidity = hum;
  ammonia = nh3;
  targetTemp = targTemp;
}

void FuzzyLogic::compute() {
  float tempError = temperature - targetTemp;
  
  // FUZZIFICATION
  float coldVal = tempErrorCold(tempError);
  float comfortVal = tempErrorComfort(tempError);
  float hotVal = tempErrorHot(tempError);
  
  float nh3LowVal = nh3Low(ammonia);
  float nh3MedVal = nh3Medium(ammonia);
  float nh3HighVal = nh3High(ammonia);
  
  // RULE EVALUATION (Mamdani style)
  // Rule 1: IF temp is COLD AND NH3 is low => FAN LOW
  float rule1 = fuzzifyAND(coldVal, nh3LowVal);
  
  // Rule 2: IF temp is COLD AND NH3 is medium => FAN LOW
  float rule2 = fuzzifyAND(coldVal, nh3MedVal);
  
  // Rule 3: IF temp is COLD AND NH3 is high => FAN MEDIUM (purge needed)
  float rule3 = fuzzifyAND(coldVal, nh3HighVal);
  
  // Rule 4: IF temp is COMFORT AND NH3 is low => FAN LOW
  float rule4 = fuzzifyAND(comfortVal, nh3LowVal);
  
  // Rule 5: IF temp is COMFORT AND NH3 is medium => FAN MEDIUM
  float rule5 = fuzzifyAND(comfortVal, nh3MedVal);
  
  // Rule 6: IF temp is COMFORT AND NH3 is high => FAN HIGH (health risk)
  float rule6 = fuzzifyAND(comfortVal, nh3HighVal);
  
  // Rule 7: IF temp is HOT AND NH3 is low => FAN MEDIUM (cooling)
  float rule7 = fuzzifyAND(hotVal, nh3LowVal);
  
  // Rule 8: IF temp is HOT AND NH3 is medium => FAN HIGH
  float rule8 = fuzzifyAND(hotVal, nh3MedVal);
  
  // Rule 9: IF temp is HOT AND NH3 is high => FAN HIGH (emergency)
  float rule9 = fuzzifyAND(hotVal, nh3HighVal);
  
  // AGGREGATION – Combine rule outputs for LOW, MEDIUM, HIGH fan
  float fanLowOutput = fuzzifyOR(fuzzifyOR(rule1, rule2), rule4);
  float fanMedOutput = fuzzifyOR(fuzzifyOR(rule3, rule5), rule7);
  float fanHighOutput = fuzzifyOR(fuzzifyOR(rule6, rule8), rule9);
  
  // DEFUZZIFICATION – Centroid method
  // Fan LOW => ~64, MEDIUM => ~160, HIGH => ~255
  fanSpeed = (int)defuzzifyCentroid(fanLowOutput * 64, fanMedOutput * 160, fanHighOutput * 255);
  fanSpeed = constrain(fanSpeed, 0, 255);
  
  // COMFORT SCORE (inverse of distress)
  float penalty = 0;
  if (abs(tempError) > 3) penalty += 30;
  if (ammonia > 25) penalty += 40;
  if (ammonia > 50) penalty += 20;
  if (humidity < 40 || humidity > 80) penalty += 10;
  comfortScore = (int)constrain(100 - penalty, 0, 100);
  if (nh3HighVal > 0.5) comfortScore = constrain(comfortScore - 15, 0, 100);
}

int FuzzyLogic::getFanSpeed() {
  return fanSpeed;
}

int FuzzyLogic::getComfortScore() {
  return comfortScore;
}

// ==================== MEMBERSHIP FUNCTIONS ====================

// Temperature Error (difference from target)
float FuzzyLogic::tempErrorCold(float err) {
  // Cold: error < -3°C
  if (err <= -5) return 1.0;
  if (err >= -1) return 0.0;
  return (-err - 1) / 4.0;  // Linear between -5 and -1
}

float FuzzyLogic::tempErrorComfort(float err) {
  // Comfort: error between -2°C and +2°C
  if (err <= -3 || err >= 3) return 0.0;
  if (err >= -1 && err <= 1) return 1.0;
  if (err > -3 && err < -1) return (err + 3) / 2.0;
  return (3 - err) / 2.0;  // err > 1 && err < 3
}

float FuzzyLogic::tempErrorHot(float err) {
  // Hot: error > +3°C
  if (err >= 5) return 1.0;
  if (err <= 1) return 0.0;
  return (err - 1) / 4.0;
}

// Ammonia (NH3) levels
float FuzzyLogic::nh3Low(float nh3) {
  // Low: < 15 ppm
  if (nh3 <= 10) return 1.0;
  if (nh3 >= 20) return 0.0;
  return (20 - nh3) / 10.0;
}

float FuzzyLogic::nh3Medium(float nh3) {
  // Medium: 15-40 ppm
  if (nh3 <= 10 || nh3 >= 45) return 0.0;
  if (nh3 >= 15 && nh3 <= 35) return 1.0;
  if (nh3 > 10 && nh3 < 15) return (nh3 - 10) / 5.0;
  return (45 - nh3) / 10.0;  // nh3 > 35 && nh3 < 45
}

float FuzzyLogic::nh3High(float nh3) {
  // High: > 40 ppm
  if (nh3 >= 50) return 1.0;
  if (nh3 <= 35) return 0.0;
  return (nh3 - 35) / 15.0;
}

// Fan output membership
float FuzzyLogic::fanLow(float val) {
  if (val <= 0.2) return 1.0;
  if (val >= 0.5) return 0.0;
  return (0.5 - val) / 0.3;
}

float FuzzyLogic::fanMedium(float val) {
  if (val <= 0.3 || val >= 0.8) return 0.0;
  if (val >= 0.45 && val <= 0.65) return 1.0;
  if (val > 0.3 && val < 0.45) return (val - 0.3) / 0.15;
  return (0.8 - val) / 0.15;
}

float FuzzyLogic::fanHigh(float val) {
  if (val >= 0.8) return 1.0;
  if (val <= 0.5) return 0.0;
  return (val - 0.5) / 0.3;
}

// ==================== FUZZY OPERATORS ====================
float FuzzyLogic::fuzzifyAND(float a, float b) {
  return min(a, b);
}

float FuzzyLogic::fuzzifyOR(float a, float b) {
  return max(a, b);
}

float FuzzyLogic::defuzzifyCentroid(float low, float mid, float high) {
  float denominator = low + mid + high;
  if (denominator < 0.001) return 0.0;
  return (low * 64 + mid * 160 + high * 255) / denominator;
}
