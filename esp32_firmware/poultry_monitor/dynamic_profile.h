#ifndef DYNAMIC_PROFILE_H
#define DYNAMIC_PROFILE_H

#include <Arduino.h>

class DynamicProfile {
public:
  DynamicProfile(int flockSize, int startDay);
  void setFlockDay(int day);
  int getFlockDay();
  float getTargetTemperature();
  float getTemperatureTolerance();
  float getTargetHumidity();
  float getAmmoniaThreshold();
  float getRecommendedVentilation(); // CFM per bird
  void printCurrentProfile();

private:
  int flockSize;
  int currentDay;
  float targetTemp;
  float tempTolerance;
  float targetHumidity;
  float nh3Threshold;
  
  // Age-specific temperature profile (Broiler chickens)
  float computeTargetTemp(int day);
  float computeTolerance(int day);
  float computeHumidityTarget(int day);
};

#endif
