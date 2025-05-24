# gui/status_widgets.py
"""
Status og information widgets for GUI
"""

import tkinter as tk
from tkinter import ttk


class StatusWidgets:
    """
    Håndterer alle status og information widgets
    """
    
    def __init__(self, parent, session_manager):
        self.session_manager = session_manager
        self._setup_status_frame(parent)
        self._initialize_status()

    def _setup_status_frame(self, parent):
        """Setup status frame og labels"""
        status_frame = ttk.LabelFrame(parent, text="Status & Score")
        status_frame.grid(row=3, column=0, padx=0, pady=0, sticky="ew")
        status_frame.grid_columnconfigure(0, weight=1)
        
        # Serial status
        self.serial_status_label = ttk.Label(
            status_frame, 
            text="Seriel Status: Initialiserer..."
        )
        self.serial_status_label.grid(row=0, column=0, sticky="w", padx=5, pady=2)
        
        # Run status
        self.run_status_label = ttk.Label(
            status_frame, 
            text="Kørsel Status: Standby"
        )
        self.run_status_label.grid(row=1, column=0, sticky="w", padx=5, pady=2)
        
        # Current run score
        self.current_run_score_label = ttk.Label(
            status_frame, 
            text="Seneste Kørsel Score: -"
        )
        self.current_run_score_label.grid(row=2, column=0, sticky="w", padx=5, pady=2)
        
        # Current run time upright
        self.current_run_time_upright_label = ttk.Label(
            status_frame, 
            text="Seneste Kørsel Tid Oprejst: - s"
        )
        self.current_run_time_upright_label.grid(row=3, column=0, sticky="w", padx=5, pady=2)
        
        # Session average score
        self.session_avg_score_label = ttk.Label(
            status_frame, 
            text="Session Gns. Score: -"
        )
        self.session_avg_score_label.grid(row=4, column=0, sticky="w", padx=5, pady=2)
        
        # Session runs count
        self.session_runs_count_label = ttk.Label(
            status_frame, 
            text="Kørsler i session: 0"
        )
        self.session_runs_count_label.grid(row=5, column=0, sticky="w", padx=5, pady=2)
        
        # Session info
        self.session_info_label = ttk.Label(
            status_frame, 
            text="Session #1"
        )
        self.session_info_label.grid(row=6, column=0, sticky="w", padx=5, pady=2)
        
        # Session PID parameters
        self.session_pid_label = ttk.Label(
            status_frame, 
            text="Session PID: KP=3.30, KI=0.00, KD=0.20"
        )
        self.session_pid_label.grid(row=7, column=0, sticky="w", padx=5, pady=2)

    def _initialize_status(self):
        """Initialiser status med session manager data"""
        self.update_session_info(self.session_manager)

    def update_serial_status(self, message):
        """Opdater serial status"""
        self.serial_status_label.config(text=f"Seriel Status: {message}")

    def update_run_status(self, message):
        """Opdater run status"""
        self.run_status_label.config(text=f"Kørsel Status: {message}")

    def update_run_results(self, score, time_upright):
        """Opdater resultater fra seneste kørsel"""
        if score is not None and time_upright is not None:
            self.current_run_score_label.config(text=f"Seneste Kørsel Score: {score:.2f}")
            self.current_run_time_upright_label.config(text=f"Seneste Kørsel Tid Oprejst: {time_upright:.2f} s")
        else:
            self.current_run_score_label.config(text="Seneste Kørsel Score: - (Ingen data)")
            self.current_run_time_upright_label.config(text="Seneste Kørsel Tid Oprejst: - s")

    def update_session_info(self, session_manager):
        """Opdater session information"""
        session_info = session_manager.get_current_session_info()
        session_stats = session_manager.get_session_stats()
        
        # Session ID
        self.session_info_label.config(text=f"Session #{session_info['session_id']}")
        
        # Session PID parameters
        pid = session_info['pid_params']
        pid_text = f"Session PID: KP={pid['kp']:.2f}, KI={pid['ki']:.2f}, KD={pid['kd']:.2f}"
        self.session_pid_label.config(text=pid_text)
        
        # Session run count
        self.session_runs_count_label.config(text=f"Kørsler i session: {session_stats['num_runs']}")
        
        # Session average score
        if session_stats['avg_score'] is not None:
            self.session_avg_score_label.config(text=f"Session Gns. Score: {session_stats['avg_score']:.2f}")
        else:
            self.session_avg_score_label.config(text="Session Gns. Score: -")

    def get_status_summary(self):
        """Få sammendrag af nuværende status"""
        return {
            'serial_status': self.serial_status_label.cget("text"),
            'run_status': self.run_status_label.cget("text"),
            'current_score': self.current_run_score_label.cget("text"),
            'session_info': self.session_info_label.cget("text")
        }

    def reset_run_results(self):
        """Nulstil kørsel resultater"""
        self.current_run_score_label.config(text="Seneste Kørsel Score: -")
        self.current_run_time_upright_label.config(text="Seneste Kørsel Tid Oprejst: - s")

    def highlight_new_session(self):
        """Fremhæv at en ny session er startet"""
        # Midlertidig fremhævning af session info
        original_bg = self.session_info_label.cget("background")
        self.session_info_label.config(background="lightgreen")
        
        # Gendan normal baggrund efter 2 sekunder
        self.session_info_label.after(2000, 
            lambda: self.session_info_label.config(background=original_bg))

    def show_warning(self, message):
        """Vis advarsel i run status"""
        original_color = self.run_status_label.cget("foreground")
        self.run_status_label.config(foreground="red")
        self.update_run_status(f"ADVARSEL: {message}")
        
        # Gendan normal farve efter 5 sekunder
        self.run_status_label.after(5000,
            lambda: self.run_status_label.config(foreground=original_color))

    def show_success(self, message):
        """Vis success besked i run status"""
        original_color = self.run_status_label.cget("foreground")
        self.run_status_label.config(foreground="green")
        self.update_run_status(f"SUCCESS: {message}")
        
        # Gendan normal farve efter 3 sekunder
        self.run_status_label.after(3000,
            lambda: self.run_status_label.config(foreground=original_color))