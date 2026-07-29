"""
Energy Cost Optimization Analyzer for Poultry Farm IoT.

Compares dynamic age-based climate profiling versus fixed 24/7 baseline
to calculate electricity savings and ROI.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json


class EnergyOptimizer:
    """
    Calculates energy savings from dynamic climate profiling.
    
    Assumptions:
    - Heater power: 2000W (typical poultry heat lamp)
    - Exhaust fan power: 150W (typical 18" exhaust fan)
    - Electricity cost: $0.12/kWh (configurable)
    - Baseline: 24/7 heater ON (traditional method)
    """

    def __init__(self, heater_watts=2000, fan_watts=150, cost_per_kwh=0.12):
        self.heater_watts = heater_watts
        self.fan_watts = fan_watts
        self.cost_per_kwh = cost_per_kwh
        self.history = []

    def ingest(self, data_points: List[Dict]) -> None:
        """Ingest historical data for analysis."""
        self.history.extend(data_points)
        cutoff = datetime.now() - timedelta(days=7)
        self.history = [
            p for p in self.history
            if self._parse_timestamp(p.get('timestamp', '')) > cutoff
        ]

    def compute_savings(self) -> Dict:
        """
        Compute energy savings compared to 24/7 baseline.
        
        Returns dictionary with:
        - kwh_saved: Total energy saved (kWh)
        - cost_saved: Money saved ($)
        - baseline_kwh: What 24/7 operation would use
        - actual_kwh: What the smart system actually used
        - efficiency_pct: Percentage improvement
        - co2_avoided: Estimated CO2 avoided (kg)
        """
        if len(self.history) < 10:
            return {
                'kwh_saved': 0,
                'cost_saved': 0,
                'baseline_kwh': 0,
                'actual_kwh': 0,
                'efficiency_pct': 0,
                'co2_avoided': 0,
                'message': 'Insufficient data for analysis (need 10+ data points)'
            }

        heater_on_count = sum(1 for p in self.history if p.get('heater_state', False))
        fan_on_count = sum(1 for p in self.history if float(p.get('fan_speed', 0)) > 10)
        total_samples = len(self.history)

        sample_hours = self._estimate_sample_interval_hours()

        baseline_heater_kwh = (self.heater_watts / 1000) * total_samples * sample_hours
        baseline_fan_kwh = (self.fan_watts / 1000) * total_samples * sample_hours
        baseline_kwh = baseline_heater_kwh + baseline_fan_kwh

        actual_heater_kwh = (self.heater_watts / 1000) * heater_on_count * sample_hours
        
        total_fan_percent = sum(
            min(float(p.get('fan_speed', 0)), 100) / 100.0
            for p in self.history
        )
        actual_fan_kwh = (self.fan_watts / 1000) * total_fan_percent * sample_hours
        actual_kwh = actual_heater_kwh + actual_fan_kwh
        kwh_saved = max(0, baseline_kwh - actual_kwh)
        cost_saved = kwh_saved * self.cost_per_kwh
        efficiency_pct = (kwh_saved / max(baseline_kwh, 0.001)) * 100
        co2_avoided = kwh_saved * 0.5

        return {
            'kwh_saved': round(kwh_saved, 2),
            'cost_saved': round(cost_saved, 2),
            'baseline_kwh': round(baseline_kwh, 2),
            'actual_kwh': round(actual_kwh, 2),
            'efficiency_pct': round(efficiency_pct, 1),
            'co2_avoided_kg': round(co2_avoided, 2),
            'heater_duty_cycle_pct': round(heater_on_count / max(total_samples, 1) * 100, 1),
            'analysis_period_hours': round(total_samples * sample_hours, 1),
            'message': f"Smart control saved {cost_saved:.2f} USD ({efficiency_pct:.1f}% more efficient)"
        }

    def get_age_based_comparison(self) -> Dict:
        """
        Compare current flock day's energy usage vs recommended profile.
        Returns optimization suggestions.
        """
        if not self.history:
            return {'suggestions': []}

        recent = self.history[-20:]
        avg_temp = sum(float(p.get('temperature', 0)) for p in recent) / len(recent)
        avg_target = sum(float(p.get('target_temp', 33)) for p in recent) / len(recent)
        heater_pct = sum(1 for p in recent if p.get('heater_state')) / len(recent) * 100

        suggestions = []

        if avg_temp > avg_target + 2:
            suggestions.append({
                'type': 'OVERHEATING',
                'impact': 'HIGH',
                'suggestion': 'Reduce target temperature or check heater overrun',
                'potential_savings': '5-15%'
            })

        if heater_pct < 20 and avg_temp < avg_target - 1:
            suggestions.append({
                'type': 'UNDERHEATING',
                'impact': 'HIGH',
                'suggestion': 'Check heating system capacity — birds may be cold-stressed',
                'potential_savings': 'N/A (welfare risk)'
            })

        if heater_pct > 60:
            suggestions.append({
                'type': 'EXCESSIVE_HEATING',
                'impact': 'MEDIUM',
                'suggestion': 'Consider insulation improvements to reduce heating load',
                'potential_savings': '10-25%'
            })

        return {
            'avg_actual_temp': round(avg_temp, 1),
            'avg_target_temp': round(avg_target, 1),
            'heater_duty_pct': round(heater_pct, 1),
            'suggestions': suggestions
        }

    def _estimate_sample_interval_hours(self) -> float:
        """Estimate the average time between samples in hours."""
        if len(self.history) < 2:
            return 1.0 / 360.0  # Default ~10 seconds

        timestamps = []
        for p in self.history[:50]:
            ts = self._parse_timestamp(p.get('timestamp', ''))
            if ts:
                timestamps.append(ts)

        if len(timestamps) < 2:
            return 1.0 / 360.0

        intervals = []
        for i in range(1, len(timestamps)):
            delta = (timestamps[i] - timestamps[i-1]).total_seconds()
            intervals.append(abs(delta))

        avg_seconds = sum(intervals) / len(intervals)
        return avg_seconds / 3600.0

    @staticmethod
    def _parse_timestamp(ts_str: str) -> Optional[datetime]:
        """Parse ISO timestamp string."""
        try:
            return datetime.fromisoformat(
                ts_str.replace('Z', '+00:00').split('+')[0]
            )
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def calculate_monthly_projection(savings_dict: Dict) -> Dict:
        """
        Project a partial analysis period's savings to 30 days.
        """
        hours = savings_dict.get('analysis_period_hours', 24)
        if hours <= 0:
            hours = 24

        daily_factor = 24.0 / hours
        monthly_factor = daily_factor * 30

        return {
            'monthly_kwh_saved': round(savings_dict.get('kwh_saved', 0) * monthly_factor, 1),
            'monthly_cost_saved': round(savings_dict.get('cost_saved', 0) * monthly_factor, 2),
            'annual_cost_saved': round(savings_dict.get('cost_saved', 0) * monthly_factor * 12, 2),
            'monthly_co2_avoided_kg': round(savings_dict.get('co2_avoided_kg', 0) * monthly_factor, 1),
        }
