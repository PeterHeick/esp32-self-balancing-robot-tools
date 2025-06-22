# src/config/settings.py
"""
Konfigurationsparametre for Robot Performance System
"""

import json
import os
import datetime

# --- Serial Communication ---
SERIAL_PORT = '/dev/ttyUSB0'
BAUD_RATE = 115200

# --- CSV Data Format (Simplificeret) ---
CSV_EXPECTED_COLUMNS_NAMES = ["tid_ms", "fusedPitch", "fusedPitchRate", "balanceCmd", "pTerm", "iTerm", "dTerm", "scaledOutput", "displacement"]
NUM_EXPECTED_CSV_COLUMNS = len(CSV_EXPECTED_COLUMNS_NAMES)

# --- Robot Behavior Thresholds ---
BALANCED_PITCH_THRESHOLD_DEG = 2.5
FALLEN_PITCH_THRESHOLD_DEG = 30.0
MIN_VALID_RUN_DURATION_S = 10.0
MAX_OSCILLATION_CUTOFF_DEG = 15.0
MAX_OSCILLATION_AMPLITUDE_RMS = 3.0
SCORE_SETTLING_TIME_S = 1.0

# --- GUI Plot Settings ---
PLOT_HISTORY_SECONDS = 10

# --- Score Calculation Multipliers ---
SCORE_BASE_TIME_MULTIPLIER = 10 
SCORE_OSCILLATION_AMPLITUDE_PENALTY = 30
SCORE_OSCILLATION_FREQUENCY_PENALTY = 50
SCORE_DEGRADATION_PENALTY = 50
SCORE_POSITION_RMSE_PENALTY = 2000
OSCILLATION_WINDOW_SIZE_S = 2.0


# --- Default PID Parameters (Simplificeret) ---
DEFAULT_PID_PARAMS = {
    "kp": 18,
    "ki": 0.1,
    "kd": 0.20,
    "init_balance": 0.0,
    "power_gain": 0.0,
}

AUTO_DURATION_SEC = 15
AUTO_KP_START = 17.0
AUTO_KP_END = 19.0
AUTO_KP_STEP = 0.5
AUTO_KI_START = 0.0
AUTO_KI_END = 0.3
AUTO_KI_STEP = 0.1
AUTO_KD_START = 0.0
AUTO_KD_END = 0.3
AUTO_KD_STEP = 0.1

# --- Communication Tags (skal matche ESP32 output) ---
TAG_CSV = "TAG_CSV:"
TAG_FALLEN = "TAG_FALLEN"
TAG_INFO = "TAG_INFO:"
TAG_ERROR = "TAG_ERROR:"

# --- File Paths ---
DATA_DIR = "data"
PID_SETTINGS_FILE = "pid_settings.json"


# --- PID Persistence Functions (Simplificeret) ---
def save_pid_settings(kp, ki, kd, init_balance=0.0, power_gain=0.0, best_config=None):
    """Gemmer PID indstillinger til fil."""
    settings = {
        "kp": kp, "ki": ki, "kd": kd,
        "init_balance": init_balance, "power_gain": power_gain,
        "last_updated": datetime.datetime.now().isoformat()
    }
    if best_config:
        settings["best_config"] = best_config
    try:
        with open(PID_SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=2)
        print(f"Parametre gemt til {PID_SETTINGS_FILE}")
        return True
    except Exception as e:
        print(f"Fejl ved gemning af parametre: {e}")
        return False

def load_pid_settings():
    """Indlæser PID indstillinger fra fil."""
    if not os.path.exists(PID_SETTINGS_FILE):
        return DEFAULT_PID_PARAMS.copy(), None
    try:
        with open(PID_SETTINGS_FILE, 'r') as f:
            settings = json.load(f)
        
        # Sørg for at alle keys fra default er til stede
        pid_params = DEFAULT_PID_PARAMS.copy()
        pid_params.update({k: settings[k] for k in pid_params if k in settings})

        best_config = settings.get("best_config", None)
        print(f"Parametre indlæst fra {PID_SETTINGS_FILE}")
        return pid_params, best_config
    except Exception as e:
        print(f"Fejl ved indlæsning af parametre: {e}")
        return DEFAULT_PID_PARAMS.copy(), None