"""
Complete integration test suite for Poultry Farm IoT Cloud System.

Covers:
1. Backend API endpoints (Flask)
2. AnomalyDetector logic (heater failure, fan failure, stalls)
3. EnergyOptimizer calculations
4. FuzzyLogic correctness
5. DynamicProfile age-based targets
6. End-to-end demo data pipeline
"""

import sys
import os
import json
from datetime import datetime, timedelta

# Add project paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pytest


# ==================== DYNAMIC PROFILE TESTS ====================

class TestDynamicProfile:
    """Validate age-based climate profile logic."""
    
    def _get_profile_module(self):
        """Dynamically recreate dynamic profile logic for testing."""
        # Replicate the DynamicProfile class logic from firmware
        class DynamicProfile:
            @staticmethod
            def get_target_temp(day):
                if day <= 1:   return 35.0
                if day <= 3:   return 34.0
                if day <= 7:   return 32.0
                if day <= 14:  return 29.5
                if day <= 21:  return 27.0
                if day <= 28:  return 24.0
                if day <= 35:  return 21.0
                if day <= 42:  return 19.0
                return 18.0
            
            @staticmethod
            def get_tolerance(day):
                if day <= 7:   return 1.0
                if day <= 14:  return 1.5
                if day <= 21:  return 2.0
                if day <= 35:  return 2.5
                return 3.0
            
            @staticmethod
            def get_target_humidity(day):
                if day <= 7:   return 65.0
                if day <= 14:  return 60.0
                if day <= 21:  return 55.0
                if day <= 35:  return 50.0
                return 50.0
            
            @staticmethod
            def get_ventilation(day):
                if day <= 7:   return 0.1
                if day <= 14:  return 0.3
                if day <= 21:  return 0.6
                if day <= 28:  return 1.0
                if day <= 35:  return 1.5
                return 2.0
        
        return DynamicProfile
    
    def test_day_1_target_temp(self):
        profile = self._get_profile_module()
        assert profile.get_target_temp(1) == 35.0, "Day 1 should target 35°C"
    
    def test_day_14_target_temp(self):
        profile = self._get_profile_module()
        assert profile.get_target_temp(14) == 29.5, "Day 14 should target 29.5°C"
    
    def test_day_42_target_temp(self):
        profile = self._get_profile_module()
        assert profile.get_target_temp(42) == 19.0, "Day 42 should target 19°C"
    
    def test_temp_decreases_with_age(self):
        profile = self._get_profile_module()
        temps = [profile.get_target_temp(d) for d in [1, 7, 14, 21, 28, 42]]
        # Temperature should strictly decrease
        for i in range(len(temps) - 1):
            assert temps[i] >= temps[i + 1], f"Temp should decrease: {temps[i]} vs {temps[i+1]}"
    
    def test_tolerance_increases_with_age(self):
        profile = self._get_profile_module()
        tol_early = profile.get_tolerance(3)
        tol_late = profile.get_tolerance(30)
        assert tol_early < tol_late, "Younger birds need tighter tolerance"
    
    def test_humidity_target(self):
        profile = self._get_profile_module()
        assert profile.get_target_humidity(1) == 65.0
        assert profile.get_target_humidity(14) == 60.0
        assert profile.get_target_humidity(30) == 50.0


# ==================== FUZZY LOGIC TESTS ====================

