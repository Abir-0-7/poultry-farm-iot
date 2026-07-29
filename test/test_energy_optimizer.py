"""
Unit tests for EnergyOptimizer module.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pytest
from datetime import datetime, timedelta
from energy_optimizer import EnergyOptimizer


class TestEnergyOptimizer:
    def setup_method(self):
        self.optimizer = EnergyOptimizer(heater_watts=2000, fan_watts=150, cost_per_kwh=0.12)

    def _make_point(self, hours_ago=0, **overrides):
        ts = datetime.now() - timedelta(hours=hours_ago)
        base = {
            'temperature': 30.0,
            'humidity': 55.0,
            'ammonia_ppm': 10.0,
            'fan_speed': 50,
            'heater_state': False,
            'comfort_score': 85,
            'timestamp': ts.isoformat()
        }
        base.update(overrides)
        return base

    def test_empty_optimizer_returns_zero(self):
        """No data should return zeros not crash."""
        result = self.optimizer.compute_savings()
        assert result['kwh_saved'] == 0
        assert 'message' in result

    def test_savings_with_smart_control(self):
        """Smart control (less heater usage) should show savings vs 24/7 baseline."""
        points = []
        for i in range(20):
            # Smart: heater only ON 30% of time
            points.append(self._make_point(
                hours_ago=i * 0.1667,  # ~10 minute intervals
                heater_state=(i % 3 == 0),  # ON every 3rd reading
                fan_speed=40
            ))

        self.optimizer.ingest(points)
        result = self.optimizer.compute_savings()

        assert result['kwh_saved'] >= 0
        assert result['cost_saved'] >= 0
        assert result['baseline_kwh'] > 0
        assert result['efficiency_pct'] >= 0
        assert 0 <= result['heater_duty_cycle_pct'] <= 100

    def test_monthly_projection_calculation(self):
        """Monthly projection should scale partial period to 30 days."""
        savings = {
            'kwh_saved': 10.0,
            'cost_saved': 1.20,
            'co2_avoided_kg': 5.0,
            'analysis_period_hours': 2.0
        }
        monthly = EnergyOptimizer.calculate_monthly_projection(savings)

        # Should scale by factor: (24/2) * 30 = 360
        expected_monthly_kwh = 10.0 * (24.0 / 2.0) * 30
        assert monthly['monthly_kwh_saved'] == pytest.approx(expected_monthly_kwh, rel=0.01)
        assert monthly['monthly_cost_saved'] > savings['cost_saved']
        assert 'annual_cost_saved' in monthly

    def test_age_based_comparison(self):
        """Age analysis should provide suggestions."""
        points = [
            self._make_point(hours_ago=i, temperature=32.0, target_temp=29.0, heater_state=True)
            for i in range(20)
        ]
        self.optimizer.ingest(points)
        analysis = self.optimizer.get_age_based_comparison()

        assert 'avg_actual_temp' in analysis
        assert 'avg_target_temp' in analysis
        assert isinstance(analysis['suggestions'], list)

    def test_excessive_heating_suggestion(self):
        """High heater duty cycle should trigger excessive heating suggestion."""
        points = [
            self._make_point(hours_ago=i, temperature=30.0, heater_state=True)
            for i in range(15)
        ]
        self.optimizer.ingest(points)
        analysis = self.optimizer.get_age_based_comparison()

        suggestions = [s for s in analysis['suggestions'] if s['type'] == 'EXCESSIVE_HEATING']
        assert len(suggestions) > 0

    def test_overheating_suggestion(self):
        """Actual temp > target + 2 should trigger overheating suggestion."""
        points = [
            self._make_point(hours_ago=i, temperature=33.0, target_temp=29.0, heater_state=False)
            for i in range(15)
        ]
        self.optimizer.ingest(points)
        analysis = self.optimizer.get_age_based_comparison()

        suggestions = [s for s in analysis['suggestions'] if s['type'] == 'OVERHEATING']
        assert len(suggestions) > 0

    def test_underheating_suggestion(self):
        """Actual temp < target - 1 with low heater duty should suggest underheating."""
        points = [
            self._make_point(hours_ago=i, temperature=26.0, target_temp=29.0, heater_state=False)
            for i in range(15)
        ]
        self.optimizer.ingest(points)
        analysis = self.optimizer.get_age_based_comparison()

        suggestions = [s for s in analysis['suggestions'] if s['type'] == 'UNDERHEATING']
        assert len(suggestions) > 0, f"Expected UNDERHEATING suggestion, got: {analysis['suggestions']}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
