# gui/main_window.py
"""
Hovedvindue for Robot Performance & Tuning App
"""

import tkinter as tk
from tkinter import ttk, messagebox
import numpy as np
from collections import deque
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import datetime
import time
import subprocess
import os
import glob

# Vores egne moduler
from config.settings import *
from communication.serial_handler import SerialThread
from datalogger.session_manager import SessionManager
from datalogger.data_logger import DataLogger
from analysis.score_calculator import ScoreCalculator
from gui.status_widgets import StatusWidgets
from tuning.auto_tuner import AutoTuner


class RobotPerformanceApp:
    """
    Hovedapplikation for Robot Performance System
    """
    
    def __init__(self, root_window):
        self.root = root_window
        self.root.title("Robot Performance & Tuning v1.5 (Komplet)")
        
        # Core components
        saved_pid_params, saved_best_config = load_pid_settings()
        self.session_manager = SessionManager(saved_pid_params)
        
        if saved_best_config:
            self.session_manager.set_best_config(saved_best_config)
        self.data_logger = DataLogger()
        self.score_calculator = ScoreCalculator()
        
        # Runtime state
        self.current_run_data = []
        self.is_running_test = False
        self.run_start_time_esp_ms = 0
        self.first_data_line_in_run_received = False
        
        # State for Auto-Tuner
        self.is_auto_tuning = False
        self.autotuner = None
        self.countdown_timer_id = None
        self.autostop_timer_id = None
        
        # Plot data
        self.plot_time_data = deque()
        self.plot_pitch_data = deque()
        
        # Setup
        self._setup_gui()
        self.serial_thread = SerialThread(
            SERIAL_PORT, BAUD_RATE, 
            self._dispatch_serial_data_to_gui, 
            self._update_serial_status_gui
        )
        self.serial_thread.start()
        self.root.after(100, self._periodic_gui_update)
        self.root.after(2000, self._try_load_pid_from_robot)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    # ===================================================================
    #   GUI SETUP METODER
    # ===================================================================

    def _setup_gui(self):
        main_frame = ttk.Frame(self.root, padding="10"); main_frame.grid(row=0, column=0, sticky="nsew")
        self.root.grid_columnconfigure(0, weight=1); self.root.grid_rowconfigure(0, weight=1)
        left_panel = ttk.Frame(main_frame); left_panel.grid(row=0, column=0, padx=(0,10), pady=0, sticky="ns")
        right_panel = ttk.Frame(main_frame); right_panel.grid(row=0, column=1, pady=0, sticky="nsew")
        main_frame.grid_columnconfigure(1, weight=1); main_frame.grid_rowconfigure(0, weight=1)
        
        self._setup_pid_controls(left_panel)
        self._setup_manual_controls(left_panel)
        self._setup_test_controls(left_panel)
        self._setup_autotune_controls(left_panel)
        
        self.status_widgets = StatusWidgets(left_panel, self.session_manager)
        self.status_widgets.status_frame.grid(row=4, column=0, padx=0, pady=0, sticky="ew")

        self._setup_plot(right_panel)

    def _setup_pid_controls(self, parent):
        param_frame = ttk.LabelFrame(parent, text="Robot Parametre")
        param_frame.grid(row=0, column=0, padx=0, pady=(0,10), sticky="ew")
        
        saved_pid_params, _ = load_pid_settings()
        
        ttk.Label(param_frame, text="KP:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.kp_var = tk.DoubleVar(value=saved_pid_params.get("kp", 3.3))
        ttk.Entry(param_frame, textvariable=self.kp_var, width=10).grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(param_frame, text="KI:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.ki_var = tk.DoubleVar(value=saved_pid_params.get("ki", 0.0))
        ttk.Entry(param_frame, textvariable=self.ki_var, width=10).grid(row=1, column=1, padx=5, pady=5)
        
        ttk.Label(param_frame, text="KD:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.kd_var = tk.DoubleVar(value=saved_pid_params.get("kd", 0.2))
        ttk.Entry(param_frame, textvariable=self.kd_var, width=10).grid(row=2, column=1, padx=5, pady=5)
        
        ttk.Separator(param_frame, orient='horizontal').grid(row=3, column=0, columnspan=2, sticky="ew", padx=5, pady=10)
        
        ttk.Label(param_frame, text="Init Balance:").grid(row=4, column=0, padx=5, pady=5, sticky="w")
        self.init_balance_var = tk.DoubleVar(value=saved_pid_params.get("init_balance", 0.0))
        ttk.Entry(param_frame, textvariable=self.init_balance_var, width=10).grid(row=4, column=1, padx=5, pady=5)
        
        ttk.Label(param_frame, text="Power Gain:").grid(row=5, column=0, padx=5, pady=5, sticky="w")
        self.power_gain_var = tk.DoubleVar(value=saved_pid_params.get("power_gain", 0.0))
        ttk.Entry(param_frame, textvariable=self.power_gain_var, width=10).grid(row=5, column=1, padx=5, pady=5)

        self.apply_pid_params_button = ttk.Button(param_frame, text="Anvend Alle Parametre", command=self._apply_pid_parameters)
        self.apply_pid_params_button.grid(row=6, column=0, columnspan=2, pady=(10,5))

    def _setup_manual_controls(self, parent):
        manual_cmd_frame = ttk.LabelFrame(parent, text="Manuel Kommando & Lagring")
        manual_cmd_frame.grid(row=1, column=0, padx=0, pady=(0,10), sticky="ew")
        
        self.manual_cmd_var = tk.StringVar()
        manual_entry = ttk.Entry(manual_cmd_frame, textvariable=self.manual_cmd_var, width=25)
        manual_entry.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        manual_cmd_frame.grid_columnconfigure(0, weight=1)
        
        self.send_manual_cmd_button = ttk.Button(manual_cmd_frame, text="Send Manuel", command=self._send_manual_command)
        self.send_manual_cmd_button.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        self.save_to_robot_button = ttk.Button(manual_cmd_frame, text="Gem på Robot (NVS)", command=self._save_parameters_on_robot)
        self.save_to_robot_button.grid(row=1, column=0, columnspan=2, padx=5, pady=(5,5), sticky="ew")
        
    def _setup_test_controls(self, parent):
        control_frame = ttk.LabelFrame(parent, text="Manuel Test Kontrol")
        control_frame.grid(row=2, column=0, padx=0, pady=(0,10), sticky="ew")
        
        self.start_stop_button = ttk.Button(control_frame, text="Start Testkørsel", command=self._toggle_test_run)
        self.start_stop_button.pack(pady=5, padx=5, fill="x")
        
        self.print_session_button = ttk.Button(control_frame, text="Print Session Resultat", command=self._print_current_session)
        self.print_session_button.pack(pady=5, padx=5, fill="x")
        
        self.open_grafplot_button = ttk.Button(control_frame, text="Åbn Grafplot (Seneste Session)", command=self._open_grafplot_latest_session)
        self.open_grafplot_button.pack(pady=5, padx=5, fill="x")

    def _setup_autotune_controls(self, parent):
        """Setup a control panel for the automatic tuning process."""
        autotune_frame = ttk.LabelFrame(parent, text="Automatisk Tuning")
        autotune_frame.grid(row=3, column=0, padx=0, pady=(0, 10), sticky="ew")

        # Række 1: KP
        ttk.Label(autotune_frame, text="KP Start:").grid(row=0, column=0, sticky="w", padx=5, pady=2); self.kp_start_var = tk.DoubleVar(value=AUTO_KP_START); ttk.Entry(autotune_frame, textvariable=self.kp_start_var, width=8).grid(row=0, column=1)
        ttk.Label(autotune_frame, text="KP Slut:").grid(row=0, column=2, sticky="w", padx=5, pady=2); self.kp_end_var = tk.DoubleVar(value=AUTO_KP_END); ttk.Entry(autotune_frame, textvariable=self.kp_end_var, width=8).grid(row=0, column=3)
        ttk.Label(autotune_frame, text="KP Skridt:").grid(row=0, column=4, sticky="w", padx=5, pady=2); self.kp_step_var = tk.DoubleVar(value=AUTO_KP_STEP); ttk.Entry(autotune_frame, textvariable=self.kp_step_var, width=8).grid(row=0, column=5)

        # Række 2: KD
        ttk.Label(autotune_frame, text="KD Start:").grid(row=1, column=0, sticky="w", padx=5, pady=2); self.kd_start_var = tk.DoubleVar(value=AUTO_KD_START); ttk.Entry(autotune_frame, textvariable=self.kd_start_var, width=8).grid(row=1, column=1)
        ttk.Label(autotune_frame, text="KD Slut:").grid(row=1, column=2, sticky="w", padx=5, pady=2); self.kd_end_var = tk.DoubleVar(value=AUTO_KD_END); ttk.Entry(autotune_frame, textvariable=self.kd_end_var, width=8).grid(row=1, column=3)
        ttk.Label(autotune_frame, text="KD Skridt:").grid(row=1, column=4, sticky="w", padx=5, pady=2); self.kd_step_var = tk.DoubleVar(value=AUTO_KD_STEP); ttk.Entry(autotune_frame, textvariable=self.kd_step_var, width=8).grid(row=1, column=5)
        
        # Række 3: KI (NYT)
        ttk.Label(autotune_frame, text="KI Start:").grid(row=2, column=0, sticky="w", padx=5, pady=2); self.ki_start_var = tk.DoubleVar(value=AUTO_KI_START); ttk.Entry(autotune_frame, textvariable=self.ki_start_var, width=8).grid(row=2, column=1)
        ttk.Label(autotune_frame, text="KI Slut:").grid(row=2, column=2, sticky="w", padx=5, pady=2); self.ki_end_var = tk.DoubleVar(value=AUTO_KI_END); ttk.Entry(autotune_frame, textvariable=self.ki_end_var, width=8).grid(row=2, column=3)
        ttk.Label(autotune_frame, text="KI Skridt:").grid(row=2, column=4, sticky="w", padx=5, pady=2); self.ki_step_var = tk.DoubleVar(value=AUTO_KI_STEP); ttk.Entry(autotune_frame, textvariable=self.ki_step_var, width=8).grid(row=2, column=5)

        # Række 4: Varighed og Knap
        ttk.Label(autotune_frame, text="Varighed (s):").grid(row=3, column=0, sticky="w", padx=5, pady=2); self.duration_var = tk.IntVar(value=AUTO_DURATION_SEC); ttk.Entry(autotune_frame, textvariable=self.duration_var, width=8).grid(row=3, column=1)
        
        self.start_autotune_button = ttk.Button(autotune_frame, text="Start Automatisk Tuning", command=self.toggle_auto_tuning)
        self.start_autotune_button.grid(row=4, column=0, columnspan=6, pady=5, padx=5, sticky="ew")

        self.autotune_status_label = ttk.Label(autotune_frame, text="Status: Standby")
        self.autotune_status_label.grid(row=5, column=0, columnspan=6, pady=2, padx=5, sticky="w")

    def _setup_plot(self, parent):
        self.fig = Figure(figsize=(8, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_ylim(-FALLEN_PITCH_THRESHOLD_DEG - 5, FALLEN_PITCH_THRESHOLD_DEG + 5)
        self.ax.set_xlabel("Tid relativt til start af kørsel (s)")
        self.ax.set_ylabel("Pitch (grader)")
        self.ax.grid(True)
        self.line, = self.ax.plot([], [], lw=1.5, color='dodgerblue')
        self.canvas = FigureCanvasTkAgg(self.fig, master=parent)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill=tk.BOTH, expand=True)
        self.canvas.draw()
    
    # ===================================================================
    #   AUTO-TUNING LOGIK
    # ===================================================================

    def toggle_auto_tuning(self):
        """Starter eller stopper den automatiske tuning proces."""
        if self.is_auto_tuning:
            self.is_auto_tuning = False
            if self.is_running_test: self._stop_current_run("Auto-tuning afbrudt")
            self.start_autotune_button.config(text="Start Automatisk Tuning")
            self.autotune_status_label.config(text="Status: Afbrudt af bruger")
            print("--- AUTOMATISK TUNING AFBRUDT ---")
        else:
            tune_params = {
                'kp_start': self.kp_start_var.get(), 'kp_end': self.kp_end_var.get(), 'kp_step': self.kp_step_var.get(),
                'kd_start': self.kd_start_var.get(), 'kd_end': self.kd_end_var.get(), 'kd_step': self.kd_step_var.get(),
                'ki_start': self.ki_start_var.get(), 'ki_end': self.ki_end_var.get(), 'ki_step': self.ki_step_var.get()
            }
            try:
                self.autotuner = AutoTuner(tune_params)
                if self.autotuner.total_jobs == 0:
                    messagebox.showwarning("Auto-Tune", "Ingen test-jobs at køre. Tjek start/slut/skridt værdier.")
                    return
            except ValueError:
                messagebox.showerror("Fejl", "Ugyldige værdier for auto-tuning (f.eks. start > slut eller skridt <= 0).")
                return

            self.is_auto_tuning = True
            self.start_autotune_button.config(text="Stop Automatisk Tuning")
            print("--- STARTER AUTOMATISK TUNING ---")
            self._autotune_tick()

    def _autotune_tick(self):
        """Hoved 'state machine' for auto-tuneren med robust verifikation."""
        if not self.is_auto_tuning or self.is_running_test:
            return

        next_pid_params = self.autotuner.get_next_job()

        if next_pid_params is None:
            self.toggle_auto_tuning()
            self.autotune_status_label.config(text="Status: Færdig!")
            print("--- AUTOMATISK TUNING FÆRDIG ---")
            messagebox.showinfo("Auto-Tune Færdig", f"Gennemført {self.autotuner.total_jobs} tests.")
            return
        
        progress = self.autotuner.get_progress()
        status_msg = f"Tester {progress}: KP={next_pid_params['kp']:.2f}, KD={next_pid_params['kd']:.2f}, KI={next_pid_params['ki']:.2f}"
        self.autotune_status_label.config(text=f"Status: {status_msg}")
        print(status_msg)

        self.kp_var.set(next_pid_params['kp'])
        self.ki_var.set(next_pid_params['ki'])
        self.kd_var.set(next_pid_params['kd'])
        
        def on_params_verified(success, message):
            """Denne funktion kaldes, NÅR verifikationen er færdig."""
            if not self.is_auto_tuning: return

            if not success:
                print(f"FEJL: Kunne ikke verificere parametre for {next_pid_params}. Skipper test. Fejl: {message}")
                self.log_autotune_result(next_pid_params, -1000) # Log en fejl-score
                self.root.after(500, self._autotune_tick) # Prøv næste job efter en kort pause
                return
            
            # Hvis vi når hertil, er parametrene verificeret!
            print("SUCCESS: Parametre verificeret. Starter test...")
            self._start_automated_test_run()

        # Start kæden: Bed om at anvende parametre og giv 'on_params_verified' som "opskrift" på, hvad der skal ske bagefter.
        self._apply_pid_parameters_with_callback(on_params_verified)

    def _start_automated_test_run(self):
        """Hjælpefunktion til at starte en automatiseret test."""
        if not self.is_auto_tuning: return 

        duration_s = self.duration_var.get()
        title_text = (f"Auto-Tune: Tester "
                      f"KP={self.kp_var.get():.2f}, "
                      f"KD={self.kd_var.get():.2f}, "
                      f"KI={self.ki_var.get():.2f}")
        self.ax.set_title(title_text, color='darkred')
        self.canvas.draw_idle()
        self._update_countdown_timer(duration_s)

        self._start_test_run()
        
        duration_ms = duration_s * 1000
        self.autostop_timer_id = self.root.after(duration_ms, lambda: self._stop_current_run("Auto-test færdig"))
        
    def _update_countdown_timer(self, seconds_left):
        """Opdaterer nedtællings-labelen hvert sekund."""
        if seconds_left > 0 and self.is_running_test:
            self.status_widgets.update_run_status(f"Auto-Test kører: {seconds_left} sekunder tilbage...")
            self.countdown_timer_id = self.root.after(1000, lambda: self._update_countdown_timer(seconds_left - 1))
        else:
            self.countdown_timer_id = None
            
    def log_autotune_result(self, pid_params, score):
        """Logger resultatet af en enkelt auto-tune kørsel til en CSV fil."""
        filename = "autotune_results.csv"
        os.makedirs(os.path.dirname(os.path.abspath(filename)) if os.path.dirname(os.path.abspath(filename)) else '.', exist_ok=True)
        file_exists = os.path.exists(filename)
        try:
            with open(filename, 'a', newline='') as f:
                if not file_exists or os.path.getsize(filename) == 0: f.write("Timestamp,KP,KI,KD,Score\n")
                log_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                data_row = (f"{log_time},{pid_params.get('kp',0):.4f},{pid_params.get('ki',0):.4f},{pid_params.get('kd',0):.4f},{score:.2f}\n")
                f.write(data_row)
        except IOError as e:
            print(f"AUTO-TUNE ERROR: Kunne ikke skrive til logfil {filename}: {e}")

    # ===================================================================
    #   KERNE LOGIK OG HÅNDTERING
    # ===================================================================
    
    def _dispatch_serial_data_to_gui(self, line):
        self.root.after_idle(self._process_incoming_line, line)

    def _update_serial_status_gui(self, message):
        self.root.after_idle(lambda: self.status_widgets.update_serial_status(message))

    def _process_incoming_line(self, line):
        if line.startswith(TAG_CSV): self._handle_csv_data(line)
        elif line.startswith(TAG_FALLEN) and self.is_running_test: self._stop_current_run("Væltet (Signal fra Robot)")
        elif line.startswith(TAG_INFO): print(f"ROBOT INFO: {line[len(TAG_INFO):].strip()}")
        elif line.startswith(TAG_ERROR):
            msg = line[len(TAG_ERROR):].strip()
            print(f"ROBOT ERROR: {msg}")
            if not self.is_auto_tuning: messagebox.showerror("Robot Fejl", msg)
        else:
            if not any(tag in line for tag in ["KP:", "KI:", "KD:"]): print(f"ROBOT UNTAGGED: {line}")
    
    def _handle_csv_data(self, line):
        if not self.is_running_test: return
        try:
            csv_data_part = line[len(TAG_CSV):].strip()
            parts = csv_data_part.split(',')
            if len(parts) != NUM_EXPECTED_CSV_COLUMNS: return

            data_tuple = tuple(map(float, parts))
            time_ms_esp, pitch = data_tuple[0], data_tuple[1]

            if not hasattr(self, 'first_data_line_in_run_received') or not self.first_data_line_in_run_received:
                self.run_start_time_esp_ms = time_ms_esp
                self.first_data_line_in_run_received = True

            current_time_s_relative = (time_ms_esp - self.run_start_time_esp_ms) / 1000.0
            full_data_tuple = (time_ms_esp, current_time_s_relative) + data_tuple[1:]
            self.current_run_data.append(full_data_tuple)
            
            self.plot_time_data.append(current_time_s_relative)
            self.plot_pitch_data.append(pitch)

            if abs(pitch) > FALLEN_PITCH_THRESHOLD_DEG:
                self._stop_current_run("Væltet (Pitch Threshold)")
        except (ValueError, IndexError): pass

    def _apply_pid_parameters(self):
        """Manuel anvendelse af PID parametre."""
        if self.is_running_test:
            messagebox.showerror("Fejl", "Stop testkørsel før parametre ændres.")
            return

        new_pid_params = {"kp": self.kp_var.get(), "ki": self.ki_var.get(), "kd": self.kd_var.get(), "init_balance": self.init_balance_var.get(), "power_gain": self.power_gain_var.get()}
        
        def on_manual_verify_complete(success, message):
            self.apply_pid_params_button.config(state="normal", text="Anvend Alle Parametre")
            if success:
                self.session_manager.start_new_session(new_pid_params)
                self.status_widgets.update_session_info(self.session_manager)
                self.status_widgets.update_run_status("✅ Parametre verificeret og anvendt!")
            else:
                self.status_widgets.update_run_status(f"❌ Fejl: {message}")
                messagebox.showerror("Parameter Fejl", f"Kunne ikke anvende parametre:\n{message}")

        self.status_widgets.update_run_status("Sender parametre til robot...")
        self.apply_pid_params_button.config(state="disabled", text="Sender...")
        self._apply_pid_parameters_with_callback(on_manual_verify_complete)

    def _apply_pid_parameters_with_callback(self, on_complete):
        """Hjælpefunktion til at sende parametre og håndtere callback."""
        try:
            new_pid_params = {"kp": self.kp_var.get(), "ki": self.ki_var.get(), "kd": self.kd_var.get(), "init_balance": self.init_balance_var.get(), "power_gain": self.power_gain_var.get()}
            if self.serial_thread.is_connected():
                self.serial_thread.send_parameters_with_verification(new_pid_params, on_complete)
            else:
                on_complete(False, "Ikke forbundet")
        except tk.TclError:
            on_complete(False, "Ugyldig værdi i et parameterfelt.")


    def _toggle_test_run(self):
        """Start/stop manuel test kørsel."""
        if self.is_auto_tuning:
            messagebox.showinfo("Info", "Kan ikke starte manuel test, mens auto-tuning kører.")
            return
        if not self.is_running_test: self._start_test_run()
        else: self._stop_current_run("Manuelt stoppet")

    def _start_test_run(self):
        """Starter en testkørsel. Bruges af både manuel og automatisk start."""
        if not self.serial_thread.is_connected():
            if not self.is_auto_tuning: messagebox.showerror("Fejl", "Ingen seriel forbindelse.")
            return

        self.current_run_data = []
        self.plot_time_data.clear()
        self.plot_pitch_data.clear()
        self.line.set_data([], [])
        self.canvas.draw_idle()

        self.is_running_test = True
        self.first_data_line_in_run_received = False
        
        if not self.is_auto_tuning:
            self.start_stop_button.config(text="Stop Testkørsel")
            self.status_widgets.update_run_status("Testkørsel aktiv...")
        
        self.serial_thread.send_command("csv_on")

    def _stop_current_run(self, reason="Ukendt"):
        """Stopper den nuværende testkørsel og håndterer resultatet."""
        if self.autostop_timer_id:
            self.root.after_cancel(self.autostop_timer_id)
            self.autostop_timer_id = None
        if self.countdown_timer_id:
            self.root.after_cancel(self.countdown_timer_id)
            self.countdown_timer_id = None

        if not self.is_running_test: return
        self.is_running_test = False
        
        self.ax.set_title("Pitch (grader)", color='black')
        self.canvas.draw_idle()
        
        if self.serial_thread.is_connected(): 
            self.serial_thread.send_command("csv_off")

        run_results = self.score_calculator.calculate_run_score(self.current_run_data)
        score, valid_time, _, _ = run_results

        if self.is_auto_tuning:
            current_job_params = self.autotuner.jobs[self.autotuner.current_job_index - 1]
            self.log_autotune_result(current_job_params, score)
            self.root.after(1000, self._autotune_tick)
        else: # Manuel kørsel logik
            self.start_stop_button.config(text="Start Testkørsel")
            self.status_widgets.update_run_status(f"Testkørsel stoppet: {reason}")
            self.status_widgets.update_run_results(score, valid_time)
            if valid_time >= MIN_VALID_RUN_DURATION_S:
                self.session_manager.add_run_result(run_results)
                self.data_logger.write_detailed_run_data(self.session_manager.get_detailed_log_filename(), self.current_run_data)
                self.status_widgets.update_session_info(self.session_manager)
            elif self.current_run_data:
                self.status_widgets.update_run_status(f"Testkørsel stoppet: {reason}. For kort ({valid_time:.2f}s) til logning.")
            else:
                self.status_widgets.update_run_status(f"Testkørsel stoppet: {reason}. Ingen data modtaget.")
    
    # ===================================================================
    #   ØVRIGE HJÆLPEMETODER
    # ===================================================================
    
    def on_closing(self):
        if messagebox.askokcancel("Luk", "Vil du afslutte programmet?"):
            self.is_auto_tuning = False
            if self.is_running_test: self._stop_current_run("Program lukket")
            
            try:
                current_params = {"kp": self.kp_var.get(), "ki": self.ki_var.get(), "kd": self.kd_var.get(), "init_balance": self.init_balance_var.get(), "power_gain": self.power_gain_var.get()}
                best_config = self.session_manager.get_best_config()
                save_pid_settings(**current_params, best_config=best_config)
            except tk.TclError:
                print("Kunne ikke gemme indstillinger ved lukning (ugyldig værdi i felt).")

            if self.serial_thread.is_alive():
                self.serial_thread.stop()
                self.serial_thread.join(timeout=1)
            self.root.destroy()
            
    def _periodic_gui_update(self):
        if self.plot_time_data:
            max_plot_points = int(PLOT_HISTORY_SECONDS / 0.015)
            while len(self.plot_time_data) > max_plot_points:
                self.plot_time_data.popleft(); self.plot_pitch_data.popleft()
            self.line.set_data(list(self.plot_time_data), list(self.plot_pitch_data))
            if self.plot_time_data:
                max_time = self.plot_time_data[-1]
                min_time = self.plot_time_data[0] if len(self.plot_time_data) >= max_plot_points else 0
                self.ax.set_xlim(min_time, max(max_time + 1, PLOT_HISTORY_SECONDS))
            self.canvas.draw_idle()
        self.root.after(100, self._periodic_gui_update)
        
    def _log_session_results(self, session_data, session_id, pid_params):
        if not session_data: return
        session_stats = self.score_calculator.calculate_session_stats(session_data)
        print(f"\n--- PID Session Opsummering (Afsluttet) ---")
        pid_str = self.session_manager._format_pid_string(pid_params)
        filename = f"data/score_{session_id:03d}_{pid_str}.csv"
        self.data_logger.write_session_summary(filename, session_id, pid_params, session_stats)

    def _send_manual_command(self):
        cmd_to_send = self.manual_cmd_var.get().strip()
        if not cmd_to_send: return
        if self.serial_thread.is_connected():
            self.serial_thread.send_command(cmd_to_send)
            self.manual_cmd_var.set("")
        else:
            messagebox.showerror("Fejl", "Ingen seriel forbindelse.")
            
    def _save_parameters_on_robot(self):
        if self.is_running_test: return
        if messagebox.askyesno("Bekræft Gem", "Gem robottens aktive tuning-parametre til NVS?"):
            if self.serial_thread.is_connected(): self.serial_thread.send_command("save")

    def _try_load_pid_from_robot(self):
        if self.serial_thread.is_connected(): self.serial_thread.send_command("print")

    def _find_latest_session_file(self):
        try:
            list_of_files = glob.glob(os.path.join(DATA_DIR, "session_*_detailed.csv"))
            return max(list_of_files, key=os.path.getmtime) if list_of_files else None
        except: return None

    def _open_grafplot_latest_session(self):
        latest_file = self._find_latest_session_file()
        if latest_file: subprocess.Popen(["python", "grafplot.py", "--file", latest_file])

    def _print_current_session(self):
        if not self.session_manager.has_run_data():
            messagebox.showinfo("Info", "Ingen kørsler i nuværende session at udskrive.")
            return
        try:
            session_info = self.session_manager.get_current_session_info()
            session_data = self.session_manager.session_run_details
            session_stats = self.score_calculator.calculate_session_stats(session_data)
            if not session_stats: return

            print("\n" + "="*60); print(f"AKTUEL MANUEL SESSION RESULTAT - Session #{session_info['session_id']}"); print("="*60)
            pid_params = session_info['pid_params']
            print(f"Parametre:\n  KP={pid_params.get('kp', 0):.4f}, KI={pid_params.get('ki', 0):.4f}, KD={pid_params.get('kd', 0):.4f}")
            print(f"  Init Balance={pid_params.get('init_balance', 0):.4f}\n  Power Gain={pid_params.get('power_gain', 0):.4f}")
            print(f"\nResultater:\n  Antal kørsler: {session_stats.get('num_runs', 0)}")
            print(f"  Gennemsnit Score: {session_stats.get('avg_score', 0):.2f}")
            
            self._log_session_results(session_data, session_info['session_id'], pid_params)
            
            current_params = {"kp": self.kp_var.get(), "ki": self.ki_var.get(), "kd": self.kd_var.get(), "init_balance": self.init_balance_var.get(), "power_gain": self.power_gain_var.get()}
            best_config = self.session_manager.get_best_config()
            save_pid_settings(**current_params, best_config=best_config)
            print("PID indstillinger gemt til pid_settings.json")
            
            messagebox.showinfo("Session Udskrevet", f"Session #{session_info['session_id']} resultat er udskrevet og gemt.")
        except Exception as e:
            print(f"FEJL ved udskrivning af session: {e}")
