#ifndef FUZZY_LOGIC_H
#define FUZZY_LOGIC_H

#include <Arduino.h>

class FuzzyLogic {
public:
  FuzzyLogic();
  void begin();
  void setInputs(float temp, float hum, float nh3, float targetTemp);
  void compute();
  int getFanSpeed();       // 0-255
  int getComfortScore();   // 0-100

private:
  float temperature;
  float humidity;
  float ammonia;
  float targetTemp;
  int fanSpeed;
  int comfortScore;
  
  // Membership functions
  float tempErrorCold(float err);
  float tempErrorComfort(float err);
  float tempErrorHot(float err);
  float nh3Low(float nh3);
  float nh3Medium(float nh3);
  float nh3High(float nh3);
  float fanLow(float val);
  float fanMedium(float val);
  float fanHigh(float val);

  float fuzzifyAND(float a, float b);
  float fuzzifyOR(float a, float b);
  float defuzzifyCentroid(float low, float mid, float high);
};

#endif
