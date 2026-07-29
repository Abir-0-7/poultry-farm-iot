#ifndef ACOUSTIC_DETECTOR_H
#define ACOUSTIC_DETECTOR_H

#include <Arduino.h>

class AcousticDetector {
public:
  AcousticDetector(int micPin);
  void begin();
  bool checkDistress();
  float getConfidence();
  float analyzeFrequencyBand(int samples[], int numSamples, int samplingRate);

private:
  int micPin;
  float distressConfidence;
  unsigned long lastSampleTime;
  float movingAvgEnergy;
  int consecutiveDetections;
  
  // Frequency bands for chick distress calls (3-5 kHz typical)
  float computeSpectralEnergy(float freqLow, float freqHigh, int samples[], int numSamples);
};

#endif
