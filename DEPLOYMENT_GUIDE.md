# Poultry Farm IoT System — Complete Deployment Guide

## Prerequisites

- ESP32 development board (e.g., ESP32-WROOM-32)
- Arduino IDE 2.x installed
- Python 3.10+ installed
- Node.js 18+ (for dashboard dev server, optional)
- Git installed
- GitHub account

---

## Step 1: Firebase Project Setup

### 1.1 Create Firebase Project

1. Go to [console.firebase.google.com](https://console.firebase.google.com/)
2. Click **Add project** → Name it `poultry-monitor`
3. **Disable Google Analytics** (or enable if you want)
4. Click **Create project**

### 1.2 Enable Realtime Database

1. In Firebase Console → **Build → Realtime Database**
2. Click **Create Database**
3. Select location (e.g., `us-central1`)
4. **Start in test mode** (for development) or **locked mode** with rules below

### 1.3 Set Database Rules (Security)

In Realtime Database → **Rules** tab:

```json
{
  "rules": {
    ".read": true,
    ".write": true
  }
}
```

> 📝 For production, lock down with authentication. The demo uses open rules for simplicity.

### 1.4 Get Firebase Credentials

**For ESP32 (Web API Key):**
1. Go to **Project Settings → General**
2. Copy **Web API Key**
3. The database URL is: `https://YOUR-PROJECT-ID-default-rtdb.firebaseio.com/`

**For Python Backend (Service Account):**
1. Go to **Project Settings → Service Accounts**
2. Click **Generate new private key**
3. Save the JSON file as `backend/firebase-key.json`
4. **Do NOT commit this file to GitHub!** (It's already in `.gitignore`)

---

## Step 2: ESP32 Firmware Configuration & Flashing

### 2.1 Install Arduino Libraries

Open Arduino IDE → **Library Manager** (Ctrl+Shift+I), install:

| Library | Author | Version |
|---------|--------|---------|
| Firebase ESP Client | Mobizt | ≥2.8.0 |
| DHT sensor library | Adafruit | ≥1.4.0 |
| Arduino MQ135 | G.Krocker | ≥1.0.0 |

### 2.2 Configure Wi-Fi & Firebase

Open `esp32_firmware/poultry_monitor/poultry_monitor.ino` and update:

```cpp
#define WIFI_SSID "YOUR_WIFI_SSID"
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"

#define FIREBASE_HOST "https://YOUR-PROJECT-default-rtdb.firebaseio.com/"
#define FIREBASE_API_KEY "YOUR_FIREBASE_WEB_API_KEY"

#define FLOCK_SIZE 5000       // Your actual flock count
#define FLOCK_START_DAY 1     // Set to current flock day
```

### 2.3 Upload to ESP32

1. Connect ESP32 via USB cable
2. In Arduino IDE: Select **Tools → Board → ESP32 Dev Module**
3. Select correct **Port** (COM3 on Windows, /dev/ttyUSB0 on Linux)
4. Set **Upload Speed: 921600**
5. Set **Flash Frequency: 80MHz**
6. Click **Upload** (→ arrow)
7. Open **Serial Monitor** (115200 baud) to verify

### 2.4 Verify ESP32 Operation

You should see output:

```
==============================
Poultry Farm IoT System v2.0
Cloud + Edge-AI Mode
==============================

DHT22 sensor initialized
Acoustic detector initialized
Fuzzy logic controller initialized
Wi-Fi connected
IP address: 192.168.1.100
Firebase configured
Flock Day 1 | Target: 35.0°C ±1.0°C | Target RH: 65%

System initialization complete

Temp: 32.5°C, Hum: 58.3%, 0.00 ppm, Distress: NO
Target: 35.0°C, Fan: 25%, Heater: ON, Comfort: 95%
✓ Data pushed to Firebase
```

### 2.5 Wiring Verification

After firmware upload, verify each component:

```
✅ DHT22:   Open Serial Monitor → temperature/humidity values update every 2s
✅ MQ235:   Breathe near sensor → ammonia_ppm should rise then drop
✅ Fan:     Set heater OFF and warm room → fan should ramp up
✅ Heater:  Cool the DHT22 → heater relay should click ON
✅ MIC:     Make loud high-pitched sound → distress_detected should trigger
✅ LED:     Green blinks every 500ms; Red comes on with distress
✅ Buzzer:  Buzzer sounds when distress detected
```

---

## Step 3: GitHub Repository Setup (Do this FIRST!)

### 3.1 Create a GitHub Repository

1. Go to [github.com](https://github.com) → Click **+** (top-right) → **New repository**
2. Configure:
   - **Repository name**: `poultry-farm-iot`
   - **Description**: Poultry Farm IoT System v2.0
   - **Public/Private**: Public (required for free cloud deployments)
   - **Initialize with README**: Uncheck (you have existing code)
3. Click **Create repository**
4. Copy the URL shown (e.g., `https://github.com/YOUR-USERNAME/poultry-farm-iot.git`)

### 3.2 Push Code from VS Code to GitHub

```bash
# In VS Code Terminal (Ctrl+`)
cd F:/User/vsc/iccit

# Initialize git
git init
git branch -M main

# Create .gitignore
echo "# Python
*.pyc
__pycache__/
venv/
.env

# Arduino
*.build/

# Firebase credentials (CRITICAL!)
firebase-key.json
backend/firebase-key.json

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
" > .gitignore

# Add all files
git add .

# Verify firebase-key.json is NOT staged
git status | findstr firebase-key.json
# Should show nothing (not staged)

# Commit
git commit -m "Initial commit: Poultry Farm IoT System v2.0"

# Link and push to GitHub (use your copied URL)
git remote add origin https://github.com/YOUR-USERNAME/poultry-farm-iot.git
git push -u origin main
```

> ⚠️ Replace `YOUR-USERNAME` with your actual GitHub username.

### 3.3 Verify on GitHub

Refresh your GitHub repo page — you should see all project files there.

### 3.4 GitHub Actions CI (Optional)

Create `.github/workflows/test.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -r backend/requirements.txt
      - run: pip install pytest
      - run: cd backend && pip install -e . 2>/dev/null || true
      - run: pytest test/ -v
```

---

## Step 4: Backend Deployment

### 3.1 Local Testing First

```bash
# Clone the project
cd poultry-farm-iot/backend

# Create virtual environment
py -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Set environment variable (optional, for CI testing)
set FIREBASE_CRED_PATH=firebase-key.json  # Windows
export FIREBASE_CRED_PATH=firebase-key.json  # Linux/Mac

# Start the server
py app.py
```

You should see:
```
Firebase initialized: https://poultry-monitor-default-rtdb.firebaseio.com/
Starting Poultry Monitor Backend on port 5000
 * Running on http://0.0.0.0:5000
```

### 3.2 Test Local API

```bash
# In another terminal
curl http://localhost:5000/api/health
# → {"status":"healthy","firebase":true,"samples_analyzed":0,"version":"2.0.0"}

curl http://localhost:5000/api/live
# → Latest sensor data from Firebase

curl -X POST http://localhost:5000/api/demo \
  -H "Content-Type: application/json" \
  -d '[{"temperature":30,"humidity":55,"ammonia_ppm":10,"fan_speed":40}]'
# → Feeds test data into analytics

curl http://localhost:5000/api/alerts
# → Returns anomaly analysis

curl http://localhost:5000/api/savings
# → Returns energy savings report
```

### 3.3 Deploy to Cloud (Render / Railway / Fly.io)

**Option A: Render (easiest)**

1. Create account at [render.com](https://render.com)
2. Click **New → Web Service**
3. Connect your GitHub repository
4. Configure:
   - **Name**: `poultry-monitor-backend`
   - **Runtime**: Python 3
   - **Root Directory**: `backend`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app -b 0.0.0.0:$PORT`
   - **Environment Variables**:
     - `FIREBASE_CRED_JSON` = (paste entire firebase-key.json contents as one line)
     - `PORT` = 5000
5. Click **Deploy**
6. Your backend will be at: `https://poultry-monitor-backend.onrender.com`

> ⚠️ On free tier, Render spins down after 15min inactivity. Use a cron-job ping service (uptimerobot.com) to keep alive.

**Option B: Railway (free credits)**

1. Go to [railway.app](https://railway.app)
2. Click **New Project → Deploy from GitHub**
3. Select your repository
4. Set root directory to `backend`
5. Add environment variable `FIREBASE_CRED_JSON`
6. Deploy automatically on git push

### 3.4 Update Dashboard API URL

After deploying backend, update `dashboard/dashboard.js`:

```javascript
// Change this line
const API_BASE = 'http://localhost:5000/api';

// To your deployed URL
const API_BASE = 'https://poultry-monitor-backend.onrender.com/api';
```

---

## Step 4: Dashboard Deployment

### 4.1 Local Testing

```bash
# Open dashboard directly in browser (simple static files)
# Windows
start dashboard/index.html

# Or use Python's simple HTTP server
cd dashboard
py -m http.server 8080
# Then open http://localhost:8080
```

### 4.2 Deploy to GitHub Pages

1. In GitHub repository → **Settings → Pages**
2. Source: **Deploy from a branch**
3. Branch: `main` / folder: `/dashboard`
4. Click **Save**
5. Dashboard will be at: `https://YOUR-USERNAME.github.io/poultry-farm-iot/`

> Make sure to update `API_BASE` in dashboard.js before deploying!

### 4.3 Deploy to Vercel

1. Sign up at [vercel.com](https://vercel.com)
2. Click **Add New → Project**
3. Import your GitHub repository
4. **Framework Preset**: Other
5. **Root Directory**: `dashboard`
6. **Build Command**: (leave blank — it's static)
7. **Output Directory**: `.`
8. Click **Deploy**

---

## Step 5: GitHub Repository Setup

### 5.1 Initialize Git & Push

```bash
# In project root
cd F:/User/vsc/iccit

# Initialize git
git init
git branch -M main

# Create .gitignore first!
echo "# Python
*.pyc
__pycache__/
venv/
.env

# Arduino
*.build/

# Firebase credentials (CRITICAL!)
firebase-key.json
backend/firebase-key.json

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
" > .gitignore

# Add all files
git add .

# Verify firebase-key.json is NOT staged
git status | grep firebase-key.json
# Should show nothing (not staged)

# Commit
git commit -m "Initial commit: Poultry Farm IoT System v2.0

- ESP32 firmware with fuzzy logic, acoustic detection, dynamic profiling
- Flask backend with anomaly detection & energy optimization
- Web dashboard with Chart.js real-time visualization
- 40 passing tests covering all modules"

# Create repo on GitHub, then:
git remote add origin https://github.com/YOUR-USERNAME/poultry-farm-iot.git
git push -u origin main
```

### 5.2 GitHub Actions CI (Optional)

Create `.github/workflows/test.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -r backend/requirements.txt
      - run: pip install pytest
      - run: cd backend && pip install -e . 2>/dev/null || true
      - run: pytest test/ -v
```

---

## Step 6: Production Hardening Checklist

- [ ] Change Firebase rules from public to authenticated
- [ ] Add Firebase Authentication for dashboard access
- [ ] Use HTTPS for ESP32 (Firebase library does this automatically)
- [ ] Add watchdog timer to ESP32 firmware (auto-restart on crash)
- [ ] Set up uptime monitoring (UptimeRobot) for backend
- [ ] Calibrate MQ235 in actual farm environment
- [ ] Test heater failure detection with actual relay
- [ ] Add SMS/email alerting for critical anomalies (Twilio)
- [ ] Backup Firebase RTDB export periodically
- [ ] Consider moving to Firebase Firestore for better querying at scale

---

## Troubleshooting

### ESP32 won't connect to Wi-Fi
```
1. Double-check SSID and password (case-sensitive)
2. Verify 2.4GHz Wi-Fi (ESP32 doesn't support 5GHz)
3. Move ESP32 closer to router temporarily
4. Check Serial Monitor for error messages
```

### Firebase push fails
```
1. Verify API key and database URL match Firebase Console
2. Check database rules allow write (see Step 1.3)
3. Test with: curl -X PUT -d '{"test":1}' "https://YOUR-DB.firebaseio.com/test.json"
4. If using locked mode, enable test mode temporarily
```

### DHT22 returns NaN
```
1. Check wiring (especially pull-up resistor)
2. Verify power (3.3V, not 5V for DHT22)
3. Wait 2 seconds between readings (DHT22 max rate)
4. Try different GPIO pin
```

### Backend can't connect to Firebase
```
1. Verify firebase-key.json exists in backend/
2. Check file permissions
3. Ensure database URL ends with firebaseio.com (not firebaseio.com/)
4. Run: py -c "import firebase_admin; print('OK')" to verify installation
```
