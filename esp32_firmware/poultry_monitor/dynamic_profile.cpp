#include "dynamic_profile.h"

DynamicProfile::DynamicProfile(int size, int startDay) {
  flockSize = size;
  currentDay = startDay;
  targetTemp = computeTargetTemp(currentDay);
  tempTolerance = computeTolerance(currentDay);
  targetHumidity = computeHumidityTarget(currentDay);
  nh3Threshold = 25.0;
}

void DynamicProfile::setFlockDay(int day) {
  currentDay = day;
  targetTemp = computeTargetTemp(day);
  tempTolerance = computeTolerance(day);
  targetHumidity = computeHumidityTarget(day);
  printCurrentProfile();
}

int DynamicProfile::getFlockDay() {
  return currentDay;
}

float DynamicProfile::getTargetTemperature() {
  return targetTemp;
}

float DynamicProfile::getTemperatureTolerance() {
  return tempTolerance;
}

float DynamicProfile::getTargetHumidity() {
  return targetHumidity;
}

float DynamicProfile::getAmmoniaThreshold() {
  return nh3Threshold;
}

float DynamicProfile::getRecommendedVentilation() {
  // Ventilation rates increase with bird age/size (CFM per bird)
  if (currentDay <= 7) return 0.1;
  if (currentDay <= 14) return 0.3;
  if (currentDay <= 21) return 0.6;
  if (currentDay <= 28) return 1.0;
  if (currentDay <= 35) return 1.5;
  return 2.0;
}

void DynamicProfile::printCurrentProfile() {
  Serial.print("=== Flock Day ");
  Serial.print(currentDay);
  Serial.print(" | Target Temp: ");
  Serial.print(targetTemp);
  Serial.print("°C ± ");
  Serial.print(tempTolerance);
  Serial.print(" | Target RH: ");
  Serial.print(targetHumidity);
  Serial.println("% ===");
}

// ==================== AGE-SPECIFIC TEMPERATURE PROFILE ====================
// Based on standard broiler poultry guidelines
float DynamicProfile::computeTargetTemp(int day) {
  if (day <= 1) return 35.0;
  if (day <= 3) return 34.0;
  if (day <= 7) return 32.0;
  if (day <= 14) return 29.5;
  if (day <= 21) return 27.0;
  if (day <= 28) return 24.0;
  if (day <= 35) return 21.0;
  if (day <= 42) return 19.0;
  return 18.0;  // Day 43+ market weight
}

float DynamicProfile::computeTolerance(int day) {
  // Younger birds need tighter control
  if (day <= 7) return 1.0;
  if (day <= 14) return 1.5;
  if (day <= 21) return 2.0;
  if (day <= 35) return 2.5;
  return 3.0;
}

float DynamicProfile::computeHumidityTarget(int day) {
  // Higher humidity for young chicks, gradually reduce
  if (day <= 7) return 65.0;
  if (day <= 14) return 60.0;
  if (day <= 21) return 55.0;
  if (day <= 35) return 50.0;
  return 50.0;
}
