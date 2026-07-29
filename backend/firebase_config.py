"""
Firebase configuration and initialization for Poultry Monitor backend.
"""
import os
import json
from pathlib import Path

try:
    import firebase_admin
    from firebase_admin import credentials, db
except ImportError:
    firebase_admin = None
    db = None


_firebase_app = None
_db_ref = None


def init_firebase(cred_path=None, database_url=None):
    """Initialize Firebase Admin SDK with service account credentials."""
    global _firebase_app, _db_ref

    if firebase_admin is None:
        raise RuntimeError("firebase-admin package not installed")

    if _firebase_app is not None:
        return _db_ref

    cred_path = cred_path or os.getenv("FIREBASE_CRED_PATH", "firebase-key.json")
    database_url = database_url or os.getenv(
        "FIREBASE_DATABASE_URL",
        "https://poultry-monitor-9294e-default-rtdb.firebaseio.com/"
    )

    if not os.path.exists(cred_path):
     
        cred_json = os.getenv("FIREBASE_CRED_JSON", None)
        if cred_json:
            cred_dict = json.loads(cred_json)
            cred = credentials.Certificate(cred_dict)
        else:
            raise FileNotFoundError(f"Firebase credentials not found at {cred_path}")
    else:
        cred = credentials.Certificate(cred_path)

    _firebase_app = firebase_admin.initialize_app(cred, {
        'databaseURL': database_url
    })
    _db_ref = db.reference('/')
    print(f"Firebase initialized: {database_url}")
    return _db_ref


def get_db():
    """Get the Firebase database reference."""
    global _db_ref
    return _db_ref


def fetch_live_data():
    """Fetch the most recent live sensor data."""
    ref = get_db()
    if ref is None:
        return None
    return ref.child('live_data').get()


def fetch_history(limit=100):
    """Fetch historical sensor data entries."""
    ref = get_db()
    if ref is None:
        return []
    history = ref.child('history').get()
    if history is None:
        return []
    entries = []
    for key, val in history.items():
        if val is not None:
            val['_key'] = key
            entries.append(val)

    entries.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    return entries[:limit]


def fetch_config():
    """Fetch current configuration from Firebase."""
    ref = get_db()
    if ref is None:
        return {}
    return ref.child('config').get() or {}


def set_config(key, value):
    """Update a configuration value in Firebase."""
    ref = get_db()
    if ref is not None:
        ref.child(f'config/{key}').set(value)
