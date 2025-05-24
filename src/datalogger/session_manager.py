# data/session_manager.py
"""
Håndtering af test sessioner og filnavngivning
"""

import os
import datetime
from config.settings import DATA_DIR


class SessionManager:
    """
    Håndterer sessioner og generering af filnavne
    """
    
    def __init__(self, initial_pid_params):
        self.session_id = 1
        self.session_start_time = datetime.datetime.now()
        self.current_pid_params = initial_pid_params.copy()
        self.session_score_log_filename = None
        self.detailed_run_log_filename = None
        self.session_run_details = []
        
        self._ensure_data_directory()
        self._create_session_files()

    def _ensure_data_directory(self):
        """Sikr at data mappen eksisterer"""
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)

    def _create_session_files(self):
        """Opret filnavne for den aktuelle session"""
        pid_str = self._format_pid_string(self.current_pid_params)
        
        session_base = f"session_{self.session_id:03d}_{pid_str}"
        score_base = f"score_{self.session_id:03d}_{pid_str}"
        
        self.session_score_log_filename = f"{DATA_DIR}/{score_base}.csv"
        self.detailed_run_log_filename = f"{DATA_DIR}/{session_base}_detailed.csv"
        
        print(f"ROBOT INFO: Ny session #{self.session_id} oprettet")
        print(f"  Score log: {self.session_score_log_filename}")
        print(f"  Detailed log: {self.detailed_run_log_filename}")

    def _format_pid_string(self, pid_params):
        """Format PID parametre til filnavn"""
        return f"KP{pid_params['kp']:.2f}_KI{pid_params['ki']:.2f}_KD{pid_params['kd']:.2f}"

    def start_new_session(self, new_pid_params):
        """
        Start en ny session med nye PID parametre
        
        Args:
            new_pid_params: Dict med nye PID parametre
            
        Returns:
            tuple: (old_session_data, old_session_id) for logging
        """
        # Gem data fra tidligere session
        old_session_data = self.session_run_details.copy()
        old_session_id = self.session_id
        old_pid_params = self.current_pid_params.copy()
        
        # Opdater til ny session
        self.session_id += 1
        self.session_start_time = datetime.datetime.now()
        self.current_pid_params = new_pid_params.copy()
        self.session_run_details = []
        
        # Opret nye filnavne
        self._create_session_files()
        
        return old_session_data, old_session_id, old_pid_params

    def add_run_result(self, run_result):
        """
        Tilføj resultat fra en testkørsel til sessionen
        
        Args:
            run_result: Tuple med (score, time_upright, total_duration, 
                                  avg_abs_pitch_dev, stability_metric)
        """
        self.session_run_details.append(run_result)

    def get_session_stats(self):
        """
        Få statistikker for nuværende session
        
        Returns:
            dict: Session statistikker
        """
        if not self.session_run_details:
            return {
                'num_runs': 0,
                'avg_score': None
            }
        
        scores = [details[0] for details in self.session_run_details]
        return {
            'num_runs': len(self.session_run_details),
            'avg_score': sum(scores) / len(scores) if scores else None
        }

    def get_current_session_info(self):
        """Få info om nuværende session"""
        return {
            'session_id': self.session_id,
            'pid_params': self.current_pid_params.copy(),
            'start_time': self.session_start_time,
            'num_runs': len(self.session_run_details)
        }

    def get_detailed_log_filename(self):
        """Få filnavn for detaljeret log"""
        return self.detailed_run_log_filename

    def get_score_log_filename(self):
        """Få filnavn for score log"""
        return self.session_score_log_filename

    def has_run_data(self):
        """Check om sessionen har kørsel data"""
        return len(self.session_run_details) > 0