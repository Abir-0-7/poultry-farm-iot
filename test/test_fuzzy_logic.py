"""
Unit tests for Fuzzy Logic (Python port for testing).

This tests the algorithm that runs on the ESP32.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pytest


# Python port of the C++ FuzzyLogic class for testing
class FuzzyLogicPy:
    """Python implementation mirroring ESP32 FuzzyLogic class."""
    
    def __init__(self):
        self.temperature = 0.0
        self.humidity = 0.0
        self.ammonia = 0.0
        self.target_temp = 33.0
        self.fan_speed = 0
        self.comfort_score = 100
    
    def set_inputs(self, temp, hum, nh3, target_temp):
        self.temperature = temp
        self.humidity = hum
        self.ammonia = nh3
        self.target_temp = target_temp
    
    def compute(self):
        temp_error = self.temperature - self.target_temp
        
        # Fuzzification
        cold_val = self._temp_error_cold(temp_error)
        comfort_val = self._temp_error_comfort(temp_error)
        hot_val = self._temp_error_hot(temp_error)
        
        nh3_low = self._nh3_low(self.ammonia)
        nh3_med = self._nh3_medium(self.ammonia)
        nh3_high = self._nh3_high(self.ammonia)
        
        # Rules (same 9 rules as C++ version)
        rule1 = min(cold_val, nh3_low)       # COLD + NH3 LOW => FAN LOW
        rule2 = min(cold_val, nh3_med)        # COLD + NH3 MED => FAN LOW
        rule3 = min(cold_val, nh3_high)       # COLD + NH3 HIGH => FAN MED (purge)
        rule4 = min(comfort_val, nh3_low)     # COMFORT + NH3 LOW => FAN LOW
        rule5 = min(comfort_val, nh3_med)     # COMFORT + NH3 MED => FAN MED
        rule6 = min(comfort_val, nh3_high)    # COMFORT + NH3 HIGH => FAN HIGH
        rule7 = min(hot_val, nh3_low)         # HOT + NH3 LOW => FAN MED (cooling)
        rule8 = min(hot_val, nh3_med)         # HOT + NH3 MED => FAN HIGH
        rule9 = min(hot_val, nh3_high)        # HOT + NH3 HIGH => FAN HIGH (emergency)
        
        # Aggregate
        fan_low_output = max(max(rule1, rule2), rule4)
        fan_med_output = max(max(rule3, rule5), rule7)
        fan_high_output = max(max(rule6, rule8), rule9)
        
        # Defuzzify (centroid)
        denom = fan_low_output + fan_med_output + fan_high_output
        if denom < 0.001:
            self.fan_speed = 0
        else:
            self.fan_speed = int((fan_low_output * 64 + fan_med_output * 160 + fan_high_output * 255) / denom)
        
        self.fan_speed = max(0, min(255, self.fan_speed))
        
        # Comfort score
        penalty = 0
        if abs(temp_error) > 3:
            penalty += 30
        if self.ammonia > 25:
            penalty += 40
        if self.ammonia > 50:
            penalty += 20
        if self.humidity < 40 or self.humidity > 80:
            penalty += 10
        self.comfort_score = max(0, min(100, int(100 - penalty)))
        if nh3_high > 0.5:
            self.comfort_score = max(0, self.comfort_score - 15)
    
    def get_fan_speed(self):
        return self.fan_speed
    
    def get_comfort_score(self):
        return self.comfort_score
    
    # Membership functions (same as C++)
    @staticmethod
    def _temp_error_cold(err):
        if err <= -5: return 1.0
        if err >= -1: return 0.0
        return (-err - 1) / 4.0
    
    @staticmethod
    def _temp_error_comfort(err):
        if err <= -3 or err >= 3: return 0.0
        if err >= -1 and err <= 1: return 1.0
        if err > -3 and err < -1: return (err + 3) / 2.0
        return (3 - err) / 2.0
    
    @staticmethod
    def _temp_error_hot(err):
        if err >= 5: return 1.0
        if err <= 1: return 0.0
        return (err - 1) / 4.0
    
    @staticmethod
    def _nh3_low(nh3):
        if nh3 <= 10: return 1.0
        if nh3 >= 20: return 0.0
        return (20 - nh3) / 10.0
    
    @staticmethod
    def _nh3_medium(nh3):
        if nh3 <= 10 or nh3 >= 45: return 0.0
        if nh3 >= 15 and nh3 <= 35: return 1.0
        if nh3 > 10 and nh3 < 15: return (nh3 - 10) / 5.0
        return (45 - nh3) / 10.0
    
    @staticmethod
    def _nh3_high(nh3):
        if nh3 >= 50: return 1.0
        if nh3 <= 35: return 0.0
        return (nh3 - 35) / 15.0


class TestFuzzyLogic:
    def setup_method(self):
        self.fl = FuzzyLogicPy()
    
    # ---------- Cold Scenarios ----------
    
    def test_cold_low_nh3_fan_should_be_low(self):
        """Cold bird + clean air → minimal ventilation to conserve heat."""
        self.fl.set_inputs(temp=28, hum=55, nh3=5, target_temp=33)
        self.fl.compute()
        assert self.fl.get_fan_speed() < 128, \
            f"Fan should be LOW (<128) for cold+clean, got {self.fl.get_fan_speed()}"
    
    def test_cold_high_nh3_fan_should_ramp_up(self):
        """Cold but toxic air → still need to purge ammonia."""
        self.fl.set_inputs(temp=28, hum=55, nh3=55, target_temp=33)
        self.fl.compute()
        # Should be medium to high (need to purge despite cold)
        assert self.fl.get_fan_speed() > 60, \
            f"Fan should ramp up to purge NH3 even when cold, got {self.fl.get_fan_speed()}"
    
    # ---------- Comfort Scenarios ----------
    
    def test_comfort_clean_fan_should_be_low(self):
        """Perfect temperature + clean air → minimum ventilation."""
        self.fl.set_inputs(temp=33, hum=55, nh3=5, target_temp=33)
        self.fl.compute()
        assert self.fl.get_fan_speed() < 100, \
            f"Fan should be LOW in perfect conditions, got {self.fl.get_fan_speed()}"
    
    def test_comfort_high_nh3_fan_should_be_high(self):
        """Good temperature but toxic air → prioritize health."""
        self.fl.set_inputs(temp=33, hum=55, nh3=60, target_temp=33)
        self.fl.compute()
        assert self.fl.get_fan_speed() > 180, \
            f"Fan should be HIGH for toxic air, got {self.fl.get_fan_speed()}"
    
    # ---------- Hot Scenarios ----------
    
    def test_hot_low_nh3_fan_should_cool(self):
        """Hot but clean air → medium fan for cooling."""
        self.fl.set_inputs(temp=38, hum=55, nh3=5, target_temp=33)
        self.fl.compute()
        assert self.fl.get_fan_speed() > 120, \
            f"Fan should be >120 for cooling, got {self.fl.get_fan_speed()}"
    
    def test_hot_high_nh3_fan_should_be_maximum(self):
        """Hot AND toxic → emergency maximum ventilation."""
        self.fl.set_inputs(temp=40, hum=55, nh3=70, target_temp=33)
        self.fl.compute()
        assert self.fl.get_fan_speed() > 200, \
            f"Fan should be near-max in emergency, got {self.fl.get_fan_speed()}"
    
    # ---------- Edge Cases ----------
    
    def test_extreme_values_do_not_crash(self):
        """Extreme sensor values should not crash or produce invalid output."""
        self.fl.set_inputs(temp=0, hum=0, nh3=0, target_temp=33)
        self.fl.compute()
        assert 0 <= self.fl.get_fan_speed() <= 255
        assert 0 <= self.fl.get_comfort_score() <= 100
        
        self.fl.set_inputs(temp=60, hum=100, nh3=200, target_temp=33)
        self.fl.compute()
        assert 0 <= self.fl.get_fan_speed() <= 255
        assert 0 <= self.fl.get_comfort_score() <= 100
    
    def test_fan_speed_never_exceeds_255(self):
        """PWM output must be within 0-255."""
        test_cases = [
            (20, 30, 0, 33),
            (50, 90, 100, 33),
            (35, 60, 50, 33),
            (25, 45, 80, 33),
        ]
        for temp, hum, nh3, target in test_cases:
            self.fl.set_inputs(temp, hum, nh3, target)
            self.fl.compute()
            assert 0 <= self.fl.get_fan_speed() <= 255, \
                f"Fan speed {self.fl.get_fan_speed()} out of range for ({temp},{hum},{nh3})"
    
    def test_cold_extreme_fan_is_low(self):
        """Very cold with no ammonia → minimum ventilation for O2/CO2 exchange."""
        self.fl.set_inputs(temp=20, hum=50, nh3=0, target_temp=33)
        self.fl.compute()
        assert self.fl.get_fan_speed() < 100, \
            f"Fan should be minimum ventilation for cold+clean, got {self.fl.get_fan_speed()}"
    
    def test_comfort_score_maximum(self):
        """Perfect conditions should give maximum comfort score."""
        self.fl.set_inputs(temp=33, hum=55, nh3=5, target_temp=33)
        self.fl.compute()
        assert self.fl.get_comfort_score() >= 90, \
            f"Perfect conditions should score >=90, got {self.fl.get_comfort_score()}"
    
    def test_comfort_score_minimum(self):
        """Terrible conditions should give very low comfort."""
        self.fl.set_inputs(temp=42, hum=90, nh3=80, target_temp=33)
        self.fl.compute()
        assert self.fl.get_comfort_score() < 40, \
            f"Terrible conditions should score <40, got {self.fl.get_comfort_score()}"
    
    # ---------- Membership Function Tests ----------
    
    def test_membership_cold(self):
        assert FuzzyLogicPy._temp_error_cold(-7) == 1.0
        assert FuzzyLogicPy._temp_error_cold(0) == 0.0
        assert 0 < FuzzyLogicPy._temp_error_cold(-3) < 1.0
    
    def test_membership_comfort(self):
        assert FuzzyLogicPy._temp_error_comfort(0) == 1.0
        assert FuzzyLogicPy._temp_error_comfort(4) == 0.0
    
    def test_membership_hot(self):
        assert FuzzyLogicPy._temp_error_hot(6) == 1.0
        assert FuzzyLogicPy._temp_error_hot(0) == 0.0
    
    def test_membership_nh3_low(self):
        assert FuzzyLogicPy._nh3_low(5) == 1.0
        assert FuzzyLogicPy._nh3_low(25) == 0.0
    
    def test_membership_nh3_high(self):
        assert FuzzyLogicPy._nh3_high(55) == 1.0
        assert FuzzyLogicPy._nh3_high(30) == 0.0
    
    # ---------- Dynamic Age Profile Tests ----------
    
    def test_different_age_targets_produce_different_outputs(self):
        """Colder target (older birds) should produce less fan for same temp."""
        # Young chicks (target 33°C) at 30°C — cold!
        self.fl.set_inputs(temp=30, hum=55, nh3=10, target_temp=33)
        self.fl.compute()
        young_fan = self.fl.get_fan_speed()
        
        # Older birds (target 21°C) at 30°C — hot!
        self.fl.set_inputs(temp=30, hum=55, nh3=10, target_temp=21)
        self.fl.compute()
        old_fan = self.fl.get_fan_speed()
        
        assert old_fan > young_fan, \
            f"Same 30°C: old birds (target 21) fan={old_fan} should be > young birds (target 33) fan={young_fan}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
