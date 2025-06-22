# src/gui/status_widgets.py
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
        # Denne metode opretter nu self.status_frame, men placerer den ikke
        self._setup_status_frame(parent)
        self._initialize_status()

    def _setup_status_frame(self, parent):
        """Setup status frame og labels"""
        # RETTELSE: Gem framen som en instansvariabel (self.status_frame)
        self.status_frame = ttk.LabelFrame(parent, text="Status & Score")
        
        # FJERNELSE: Widget'et skal ikke længere placere sig selv.
        # Main_window vil nu håndtere .grid() for denne frame.
        
        self.status_frame.grid_columnconfigure(0, weight=1)
        
        # Alle labels placeres nu i self.status_frame
        self.serial_status_label = ttk.Label(
            self.status_frame, 
            text="Seriel Status: Initialiserer..."
        )
        self.serial_status_label.grid(row=0, column=0, sticky="w", padx=5, pady=2)
        
        self.run_status_label = ttk.Label(
            self.status_frame, 
            text="Kørsel Status: Standby"
        )
        self.run_status_label.grid(row=1, column=0, sticky="w", padx=5, pady=2)
        
        self.current_run_score_label = ttk.Label(
            self.status_frame, 
            text="Seneste Kørsel Score: -"
        )
        self.current_run_score_label.grid(row=2, column=0, sticky="w", padx=5, pady=2)
        
        self.current_run_time_upright_label = ttk.Label(
            self.status_frame, 
            text="Seneste Kørsel Tid Oprejst: - s"
        )
        self.current_run_time_upright_label.grid(row=3, column=0, sticky="w", padx=5, pady=2)
        
        self.session_avg_score_label = ttk.Label(
            self.status_frame, 
            text="Session Gns. Score: -"
        )
        self.session_avg_score_label.grid(row=4, column=0, sticky="w", padx=5, pady=2)
        
        self.session_runs_count_label = ttk.Label(
            self.status_frame, 
            text="Kørsler i session: 0"
        )
        self.session_runs_count_label.grid(row=5, column=0, sticky="w", padx=5, pady=2)
        
        self.session_info_label = ttk.Label(
            self.status_frame, 
            text="Session #1"
        )
        self.session_info_label.grid(row=6, column=0, sticky="w", padx=5, pady=2)
        
        self.session_pid_label = ttk.Label(
            self.status_frame, 
            text="Session PID: KP=3.30, KI=0.00, KD=0.20"
        )
        self.session_pid_label.grid(row=7, column=0, sticky="w", padx=5, pady=2)
        
        self.best_config_label = ttk.Label(
            self.status_frame, 
            text="Bedste Config: Ingen data"
        )
        self.best_config_label.grid(row=8, column=0, sticky="w", padx=5, pady=2)
        
        self.best_config_details_label = ttk.Label(
            self.status_frame, 
            text=""
        )
        self.best_config_details_label.grid(row=9, column=0, sticky="w", padx=5, pady=2)

    # ... resten af metoderne i StatusWidgets er uændrede ...
    def _initialize_status(self):
        self.update_session_info(self.session_manager)
    def update_serial_status(self, message):
        self.serial_status_label.config(text=f"Seriel Status: {message}")
    def update_run_status(self, message):
        self.run_status_label.config(text=f"Kørsel Status: {message}")
    def update_run_results(self, score, time_upright):
        if score is not None and time_upright is not None:
            self.current_run_score_label.config(text=f"Seneste Kørsel Score: {score:.2f}")
            self.current_run_time_upright_label.config(text=f"Seneste Kørsel Tid Oprejst: {time_upright:.2f} s")
        else:
            self.current_run_score_label.config(text="Seneste Kørsel Score: - (Ingen data)")
            self.current_run_time_upright_label.config(text="Seneste Kørsel Tid Oprejst: - s")
    def update_session_info(self, session_manager):
        session_info = session_manager.get_current_session_info()
        session_stats = session_manager.get_session_stats()
        self.session_info_label.config(text=f"Session #{session_info['session_id']}")
        pid = session_info['pid_params']
        pid_text = f"Session PID: KP={pid.get('kp', 0):.2f}, KI={pid.get('ki', 0):.2f}, KD={pid.get('kd', 0):.2f}"
        self.session_pid_label.config(text=pid_text)
        self.session_runs_count_label.config(text=f"Kørsler i session: {session_stats['num_runs']}")
        if session_stats['avg_score'] is not None:
            self.session_avg_score_label.config(text=f"Session Gns. Score: {session_stats['avg_score']:.2f}")
        else:
            self.session_avg_score_label.config(text="Session Gns. Score: -")
        self._update_best_config_display(session_manager)
    def get_status_summary(self):
        return { 'serial_status': self.serial_status_label.cget("text"), 'run_status': self.run_status_label.cget("text"), 'current_score': self.current_run_score_label.cget("text"), 'session_info': self.session_info_label.cget("text"), 'best_config': self.best_config_label.cget("text") }
    def reset_run_results(self):
        self.current_run_score_label.config(text="Seneste Kørsel Score: -")
        self.current_run_time_upright_label.config(text="Seneste Kørsel Tid Oprejst: - s")
    def highlight_new_session(self):
        original_bg = self.session_info_label.cget("background")
        self.session_info_label.config(background="lightgreen")
        self.session_info_label.after(2000, lambda: self.session_info_label.config(background=original_bg))
    def show_warning(self, message):
        original_color = self.run_status_label.cget("foreground")
        self.run_status_label.config(foreground="red")
        self.update_run_status(f"ADVARSEL: {message}")
        self.run_status_label.after(5000, lambda: self.run_status_label.config(foreground=original_color))
    def show_success(self, message):
        original_color = self.run_status_label.cget("foreground")
        self.run_status_label.config(foreground="green")
        self.update_run_status(f"SUCCESS: {message}")
        self.run_status_label.after(3000, lambda: self.run_status_label.config(foreground=original_color))
    def _update_best_config_display(self, session_manager):
        best_config = session_manager.get_best_config()
        if best_config is None:
            self.best_config_label.config(text="Bedste Config: Ingen data")
            self.best_config_details_label.config(text="")
            return
        avg_score = best_config.get('avg_score', 0)
        session_id = best_config.get('session_id', '?')
        self.best_config_label.config(text=f"Bedste Config: Score {avg_score:.2f} (Session #{session_id})")
        pid_params = best_config.get('pid_params', {})
        if pid_params:
            kp = pid_params.get('kp', 0)
            ki = pid_params.get('ki', 0)
            kd = pid_params.get('kd', 0)
            power_gain = pid_params.get('power_gain', 0)
            details_text = f"  KP={kp:.2f}, KI={ki:.2f}, KD={kd:.2f}, PowerGain={power_gain:.2f}"
            self.best_config_details_label.config(text=details_text)
        else:
            self.best_config_details_label.config(text="")
    def highlight_new_best_config(self):
        original_bg = self.best_config_label.cget("background")
        self.best_config_label.config(background="lightblue")
        self.best_config_label.after(3000, lambda: self.best_config_label.config(background=original_bg))