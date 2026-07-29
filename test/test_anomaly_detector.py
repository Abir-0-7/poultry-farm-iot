"""
Unit tests for AnomalyDetector module.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pytest
from datetime import datetime, timedelta
from anomaly_detector import AnomalyDetector


class TestAnomalyDetector:
    def setup_method(self):
        self.detector = AnomalyDetector(window_size=15)

    def _make_point(self, **overrides):
        """Create a standard data point."""
        base = {
            'temperature': 30.0,
            'humidity': 55.0,
            'ammonia_ppm': 10.0,
            'fan_speed': 50,
            'heater_state': False,
            'comfort_score': 85,
            'timestamp': datetime.now().isoformat()
        }
        base.update(overrides)
        return base

    def test_no_alerts_on_normal_data(self):
        """Normal data should not trigger any alerts."""
        for i in range(10):
            alerts = self.detector.ingest(self._make_point(temperature=30.0 + i * 0.1, ammonia_ppm=10.0 + i * 0.5))
            assert len(alerts) == 0, f"Unexpected alert at iteration {i}: {alerts}"

    def test_heater_failure_detection(self):
        """Heater ON but temperature flatlines = failure detected."""
        # Feed 8 points with heater ON and temperature NOT rising
        for i in range(8):
            point = self._make_point(
                temperature=28.0,  # Flatline
                heater_state=True
            )
            alerts = self.detector.ingest(point)

        alerts = self.detector.detect()
        heater_alerts = [a for a in alerts if a['type'] == 'HEATER_FAILURE']
        assert len(heater_alerts) > 0, f"Should detect heater failure, got: {alerts}"
        assert heater_alerts[0]['severity'] in ('CRITICAL', 'WARNING')

    def test_heater_failure_temp_dropping(self):
        """Heater ON but temperature dropping should trigger warning."""
        for i in range(8):
            point = self._make_point(
                temperature=30.0 - i * 0.3,  # Dropping
                heater_state=True
            )
            self.detector.ingest(point)

        alerts = self.detector.detect()
        heater_alerts = [a for a in alerts if a['type'] == 'HEATER_FAILURE']
        assert len(heater_alerts) > 0

    def test_fan_failure_detection(self):
        """High ammonia + low fan should detect fan failure."""
        for i in range(8):
            point = self._make_point(
                ammonia_ppm=30.0,
                fan_speed=10  # Very low fan speed
            )
            self.detector.ingest(point)

        alerts = self.detector.detect()
        fan_alerts = [a for a in alerts if a['type'] == 'FAN_FAILURE']
        assert len(fan_alerts) > 0, f"Should detect fan failure, got: {alerts}"

    def test_sensor_stall_detection(self):
        """Identical sensor values for many readings should trigger stall alert."""
        for i in range(12):
            point = self._make_point(temperature=25.5)  # Same value every time
            self.detector.ingest(point)

        alerts = self.detector.detect()
        stall_alerts = [a for a in alerts if a['type'] == 'SENSOR_STALL']
        assert len(stall_alerts) > 0, f"Should detect sensor stall, got: {alerts}"

    def test_heating_efficiency(self):
        """Test heating efficiency calculation."""
        for i in range(20):
            point = self._make_point(
                temperature=28.0 + (i % 3) * 2,
                heater_state=(i % 3 == 0)
            )
            self.detector.ingest(point)

        efficiency = self.detector.get_heating_efficiency()
        assert 'score' in efficiency
        assert 'duty_cycle' in efficiency
        assert 0 <= efficiency['score'] <= 100
        assert 0 <= efficiency['duty_cycle'] <= 100

    def test_empty_detector_no_crash(self):
        """Empty detector should handle queries gracefully."""
        detector = AnomalyDetector()
        alerts = detector.detect()
        assert alerts == []
        eff = detector.get_heating_efficiency()
        assert eff['score'] == 100


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
