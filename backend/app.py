"""
Flask API Backend for Poultry Farm IoT Monitor.

Endpoints:
- GET  /api/live       — Latest sensor data
- GET  /api/history    — Historical data
- GET  /api/alerts     — Active anomaly alerts
- GET  /api/savings    — Energy optimization report
- POST /api/config     — Update configuration
"""
import os
import json
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS

from firebase_config import init_firebase, fetch_live_data, fetch_history, fetch_config, set_config
from anomaly_detector import AnomalyDetector
from energy_optimizer import EnergyOptimizer


# ==================== APP INITIALIZATION ====================

app = Flask(__name__)
CORS(app)

# Initialize Firebase (will use test mode if no credentials)
try:
    init_firebase()
    firebase_available = True
except Exception as e:
    print(f"Firebase not available (running in test mode): {e}")
    firebase_available = False

# Initialize analytics engines
anomaly_detector = AnomalyDetector(window_size=15)
energy_optimizer = EnergyOptimizer(heater_watts=2000, fan_watts=150, cost_per_kwh=0.12)

# In-memory buffer for testing/demo
_buffer = []


# ==================== HELPER ====================

def _ingest_data_point(point):
    """Feed a data point into both analytics engines."""
    if point:
        anomaly_detector.ingest(point)
        energy_optimizer.ingest([point])
        _buffer.append(point)
        # Keep buffer manageable
        if len(_buffer) > 1000:
            _buffer.clear()


# ==================== API ROUTES ====================

@app.route('/api/live', methods=['GET'])
def get_live_data():
    """Return the latest sensor reading."""
    if firebase_available:
        data = fetch_live_data()
    else:
        data = _buffer[-1] if _buffer else _generate_demo_data()

    if data:
        _ingest_data_point(data)

    return jsonify({
        'success': True,
        'data': data,
        'firebase_connected': firebase_available
    })


@app.route('/api/history', methods=['GET'])
def get_history():
    """Return historical data with optional query params."""
    limit = request.args.get('limit', 100, type=int)

    if firebase_available:
        history = fetch_history(limit)
    else:
        history = _buffer[-limit:] if _buffer else []

    # Feed all historical points into analytics
    for point in history:
        _ingest_data_point(point)

    return jsonify({
        'success': True,
        'count': len(history),
        'data': history
    })


@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    """Return active anomaly alerts."""
    # Ingest latest data before checking
    if firebase_available:
        live = fetch_live_data()
    else:
        live = _buffer[-1] if _buffer else _generate_demo_data()

    if live:
        alerts = anomaly_detector.ingest(live)
    else:
        alerts = anomaly_detector.detect()

    efficiency = anomaly_detector.get_heating_efficiency()

    return jsonify({
        'success': True,
        'alerts': alerts,
        'alert_count': len(alerts),
        'heating_efficiency': efficiency
    })


@app.route('/api/savings', methods=['GET'])
def get_savings():
    """Return energy optimization report."""
    # Ensure we have data to analyze
    if firebase_available and len(_buffer) < 10:
        history = fetch_history(200)
        for p in history:
            energy_optimizer.ingest([p])

    savings = energy_optimizer.compute_savings()
    monthly = EnergyOptimizer.calculate_monthly_projection(savings)
    age_comparison = energy_optimizer.get_age_based_comparison()

    return jsonify({
        'success': True,
        'savings': savings,
        'monthly_projection': monthly,
        'age_analysis': age_comparison
    })


@app.route('/api/config', methods=['POST'])
def update_config():
    """Update system configuration (flock day, manual override, etc.)."""
    body = request.get_json()
    if not body:
        return jsonify({'success': False, 'error': 'No JSON body provided'}), 400

    updated = {}
    for key in ['flock_start_day', 'manual_override', 'target_temp_override']:
        if key in body:
            if firebase_available:
                set_config(key, body[key])
            updated[key] = body[key]

    return jsonify({
        'success': True,
        'updated_keys': updated
    })


@app.route('/api/demo', methods=['POST'])
def feed_demo_data():
    """Feed demo/test data into the analytics pipeline."""
    body = request.get_json()
    if not body:
        return jsonify({'success': False, 'error': 'No JSON body'}), 400

    # Support single point or array
    points = body if isinstance(body, list) else [body]
    for p in points:
        p.setdefault('timestamp', datetime.now().isoformat())
        p.setdefault('temperature', 30.0)
        p.setdefault('humidity', 55.0)
        p.setdefault('ammonia_ppm', 10.0)
        p.setdefault('fan_speed', 50)
        p.setdefault('heater_state', False)
        p.setdefault('comfort_score', 85)
        p.setdefault('target_temp', 33.0)
        _ingest_data_point(p)

    return jsonify({
        'success': True,
        'points_ingested': len(points),
        'buffer_size': len(_buffer)
    })


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'firebase': firebase_available,
        'samples_analyzed': len(_buffer),
        'version': '2.0.0'
    })


# ==================== DEMO DATA GENERATOR ====================

def _generate_demo_data():
    """Generate realistic demo data for testing without hardware."""
    import random
    hour = datetime.now().hour
    # Simulate diurnal temperature variation
    base_temp = 30.0 + 5 * (hour / 24.0)  # Cooler at night
    return {
        'temperature': round(base_temp + random.uniform(-1, 1), 1),
        'humidity': round(55 + random.uniform(-5, 5), 1),
        'ammonia_ppm': round(random.uniform(5, 30), 1),
        'fan_speed': random.randint(0, 100),
        'heater_state': random.random() < 0.3,
        'comfort_score': random.randint(60, 100),
        'distress_detected': random.random() < 0.05,
        'distress_confidence': round(random.uniform(0, 1), 2),
        'flock_day': 14,
        'target_temp': 29.5,
        'system_status': 'NORMAL',
        'timestamp': datetime.now().isoformat()
    }


# ==================== MAIN ====================

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'true').lower() == 'true'
    print(f"Starting Poultry Monitor Backend on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
