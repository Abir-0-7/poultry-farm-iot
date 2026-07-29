"""
Hardware Anomaly Detection for Poultry Farm IoT System.

Detects:
- Heater failure: relay ON but temperature stagnates or drops
- Sensor drift: unexpected flatlines or spikes
- Fan failure: high NH3 with low fan RPM
- Communication gaps: missing data for extended periods
"""
import numpy as np
from datetime import datetime, timedelta
from collections import deque


class AnomalyDetector:
    """Real-time anomaly detection for poultry environmental hardware."""

    def __init__(self, window_size=15):
        self.window_size = window_size
        self.temp_history = deque(maxlen=window_size)
        self.nh3_history = deque(maxlen=window_size)
        self.fan_history = deque(maxlen=window_size)
        self.heater_states = deque(maxlen=window_size)
        self.timestamps = deque(maxlen=window_size)
        self.alerts = []

    def ingest(self, data_point):
        """
        Ingest a new data point for analysis.
        Expected keys: temperature, heater_state, ammonia_ppm, fan_speed, timestamp
        """
        self.timestamps.append(data_point.get('timestamp', datetime.now().isoformat()))
        self.temp_history.append(float(data_point.get('temperature', 0)))
        self.nh3_history.append(float(data_point.get('ammonia_ppm', 0)))
        self.fan_history.append(float(data_point.get('fan_speed', 0)))
        self.heater_states.append(bool(data_point.get('heater_state', False)))
        return self.detect()

    def detect(self):
        """Run all anomaly checks and return active alerts."""
        alerts = []

        alerts.extend(self._check_heater_failure())
        alerts.extend(self._check_fan_failure())
        alerts.extend(self._check_sensor_stall())
        alerts.extend(self._check_data_gap())

        return alerts

    def _check_heater_failure(self, lookback=6):
        """
        Heater failure detection:
        If heater is ON for multiple consecutive readings but temperature
        doesn't rise (or falls), the heating element may be broken.
        """
        alerts = []
        if len(self.temp_history) < lookback:
            return alerts

        recent_temps = list(self.temp_history)[-lookback:]
        recent_heaters = list(self.heater_states)[-lookback:]

        # Check if heater is consistently ON
        heater_on_ratio = sum(recent_heaters) / len(recent_heaters)
        if heater_on_ratio < 0.8:
            return alerts

        # Calculate temperature trend
        temps = np.array(recent_temps, dtype=float)
        if np.ptp(temps) < 0.3:
            # Temperature is flatlining
            alerts.append({
                'type': 'HEATER_FAILURE',
                'severity': 'CRITICAL',
                'message': 'Temperature flatlining with heater ON — possible burnt bulb or heater failure',
                'current_temp': float(temps[-1]),
                'temp_change': float(np.ptp(temps)),
                'detected_at': datetime.now().isoformat()
            })
        elif np.mean(np.diff(temps)) < -0.05:
            # Temperature is dropping while heater is ON
            alerts.append({
                'type': 'HEATER_FAILURE',
                'severity': 'WARNING',
                'message': 'Temperature dropping despite heater ON — check heating system',
                'current_temp': float(temps[-1]),
                'temp_trend': float(np.mean(np.diff(temps))),
                'detected_at': datetime.now().isoformat()
            })

        return alerts

    def _check_fan_failure(self, lookback=5):
        """
        Fan failure detection:
        If ammonia levels are high (>20ppm) but fan speed is low,
        the exhaust fan may have failed.
        """
        alerts = []
        if len(self.nh3_history) < lookback:
            return alerts

        recent_nh3 = list(self.nh3_history)[-lookback:]
        recent_fan = list(self.fan_history)[-lookback:]

        avg_nh3 = sum(recent_nh3) / len(recent_nh3)
        avg_fan = sum(recent_fan) / len(recent_fan)

        if avg_nh3 > 20 and avg_fan < 30:
            alerts.append({
                'type': 'FAN_FAILURE',
                'severity': 'HIGH',
                'message': f'Ammonia high ({avg_nh3:.1f} ppm) but fan speed low ({avg_fan:.0f}%) — possible fan failure',
                'avg_nh3': round(avg_nh3, 1),
                'avg_fan_speed': round(avg_fan, 1),
                'detected_at': datetime.now().isoformat()
            })

        return alerts

    def _check_sensor_stall(self, lookback=12, max_flat=8):
        """
        Sensor stall detection:
        If sensor values are identical for too long, the sensor may be stuck.
        """
        alerts = []

        for history, name in [(self.temp_history, 'Temperature'),
                              (self.nh3_history, 'Ammonia')]:
            if len(history) < max_flat:
                continue
            recent = list(history)[-max_flat:]
            if len(set(round(v, 3) for v in recent)) == 1:
                alerts.append({
                    'type': 'SENSOR_STALL',
                    'severity': 'MEDIUM',
                    'message': f'{name} sensor appears stuck (no change in {max_flat} readings)',
                    'stuck_value': recent[0],
                    'detected_at': datetime.now().isoformat()
                })

        return alerts

    def _check_data_gap(self, max_gap_minutes=5):
        """Check for communication gaps in data stream."""
        alerts = []
        if len(self.timestamps) < 2:
            return alerts

        try:
            last_ts = datetime.fromisoformat(
                list(self.timestamps)[-1].replace('Z', '+00:00').split('+')[0]
            )
            prev_ts = datetime.fromisoformat(
                list(self.timestamps)[-2].replace('Z', '+00:00').split('+')[0]
            )
            gap = (last_ts - prev_ts).total_seconds() / 60.0

            if gap > max_gap_minutes:
                alerts.append({
                    'type': 'DATA_GAP',
                    'severity': 'LOW',
                    'message': f'Data gap detected: {gap:.1f} minutes between readings',
                    'gap_minutes': round(gap, 1),
                    'detected_at': datetime.now().isoformat()
                })
        except Exception:
            pass

        return alerts

    def get_heating_efficiency(self):
        """
        Calculate heating efficiency score.
        Returns a dict with efficiency metrics for energy optimization.
        """
        if len(self.temp_history) < 10:
            return {'score': 100, 'cycles_per_hour': 0, 'duty_cycle': 0}

        temps = list(self.temp_history)
        heaters = list(self.heater_states)

        # Count heater cycles (ON->OFF transitions)
        cycles = sum(1 for i in range(1, len(heaters))
                     if heaters[i] != heaters[i - 1])

        # Duty cycle (percentage of time heater is ON)
        duty = sum(heaters) / max(len(heaters), 1) * 100

        # Efficiency score (fewer cycles = better, moderate duty = efficient)
        score = max(0, 100 - cycles * 2 - abs(duty - 40) * 0.5)

        return {
            'score': round(score, 1),
            'cycles_per_hour': round(cycles / 2, 1),  # approximate 10s readings => 2 cycles per 20s
            'duty_cycle': round(duty, 1)
        }
