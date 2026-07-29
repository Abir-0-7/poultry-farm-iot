# ESP32 Wiring Diagram - Poultry Farm IoT Monitor

## Pin Connections

```
                    ESP32 Dev Board
┌──────────────────────────────────────────────────────────┐
│                                                           │
│  3.3V ──────────┬──────── DHT22 VCC (pin 1)              │
│  GND  ──────────┼─┬────── DHT22 GND (pin 4)              │
│                 │ └────── MQ135 GND                      │
│   GPIO4 (D4) ───┘        DHT22 DATA (pin 2)              │
│                           (with 10kΩ pull-up to 3.3V)    │
│                                                           │
│  5V  ──────────────────── MQ135 VCC                       │
│  GPIO34 (ADC1_CH6)─────── MQ135 AOUT (analog out)         │
│  GND ──────────────────── MQ135 GND                       │
│                                                           │
│  GPIO25 (D25) ─────────── EXHAUST FAN (via relay/L298N)   │
│  GPIO26 (D26) ─────────── HEATER (via relay module)       │
│  GPIO14 (D14) ─────────── RED LED (via 220Ω resistor)     │
│  GPIO12 (D12) ─────────── GREEN LED (via 220Ω resistor)   │
│  GPIO27 (D27) ─────────── BUZZER (via transistor 2N253))  │
│  GPIO32 (ADC1_CH4)─────── ELECTRET MIC (via ADC)          │
│                                                           │
└──────────────────────────────────────────────────────────┘

## Component Details

### Sensor: DHT22 Temperature/Humidity
- VCC to 3.3V
- DATA to GPIO4 with 10kΩ pull-up resistor to 3.3V
- GND to common ground
- Library: 'DHT sensor library' by Adut
```onel Pro:  -40 to 80°C, 0-100% RH, 0.5°C accuracy
```

### Sensor: MQ135 (Ammonia/NH₃)
- VCC to 5V
- A0 to ESP32 GPIO34 (ADC input)
- Requires pre-heating (24-48h on first use)
- Library: MQ135 by G. Krocker
```powershell
Heater 5V draws ~150mA
Readings stabilize after 24-48h burn-in
Calibrate in clean air first
```

### Microphone (Acoustic Distress Detection)
- MAX9814 microphone amplifier module recommended
- VCC to 3.3V
- OUT to GPIO32 (ADC input)
- GND to ground
```powershell
MAX9814 has built-in AGC for consistent levels
Samples at 8kHz for Nyquist up to 4kHz
Chick story distress: 3-5kHz frequency band
```

### Exhaust Fan Control
```
GPIO25 ──── 2N2222 NPN Transistor (base via 1kΩ resistor)
                    Collector ──── Fan Motor ──── 12V Supply
                    Emitter ─── GND
                    Flyback diode across fan motor
```
Alternative: Use 5V relay module
```
GPIO25 ──── Relay Module IN
           Relay NC ──── Fan
```

### Heat Beam Control
```
GPIO26 ──── Relay Module (5V)
           Relay COM ──── 220V Line
           Relay NO ──── Heat Bulb Load
           Connect GND + 5V from ESP
```

### Status LEDs & Buzzer
```
GPIO14 ──── 220Ω ──── RED LED Anode ──── LED Cathode ──── GND
GPIO12 ──── 220Ω ──── GREEN LED Anode ──── LED Cathode ──── GND
GPIO27 ──── 2N2222 Base (in series 1kΩ) ──── Buzzer ──── 5V ──── GND
```

## Power Budget

| Component        | Voltage | Current | Power |
|-----------------|---------|---------|-------|
| ESP32 board      | 5V      | 500mA   | 2.5W |
| DHT22            | 3.3V    | 2.5mA   | 8mW  |
| MQ235 (heater)   | 5V      | 150mA   | 0.75W |
| MAX9814 Mic      | 3.3V    | 5mA     | 16mW |
| Red LED + Green LED| 3.3V | 20mA total | 66mW|Active Buzzer    | 5V      | 30mA    | 150mW     │
| **Total ESP side** | —     | 707mA   | ~3.5W      │
| **Heating Bulb**   | 220V | 2000W | 2000W   │
| **Exhaust Fan**    | 12V  | 2A    | 24W  │

**Recommended:**
- ESP32: USB-C 5V 2A adapter
- Heater: Separate 220V circuit with relay
- Fan: 12V bench power supply (>= 3A)
- Total system: ~3.5W (ESP + sensors) + load devices

## Initial Power-UP

1. MQ235 needs 24-48h pre-heating first time
2. After burn-in, calibrate in clean outdoor air
3. ESP32 will start DHT22 readings immediately
4. Wi-Fi credentials need set in poultry_monitor.ino
5. Firebase project needs created (see deployment guide)
