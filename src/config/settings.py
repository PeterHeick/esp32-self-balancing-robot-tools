# config/settings.py
"""
Konfigurationsparametre for Robot Performance System
"""

import json
import os
import datetime

# --- Serial Communication ---
SERIAL_PORT = '/dev/ttyUSB0'
BAUD_RATE = 115200

# --- CSV Data Format ---
CSV_EXPECTED_COLUMNS_NAMES = ["tid_ms", "fusedPitch", "fusedPitchRate", "balanceCmd", "pTerm", "iTerm", "dTerm", "scaledOutput"]
NUM_EXPECTED_CSV_COLUMNS = len(CSV_EXPECTED_COLUMNS_NAMES)

# --- Robot Behavior Thresholds ---
BALANCED_PITCH_THRESHOLD_DEG = 2.5
FALLEN_PITCH_THRESHOLD_DEG = 30.0
MIN_VALID_RUN_DURATION_S = 10.0  # Øget til 10 sekunder minimum
MAX_OSCILLATION_CUTOFF_DEG = 15.0  # Stop scoring ved store oscillationer
MAX_OSCILLATION_AMPLITUDE_RMS = 3.0  # Maksimal tilladt RMS amplitude

# --- Timing Parameters ---
TARGET_LOOP_TIME_MS = 15.0
LOOP_TIME_WARNING_THRESHOLD_MS = TARGET_LOOP_TIME_MS + 1.0

# --- GUI Plot Settings ---
PLOT_HISTORY_SECONDS = 10

# --- Score Calculation Multipliers ---
SCORE_BASE_TIME_MULTIPLIER = 10  # Base score for valid time
SCORE_OSCILLATION_AMPLITUDE_PENALTY = 30  # Straf for oscillation amplitude
SCORE_OSCILLATION_FREQUENCY_PENALTY = 50  # Straf for høj frekvens
SCORE_DEGRADATION_PENALTY = 50  # Straf for forværring over tid
OSCILLATION_WINDOW_SIZE_S = 2.0  # Størrelse af analyse-vinduer

# --- Default PID Parameters ---
DEFAULT_PID_PARAMS = {
    "kp": 3.3,
    "ki": 0.0,
    "kd": 0.20,
    "init_balance": 0.0,    # Initial balance offset (grader)
    "power_gain": 0.0,      # Power gain multiplier
}

# --- Communication Tags (skal matche ESP32 output) ---
TAG_CSV = "TAG_CSV:"
TAG_FALLEN = "TAG_FALLEN"
TAG_INFO = "TAG_INFO:"
TAG_ERROR = "TAG_ERROR:"

# --- File Paths ---
DATA_DIR = "data"
PID_SETTINGS_FILE = "pid_settings.json"


# --- PID Persistence Functions ---
def save_pid_settings(kp, ki, kd, init_balance=0.0, power_gain=0.0, best_config=None):
    """Gem alle PID indstillinger til fil - OPDATERET med position control"""
    settings = {
        "kp": kp,
        "ki": ki,
        "kd": kd,
        "init_balance": init_balance,
        "power_gain": power_gain,
        "last_updated": datetime.datetime.now().isoformat()
    }
    
    # Tilføj bedste konfiguration hvis tilgængelig
    if best_config:
        settings["best_config"] = best_config
    
    try:
        with open(PID_SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=2)
        print(f"Alle parametre gemt til {PID_SETTINGS_FILE}")
        if best_config:
            print(f"Bedste konfiguration også gemt (Score: {best_config.get('avg_score', 'N/A'):.2f})")
        return True
    except Exception as e:
        print(f"Fejl ved gemning af parametre: {e}")
        return False


def load_pid_settings():
    """Indlæs alle PID indstillinger fra fil - OPDATERET med position control"""
    if not os.path.exists(PID_SETTINGS_FILE):
        print(f"Ingen gemt parameter fil: {PID_SETTINGS_FILE} - bruger default værdier")
        return DEFAULT_PID_PARAMS.copy(), None
    
    try:
        with open(PID_SETTINGS_FILE, 'r') as f:
            settings = json.load(f)
        
        pid_params = {
            "kp": settings.get("kp", DEFAULT_PID_PARAMS["kp"]),
            "ki": settings.get("ki", DEFAULT_PID_PARAMS["ki"]),
            "kd": settings.get("kd", DEFAULT_PID_PARAMS["kd"]),
            "init_balance": settings.get("init_balance", DEFAULT_PID_PARAMS["init_balance"]),
            "power_gain": settings.get("power_gain", DEFAULT_PID_PARAMS["power_gain"]),
        }
        
        best_config = settings.get("best_config", None)
        
        print(f"Parametre indlæst fra {PID_SETTINGS_FILE}")
        print(f"  Balance: KP={pid_params['kp']}, KI={pid_params['ki']}, KD={pid_params['kd']}")
        print(f"  Config: Init={pid_params['init_balance']}, Power={pid_params['power_gain']}")
        
        if best_config:
            print(f"  Bedste config fundet: Score = {best_config.get('avg_score', 'N/A'):.2f}")
        
        return pid_params, best_config
        
    except Exception as e:
        print(f"Fejl ved indlæsning af parametre: {e}")
        return DEFAULT_PID_PARAMS.copy(), None


# --- Debug Settings ---
DEBUG_MODE = False
VERBOSE_LOGGING = False

def enable_debug_mode():
    """Aktiver debug mode"""
    global DEBUG_MODE, VERBOSE_LOGGING
    DEBUG_MODE = True
    VERBOSE_LOGGING = True
    print("DEBUG MODE AKTIVERET")

def debug_print(message):
    """Print debug besked hvis debug mode er aktiv"""
    if DEBUG_MODE:
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[DEBUG {timestamp}] {message}")