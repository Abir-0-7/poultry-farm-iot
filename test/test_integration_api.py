"""
End-to-end integration test for the Poultry Farm IoT Backend API.
Starts a Flask test server, feeds demo data, and validates all endpoints.
"""
import sys
import os
import json
import threading
import time
import requests

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app import app


class TestIntegrationAPI:
    """Full system integration tests against a live Flask server."""

    BASE_URL = 'http://127.0.0.1:5300'

    @classmethod
    def setup_class(cls):
        """Start Flask test server in background thread."""
        def run_server():
            app.run(host='127.0.0.1', port=5300, debug=False, use_reloader=False)

        cls.server_thread = threading.Thread(target=run_server, daemon=True)
        cls.server_thread.start()
        time.sleep(2)  # Wait for server to start
        print('Flask test server running on port 5300')

    def test_health_check(self):
        """Verify the server is running."""
        resp = requests.get(f'{self.BASE_URL}/api/health', timeout=5)
        assert resp.status_code == 200
        data = resp.json()
        assert data['status'] == 'healthy'
        assert data['version'] == '2.0.0'

    def test_demo_data_ingestion(self):
        """Feed demo sensor data and verify ingestion."""
        # Feed 20 simulated data points
        demo_points = []
        for i in range(20):
            demo_points.append({
                'temperature': 30.0 + i * 0.2,
                'humidity': 55.0,
                'ammonia_ppm': 10.0 + i * 0.5,
                'fan_speed': 40 + (i % 3) * 20,
                'heater_state': (i % 4 == 0),
                'comfort_score': 85 - i,
                'distress_detected': (i == 10),  # One distress point
                'distress_confidence': 0.75 if i == 10 else 0.1,
                'flock_day': 14,
                'target_temp': 29.5,
                'system_status': 'NORMAL'
            })

        resp = requests.post(
            f'{self.BASE_URL}/api/demo',
            json=demo_points,
            timeout=10
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True
        assert data['points_ingested'] == 20
        assert data['buffer_size'] >= 20

    def test_live_endpoint(self):
        """GET /api/live should return demo data."""
        resp = requests.get(f'{self.BASE_URL}/api/live', timeout=5)
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True
        assert data['data'] is not None

    def test_history_endpoint(self):
        """GET /api/history should return ingested points."""
        resp = requests.get(f'{self.BASE_URL}/api/history?limit=10', timeout=5)
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True
        assert data['count'] <= 10

    def test_alerts_endpoint(self):
        """GET /api/alerts should return anomaly analysis."""
        # Ingest heater-failure pattern first
        failure_points = []
        for i in range(10):
            failure_points.append({
                'temperature': 28.0,  # Flatline
                'heater_state': True,  # Heater ON but no temp rise
                'ammonia_ppm': 10.0,
                'fan_speed': 30
            })
        requests.post(f'{self.BASE_URL}/api/demo', json=failure_points, timeout=5)

        resp = requests.get(f'{self.BASE_URL}/api/alerts', timeout=5)
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True
        # Should detect heater failure
        alerts = data.get('alerts', [])
        heater_alerts = [a for a in alerts if a['type'] == 'HEATER_FAILURE']
        assert len(heater_alerts) > 0, f'Heater failure not detected, alerts: {alerts}'

    def test_savings_endpoint(self):
        """GET /api/savings should return energy report."""
        resp = requests.get(f'{self.BASE_URL}/api/savings', timeout=5)
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True
        savings = data['savings']
        assert 'kwh_saved' in savings
        assert 'cost_saved' in savings
        assert 'efficiency_pct' in savings

    def test_config_endpoint(self):
        """POST /api/config should update configuration."""
        resp = requests.post(
            f'{self.BASE_URL}/api/config',
            json={'flock_start_day': 21},
            timeout=5
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True
        assert 'flock_start_day' in data['updated_keys']

    def test_cors_headers(self):
        """Verify CORS headers are present for dashboard access."""
        resp = requests.options(f'{self.BASE_URL}/api/live', timeout=5)
        # Flask-CORS should allow cross-origin requests
        assert resp.status_code in (200, 204), f'OPTIONS response: {resp.status_code}'

    def test_json_content_type(self):
        """All API responses should be JSON."""
        resp = requests.get(f'{self.BASE_URL}/api/health', timeout=5)
        assert resp.headers['Content-Type'].startswith('application/json')


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v', '--tb=short'])
