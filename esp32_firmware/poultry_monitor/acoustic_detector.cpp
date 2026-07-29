#include "acoustic_detector.h"

AcousticDetector::AcousticDetector(int pin) {
  micPin = pin;
  distressConfidence = 0.0;
}

void AcousticDetector::begin() {
  pinMode(micPin, INPUT);
  distressConfidence = 0.0;
  Serial.println("Acoustic Detector (Edge-AI) ready");
}

bool AcousticDetector::checkDistress() {
  const int NUM_SAMPLES = 256;
  const int SAMPLING_RATE = 8000; // 8kHz
  int samples[NUM_SAMPLES];
  
  // Collect audio samples
  unsigned long startTime = micros();
  for (int i = 0; i < NUM_SAMPLES; i++) {
    samples[i] = analogRead(micPin);
    delayMicroseconds(1000000 / SAMPLING_RATE);
  }
  unsigned long elapsed = micros() - startTime;
  
  // Analyze distress frequency band (3-5 kHz for chick calls)
  float distressEnergy = computeSpectralEnergy(3000, 5000, samples, NUM_SAMPLES);
  float totalEnergy = computeSpectralEnergy(200, 7000, samples, NUM_SAMPLES);
  
  // Calculate relative energy in distress band
  if (totalEnergy > 1.0) {
    distressConfidence = distressEnergy / totalEnergy;
  } else {
    distressConfidence = 0.0;
  }
  
  // Apply noise floor threshold
  if (distressConfidence < 0.15) distressConfidence = 0.0;
  
  // Normalize confidence
  distressConfidence = constrain(distressConfidence, 0.0, 1.0);
  
  return (distressConfidence > 0.6);
}

float AcousticDetector::getConfidence() {
  return distressConfidence;
}

float AcousticDetector::analyzeFrequencyBand(int samples[], int numSamples, int samplingRate) {
  // Simplified FFT-based energy analysis
  float energy = 0;
  for (int i = 0; i < numSamples; i++) {
    // Apply a simple bandpass filter via difference
    float val = samples[i] - 2048.0;  // Center around zero (12-bit ADC)
    energy += val * val;
  }
  return energy / (float)numSamples;
}

float AcousticDetector::computeSpectralEnergy(float freqLow, float freqHigh, 
                                                int samples[], int numSamples) {
  // Simplified spectral energy estimation using zero-crossing + peak detection
  // In production, this would use a proper FFT (e.g., arduinoFFT library)
  float energy = 0;
  int zeroCrossings = 0;
  int peaks = 0;
  long sumAmplitude = 0;
  
  for (int i = 1; i < numSamples; i++) {
    int diff = samples[i] - samples[i-1];
    sumAmplitude += abs(samples[i] - 2048);
    
    // Count zero crossings
    if ((samples[i] > 2048 && samples[i-1] <= 2048) || 
        (samples[i] <= 2048 && samples[i-1] > 2048)) {
      zeroCrossings++;
    }
    
    // Simple peak detection
    if (abs(samples[i] - 2048) > 1500) {
      peaks++;
    }
  }
  
  float avgAmplitude = sumAmplitude / (float)numSamples;
  float crossingRate = zeroCrossings / (float)(numSamples - 1);
  
  // Map crossing rate to frequency band relevance
  // 3000-5000 Hz distress band => crossing rate ~0.375-0.625 at 8kHz sampling
  float lowCrossing = (freqLow * 2.0) / (float)8000.0;
  float highCrossing = (freqHigh * 2.0) / (float)8000.0;
  
  if (crossingRate >= lowCrossing && crossingRate <= highCrossing) {
    energy = avgAmplitude * (1.0 + peaks * 0.01);
  } else {
    // Reduced weight outside target band
    float distFromBand = min(abs(crossingRate - lowCrossing), abs(crossingRate - highCrossing));
    energy = avgAmplitude * 0.1 / (1.0 + distFromBand * 10.0);
  }
  
  return energy / 100.0;  // Normalized
}
