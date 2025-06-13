# data/session_manager.py
"""
Håndtering af test sessioner og filnavngivning
"""

import os
import datetime
from config.settings import DATA_DIR
from analysis.score_calculator import ScoreCalculator


class SessionManager:
    """
    Håndterer sessioner og generering af filnavne
    """
    
    def __init__(self, initial_pid_params):
        self.session_id = 1
        self.session_start_time = datetime.datetime.now()
        self.current_pid_params = self._ensure_all_params(initial_pid_params.copy())
        self.session_score_log_filename = None
        self.detailed_run_log_filename = None
        self.session_run_details = []
        
        # Track bedste konfiguration
        self.best_config = {
            'pid_params': None,
            'avg_score': float('-inf'),
            'max_score': float('-inf'),
            'session_id': None,
            'timestamp': None,
            'stats': None
        }
        
        self._ensure_data_directory()
        self._create_session_files()

    def _ensure_all_params(self, params):
        """Sikr at alle nødvendige parametre er til stede"""
        from config.settings import DEFAULT_PID_PARAMS
        
        # Start med default værdier
        complete_params = DEFAULT_PID_PARAMS.copy()
        
        # Opdater med eksisterende værdier
        complete_params.update(params)
        
        return complete_params

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
        """Format PID parametre til filnavn - OPDATERET med position control"""
        # Balance PID
        base_str = f"KP{pid_params['kp']:.2f}_KI{pid_params['ki']:.2f}_KD{pid_params['kd']:.2f}"
        
        # Tilføj init balance og power gain hvis tilgængelig
        if 'init_balance' in pid_params:
            base_str += f"_I{pid_params['init_balance']:.2f}"
        if 'power_gain' in pid_params:
            base_str += f"_G{pid_params['power_gain']:.2f}"
            
        return base_str

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
        self.current_pid_params = self._ensure_all_params(new_pid_params.copy())
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
        
        # Check om denne session nu har den bedste performance
        self._update_best_config_if_needed()

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
    
    def _update_best_config_if_needed(self):
        """
        Opdater bedste konfiguration hvis nuværende session er bedre
        """
        if not self.session_run_details:
            return
            
        # Beregn session statistikker
        session_stats = ScoreCalculator.calculate_session_stats(self.session_run_details)
        
        if not session_stats:
            return
            
        avg_score = session_stats.get('avg_score', float('-inf'))
        max_score = session_stats.get('max_score', float('-inf'))
        
        # Check om denne session er bedre (bruger gennemsnit som primær metrik)
        if avg_score > self.best_config['avg_score']:
            self.best_config = {
                'pid_params': self.current_pid_params.copy(),
                'avg_score': avg_score,
                'max_score': max_score,
                'session_id': self.session_id,
                'timestamp': datetime.datetime.now().isoformat(),
                'stats': session_stats
            }
            
            print(f"ROBOT INFO: Ny bedste konfiguration fundet!")
            print(f"  Session #{self.session_id}: Gns. Score = {avg_score:.2f}")
            print(f"  PID: KP={self.current_pid_params['kp']}, KI={self.current_pid_params['ki']}, KD={self.current_pid_params['kd']}")
            print(f"  Power Gain: {self.current_pid_params.get('power_gain', 0.0)}")
    
    def get_best_config(self):
        """
        Få den bedste konfiguration fundet indtil videre
        
        Returns:
            dict: Bedste konfiguration eller None hvis ingen data
        """
        if self.best_config['pid_params'] is None:
            return None
        return self.best_config.copy()
    
    def set_best_config(self, best_config_data):
        """
        Sæt bedste konfiguration (bruges ved indlæsning fra fil)
        
        Args:
            best_config_data: Dict med bedste konfiguration data
        """
        if best_config_data:
            self.best_config = best_config_data.copy()
            print(f"ROBOT INFO: Bedste konfiguration indlæst fra fil")
            if self.best_config.get('pid_params'):
                pid = self.best_config['pid_params']
                print(f"  Score: {self.best_config.get('avg_score', 'N/A'):.2f}")
                print(f"  PID: KP={pid.get('kp')}, KI={pid.get('ki')}, KD={pid.get('kd')}")