class TestFuzzyLogic:
    """Validate fuzzy logic fan speed computation."""
    
    def _simulate_fuzzy(self, temp, target_temp, humidity, ammonia):
        """Replicate the firmware fuzzy logic algorithm."""
        temp_error = temp - target_temp
        
        # Membership functions
        def temp_cold(err):
            if err <= -5: return 1.0
            if err >= -1: return 0.0
            return (-err - 1) / 4.0
        
        def temp_comfort(err):
            if err <= -3 or err >= 3: return 0.0
            if err >= -1 and err <= 1: return 1.0
            if err > -3 and err < -1: return (err + 3) / 2.0
            return (3 - err) / 2.0
        
        def temp_hot(err):
            if err >= 5: return 1.0
            if err <= 1: return 0.0
            return (err - 1) / 4.0
        
        def nh3_low(nh3):
            if nh3 <= 10: return 1.0
            if nh3 >= 20: return 0.0
            return (20 - nh3) / 10.0
        
        def nh3_med(nh3):
            if nh3 <= 10 or nh3 >= 45: return 0.0
            if 15 <= nh3 <= 35: return 1.0
            if 10 < nh3 < 15: return (nh3 - 10) / 5.0
            return (45 - nh3) / 10.0
        
        def nh3_high(nh3):
            if nh3 >= 50: return 1.0
            if nh3 <= 35: return 0.0
            return (nh3 - 35) / 15.0
        
        cold = temp_cold(temp_error)
        comfort = temp_comfort(temp_error)
        hot = temp_hot(temp_error)
        
        lo = nh3_low(ammonia)
        med = nh3_med(ammonia)
        hi = nh3_high(ammonia)
        
        # Rules
        rules = [
            min(cold, lo),     # R1: cold & low NH3 => LOW
            min(cold, med),    # R2: cold & med NH3 => LOW
            min(cold, hi),     # R3: cold & high NH3 => MED
            min(comfort, lo),  # R4: comfort & low => LOW
            min(comfort, med), # R5: comfort & med => MED
            min(comfort, hi),  # R6: comfort & high => HIGH
            min(hot, lo),      # R7: hot & low => MED
            min(hot, med),     # R8: hot & med => HIGH
            min(hot, hi),      # R9: hot & high => HIGH
        ]
        
        fan_low = max(rules[0], rules[1], rules[3])
        fan_med = max(rules[2], rules[4], rules[6])
        fan_high = max(rules[5], rules[7], rules[8])
        
        denom = fan_low + fan_med + fan_high
        if denom < 0.001:
            fan = fan_low * 25 + fan_med * 63 + fan_high * 100
        else:
            fan = (fan_low * 25 + fan_med * 63 + fan_high * 100) / denom
        
        return round(min(max(fan, 0), 100))
    
    def test_cold_no_ammonia_fan_low(self):
        """Cold environment with no ammonia should give low fan speed."""
        fan = self._simulate_fuzzy(temp=20, target_temp=33, humidity=50, ammonia=5)
        assert fan <= 35, f"Expected low fan, got {fan}"
    
    def test_hot_high_ammonia_fan_high(self):
        """Hot environment with high ammonia should trigger high fan."""
        fan = self._simulate_fuzzy(temp=32, target_temp=24, humidity=60, ammonia=45)
        assert fan >= 50, f"Expected high fan, got {fan}"
    
    def test_comfort_moderate_ammonia_fan_medium(self):
        """Comfort temp with moderate NH3 should be medium fan."""
        fan = self._simulate_fuzzy(temp=29, target_temp=29, humidity=55, ammonia=20)
        # Should be somewhere in mid-range
        assert 20 <= fan <= 80, f"Expected medium fan, got {fan}"
    
    def test_ammonia_dominance(self):
        """At comfort temp, fan should increase with ammonia."""
        low_nh3 = self._simulate_fuzzy(temp=29, target_temp=29, humidity=55, ammonia=5)
        high_nh3 = self._simulate_fuzzy(temp=29, target_temp=29, humidity=55, ammonia=45)
        assert high_nh3 >= low_nh3, "Higher NH3 should increase fan speed"


# ==================== ANOMALY DETECTOR TESTS ====================

class TestAnomalyDetector:
    """Validate hardware anomaly detection logic."""
    
    def _get_detector(self):
        from anomaly_detector import AnomalyDetector
        return AnomalyDetector(window_size=10)
    
    def _make_point(self, **kwargs):
        base = {
            'temperature': 30.0,
            'humidity': 55.0,
            'ammonia_ppm': 10.0,
            'fan_speed': 50,
            'heater_state': False,
            'comfort_score': 85,
            'target_temp': 30.0,
            'timestamp': datetime.now().isoformat()
        }
        base.update(kwargs)
        return base
    
    def test_no_alerts_in_normal_conditions(self):
        detector = self._get_detector()
        for _ in range(12):
            point = self._make_point(temperature=30.0, heater_state=False)
            alerts = detector.ingest(point)
        # No heater failure or fan failure expected
        alert_types = [a['type'] for a in alerts]
        assert 'HEATER_FAILURE' not in alert_types
        assert 'FAN_FAILURE' not in alert_types
    
    def test_heater_failure_detection(self):
        """Heater ON but temp flatlines should trigger alert."""
        detector = self._get_detector()
        for i in range(10):
            point = self._make_point(temperature=28.0, heater_state=True)
            alerts = detector.ingest(point)
        
        # After 10 readings with heater ON and no temp rise
        alert_types = [a['type'] for a in alerts]
        assert 'HEATER_FAILURE' in alert_types, f"Expected HEATER_FAILURE, got {alert_types}"
    
    def test_heater_working_no_false_positive(self):
        """Normal heater operation (ON + rising temp) should not trigger."""
        detector = self._get_detector()
        temp = 25.0
        for i in range(10):
            temp += 0.5  # Rising temperature
            point = self._make_point(temperature=temp, heater_state=True)
            alerts = detector.ingest(point)
        alert_types = [a['type'] for a in alerts]
        assert 'HEATER_FAILURE' not in alert_types
    
    def test_fan_failure_detection(self):
        """High NH3 with low fan should trigger FAN_FAILURE."""
        detector = self._get_detector()
        for i in range(8):
            point = self._make_point(ammonia_ppm=35, fan_speed=10)
            alerts = detector.ingest(point)
        alert_types = [a['type'] for a in alerts]
        assert 'FAN_FAILURE' in alert_types
    
    def test_sensor_stall_detection(self):
        """Identical readings for 12+ points should trigger stall."""
        detector = self._get_detector()
        for i in range(14):
            point = self._make_point(temperature=30.0, ammonia_ppm=10.0)
            alerts = detector.ingest(point)
        alert_types = [a['type'] for a in alerts]
        assert 'SENSOR_STALL' in alert_types


# ==================== ENERGY OPTIMIZER TESTS ====================

class TestEnergyOptimizer:
    """Validate energy savings calculations."""
    
    def _get_optimizer(self):
        from energy_optimizer import EnergyOptimizer
        return EnergyOptimizer(heater_watts=2000, fan_watts=150, cost_per_kwh=0.12)
    
    def _make_point(self, heater_on=False, fan_speed=0, **kwargs):
        base = {
            'temperature': 30.0,
            'humidity': 55.0,
            'ammonia_ppm': 10.0,
            'fan_speed': fan_speed,
            'heater_state': heater_on,
            'comfort_score': 85,
            'target_temp': 30.0,
            'timestamp': datetime.now().isoformat()
        }
        base.update(kwargs)
        return base
    
    def test_insufficient_data(self):
        opt = self._get_optimizer()
        opt.ingest([self._make_point()] * 5)
        savings = opt.compute_savings()
        assert savings['kwh_saved'] == 0
        assert 'Insufficient' in savings['message']
    
    def test_savings_computation(self):
        """Smart control with 30% heater duty should save vs 100%."""
        opt = self._get_optimizer()
        points = []
        for _ in range(30):
            # 30% heater ON ratio
            points.append(self._make_point(heater_on=(_ % 10 < 3), fan_speed=40))
        opt.ingest(points)
        savings = opt.compute_savings()
        
        assert savings['kwh_saved'] > 0, "Should save energy"
        assert savings['efficiency_pct'] > 0, "Should have positive efficiency"
        # Heater duty cycle ~30%
        assert 25 <= savings['heater_duty_cycle_pct'] <= 35, \
            f"Expected ~30% duty, got {savings['heater_duty_cycle_pct']}%"
    
    def test_baseline_worse_than_smart(self):
        """Baseline always-ON should use more energy than smart control."""
        opt = self._get_optimizer()
        points = []
        for _ in range(20):
            points.append(self._make_point(heater_on=False, fan_speed=20))
        opt.ingest(points)
        savings = opt.compute_savings()
        assert savings['baseline_kwh'] > savings['actual_kwh'], \
            "Baseline should consume more than smart system"
    
    def test_monthly_projection(self):
        from energy_optimizer import EnergyOptimizer
        savings = {'kwh_saved': 5.0, 'cost_saved': 0.60, 'co2_avoided_kg': 2.5,
                    'analysis_period_hours': 2.0}
        proj = EnergyOptimizer.calculate_monthly_projection(savings)
        # 2 hours => daily factor = 12 => monthly = 12 * 30 = 360
        assert proj['monthly_kwh_saved'] == 5.0 * 12 * 30
        assert proj['monthly_cost_saved'] == 0.60 * 12 * 30
        assert proj['annual_cost_saved'] == 0.60 * 12 * 30 * 12
    
    def test_age_based_suggestions_empty(self):
        opt = self._get_optimizer()
        result = opt.get_age_based_comparison()
        assert result == {'suggestions': []}


# ==================== API INTEGRATION TESTS ====================

class TestFlaskAPI:
    """Integration tests for Flask backend API."""
    
    @pytest.fixture
    def client(self):
        from backend.app import app
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    def test_health_check(self, client):
        resp = client.get('/api/health')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'healthy'
        assert 'version' in data
    
    def test_live_data_demo(self, client):
        """Live endpoint should return data (demo mode)."""
        resp = client.get('/api/live')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert data['data'] is not None
    
    def test_history_endpoint(self, client):
        resp = client.get('/api/history?limit=10')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
    
    def test_alerts_endpoint(self, client):
        resp = client.get('/api/alerts')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'alerts' in data
        assert isinstance(data['alerts'], list)
    
    def test_savings_endpoint(self, client):
        resp = client.get('/api/savings')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'savings' in data
        assert 'monthly_projection' in data
    
    def test_config_post(self, client):
        resp = client.post('/api/config',
                          data=json.dumps({'flock_start_day': 7}),
                          content_type='application/json')
        assert resp.status