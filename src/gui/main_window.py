# gui/main_window.py
"""
Hovedvindue for Robot Performance App
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

from config.settings import *
from communication.serial_handler import SerialThread
from datalogger.session_manager import SessionManager
from datalogger.data_logger import DataLogger
from analysis.score_calculator import ScoreCalculator
from gui.status_widgets import StatusWidgets


class RobotPerformanceApp:
    """
    Hovedapplikation for Robot Performance System
    """
    
    def __init__(self, root_window):
        self.root = root_window
        self.root.title(f"RobotPerformanceScore.py v0.9 (Session-based CSV logs @{TARGET_LOOP_TIME_MS:.0f}ms)")
        
        # Core components - indlæs gemte PID værdier først
        saved_pid_params, saved_best_config = load_pid_settings()
        self.session_manager = SessionManager(saved_pid_params)
        
        # Sæt bedste konfiguration hvis tilgængelig
        if saved_best_config:
            self.session_manager.set_best_config(saved_best_config)
        self.data_logger = DataLogger()
        self.score_calculator = ScoreCalculator()
        
        # Runtime state
        self.current_run_data = []
        self.is_running_test = False
        self.first_data_line_in_run_received = False
        self.run_start_time_esp_ms = 0
        self.previous_csv_timestamp_ms = None
        self.current_run_start_wallclock = None
        self.run_counter = 0
        
        # Plot data
        self.plot_time_data = deque()
        self.plot_pitch_data = deque()
        
        # Setup GUI
        self._setup_gui()
        
        # Setup serial communication
        self.serial_thread = SerialThread(
            SERIAL_PORT, BAUD_RATE, 
            self._dispatch_serial_data_to_gui, 
            self._update_serial_status_gui
        )
        self.serial_thread.start()
        
        # Start periodic updates
        self.root.after(100, self._periodic_gui_update)
        
        # Forsøg at læse PID fra robot ved startup (efter 2 sekunder)
        self.root.after(2000, self._try_load_pid_from_robot)

    def _setup_gui(self):
        """Setup hovedlayout og widgets"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        # Left panel (controls)
        left_panel = ttk.Frame(main_frame)
        left_panel.grid(row=0, column=0, padx=(0,10), pady=0, sticky="ns")
        main_frame.grid_columnconfigure(0, weight=0)

        # Right panel (plot)
        right_panel = ttk.Frame(main_frame)
        right_panel.grid(row=0, column=1, pady=0, sticky="nsew")
        main_frame.grid_columnconfigure(1, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)

        # Setup left panel components
        self._setup_pid_controls(left_panel)
        self._setup_manual_controls(left_panel)
        self._setup_test_controls(left_panel)
        
        # Setup status widgets
        self.status_widgets = StatusWidgets(left_panel, self.session_manager)
        
        # Setup plot
        self._setup_plot(right_panel)

    def _setup_pid_controls(self, parent):
        """Setup PID parameter controls"""
        param_frame = ttk.LabelFrame(parent, text="Robot Parametre")
        param_frame.grid(row=0, column=0, padx=0, pady=(0,10), sticky="ew")
        
        # Hent gemte PID parametre
        saved_pid_params, _ = load_pid_settings()
        
        # KP
        ttk.Label(param_frame, text="KP:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.kp_var = tk.DoubleVar(value=saved_pid_params["kp"])
        ttk.Entry(param_frame, textvariable=self.kp_var, width=10).grid(row=0, column=1, padx=5, pady=5)
        
        # KI
        ttk.Label(param_frame, text="KI:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.ki_var = tk.DoubleVar(value=saved_pid_params["ki"])
        ttk.Entry(param_frame, textvariable=self.ki_var, width=10).grid(row=1, column=1, padx=5, pady=5)
        
        # KD
        ttk.Label(param_frame, text="KD:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.kd_var = tk.DoubleVar(value=saved_pid_params["kd"])
        ttk.Entry(param_frame, textvariable=self.kd_var, width=10).grid(row=2, column=1, padx=5, pady=5)
        
        # Separator linje
        ttk.Separator(param_frame, orient='horizontal').grid(row=3, column=0, columnspan=2, sticky="ew", padx=5, pady=10)
        
        # Initial Balance
        ttk.Label(param_frame, text="Init Balance:").grid(row=4, column=0, padx=5, pady=5, sticky="w")
        self.init_balance_var = tk.DoubleVar(value=saved_pid_params.get("init_balance", 0.0))
        ttk.Entry(param_frame, textvariable=self.init_balance_var, width=10).grid(row=4, column=1, padx=5, pady=5)
        
        # Power Gain
        ttk.Label(param_frame, text="Power Gain:").grid(row=5, column=0, padx=5, pady=5, sticky="w")
        self.power_gain_var = tk.DoubleVar(value=saved_pid_params.get("power_gain", 0.0))
        ttk.Entry(param_frame, textvariable=self.power_gain_var, width=10).grid(row=5, column=1, padx=5, pady=5)
        
        # Apply button
        self.apply_pid_params_button = ttk.Button(
            param_frame, text="Anvend Alle Parametre", 
            command=self._apply_pid_parameters
        )
        self.apply_pid_params_button.grid(row=12, column=0, columnspan=2, pady=(10,5))

    def _setup_manual_controls(self, parent):
        """Setup manual command controls"""
        manual_cmd_frame = ttk.LabelFrame(parent, text="Manuel Kommando & Lagring")
        manual_cmd_frame.grid(row=1, column=0, padx=0, pady=(0,10), sticky="ew")
        
        # Manual command entry
        self.manual_cmd_var = tk.StringVar()
        manual_entry = ttk.Entry(manual_cmd_frame, textvariable=self.manual_cmd_var, width=25)
        manual_entry.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        manual_cmd_frame.grid_columnconfigure(0, weight=1)
        
        # Send button
        self.send_manual_cmd_button = ttk.Button(
            manual_cmd_frame, text="Send Manuel", 
            command=self._send_manual_command
        )
        self.send_manual_cmd_button.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        # Save button
        self.save_to_robot_button = ttk.Button(
            manual_cmd_frame, text="Gem på Robot (NVS)", 
            command=self._save_parameters_on_robot
        )
        self.save_to_robot_button.grid(row=1, column=0, columnspan=2, padx=5, pady=(5,5), sticky="ew")
        
    def _setup_test_controls(self, parent):
        """Setup test control buttons"""
        control_frame = ttk.LabelFrame(parent, text="Test Kontrol")
        control_frame.grid(row=2, column=0, padx=0, pady=(0,10), sticky="ew")
        
        self.start_stop_button = ttk.Button(
            control_frame, text="Start Testkørsel", 
            command=self._toggle_test_run
        )
        self.start_stop_button.pack(pady=5, padx=5, fill="x")
        
        # Tilføj Print Session knap
        self.print_session_button = ttk.Button(
            control_frame, text="Print Session Resultat", 
            command=self._print_current_session
        )
        self.print_session_button.pack(pady=5, padx=5, fill="x")
        
        # Tilføj Åbn Grafplot knap
        self.open_grafplot_button = ttk.Button(
            control_frame, text="Åbn Grafplot (Seneste Session)", 
            command=self._open_grafplot_latest_session
        )
        self.open_grafplot_button.pack(pady=5, padx=5, fill="x")

    def _setup_plot(self, parent):
        """Setup matplotlib plot"""
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

    def _dispatch_serial_data_to_gui(self, line):
        """Dispatch serial data til GUI thread"""
        self.root.after_idle(self._process_incoming_line, line)

    def _update_serial_status_gui(self, message):
        """Opdater serial status i GUI"""
        # Check for special PID response message
        if message.startswith("PID_RESPONSE:"):
            try:
                pid_data = message[13:]  # Remove "PID_RESPONSE:" prefix
                parts = pid_data.split(',')
                
                # Minimum KP, KI, KD
                if len(parts) >= 3:
                    pid_params = {
                        "kp": float(parts[0]),
                        "ki": float(parts[1]),
                        "kd": float(parts[2])
                    }
                    
                    # Tilføj Init Balance hvis tilgængelig
                    if len(parts) >= 4:
                        pid_params["init_balance"] = float(parts[3])
                    
                    # Tilføj Power Gain hvis tilgængelig
                    if len(parts) >= 5:
                        pid_params["power_gain"] = float(parts[4])
                    
                    self.root.after_idle(lambda: self._handle_pid_from_robot(pid_params, None))
                else:
                    print(f"Fejl: For få parametre i PID response: {pid_data}")
            except Exception as e:
                print(f"Fejl ved håndtering af PID response: {e}")
        else:
            self.root.after_idle(lambda: self.status_widgets.update_serial_status(message))

    def _process_incoming_line(self, line):
        """Process indkommende serial linje"""
        if line.startswith(TAG_CSV):
            self._handle_csv_data(line)
        elif line.startswith(TAG_FALLEN):
            if self.is_running_test:
                self._stop_current_run("Væltet (Signal fra Robot)")
        elif line.startswith(TAG_INFO):
            info_message = line[len(TAG_INFO):].strip()
            print(f"ROBOT INFO: {info_message}")
            
            # Check hvis denne INFO linje indeholder PID data
            if self.serial_thread.waiting_for_pid_response:
                if self.serial_thread._handle_potential_pid_response(info_message):
                    return  # PID blev håndteret, skip resten
                    
        elif line.startswith(TAG_ERROR):
            error_message = line[len(TAG_ERROR):].strip()
            print(f"ROBOT ERROR: {error_message}")
            messagebox.showerror("Robot Fejl", error_message)
            self.status_widgets.update_serial_status(f"Robot Fejl: {error_message[:50]}...")
        else:
            print(f"ROBOT UNTAGGED: {line}")
            
            # Check også untagged linjer for PID response
            if self.serial_thread.waiting_for_pid_response:
                self.serial_thread._handle_potential_pid_response(line)

    def _handle_csv_data(self, line):
        """Håndter CSV data fra robot"""
        if not self.is_running_test:
            return
            
        csv_data_part = line[len(TAG_CSV):].strip()
        try:
            parts = csv_data_part.split(',')
            
            # Bagudkompatibel: Accepter både gamle (8 kolonner) og nye (13 kolonner) format
            if len(parts) != 8:
                print(f"ROBOT WARNING (Malformed CSV - expected 8 or 13 columns, got {len(parts)}): {line}")
                return

            time_ms_esp = float(parts[0])
            pitch = float(parts[1])
            pitch_rate = float(parts[2])
            balance_cmd = float(parts[3])  # var pid_output før
            p_term = float(parts[4])
            i_term = float(parts[5])
            d_term = float(parts[6])
            scaled_output = float(parts[7])

            # Handle timing
            if self.first_data_line_in_run_received:
                if self.previous_csv_timestamp_ms is not None:
                    interval_ms = time_ms_esp - self.previous_csv_timestamp_ms
                self.previous_csv_timestamp_ms = time_ms_esp
            else:
                self.run_start_time_esp_ms = time_ms_esp
                self.previous_csv_timestamp_ms = time_ms_esp
                self.first_data_line_in_run_received = True
            
            # Calculate relative time and store data
            current_time_s_relative = (time_ms_esp - self.run_start_time_esp_ms) / 1000.0
            self.current_run_data.append((
                time_ms_esp, current_time_s_relative, pitch, pitch_rate, balance_cmd, p_term, i_term, d_term,
                scaled_output
            ))
            
            # Update plot data
            self.plot_time_data.append(current_time_s_relative)
            self.plot_pitch_data.append(pitch)

            # Check for fall
            if abs(pitch) > FALLEN_PITCH_THRESHOLD_DEG:
                self._stop_current_run("Væltet (Pitch Threshold)")
                
        except ValueError:
            print(f"ROBOT WARNING (ValueError in CSV data part): {line}")

    def _apply_pid_parameters(self):
        """Anvend nye PID parametre"""
        if self.is_running_test:
            messagebox.showerror("Fejl", "Stop testkørsel før parametre ændres.")
            return
        
        new_pid_params = {
            "kp": self.kp_var.get(),
            "ki": self.ki_var.get(),
            "kd": self.kd_var.get(),
            "init_balance": self.init_balance_var.get(),
            "power_gain": self.power_gain_var.get(),
        }

        current_params = self.session_manager.current_pid_params
        
        if new_pid_params != current_params:
            self.status_widgets.update_run_status("Sender parametre til robot...")
            
            # Deaktiver knap mens vi sender
            self.apply_pid_params_button.config(state="disabled", text="Sender...")
            
            # Send med verification
            if self.serial_thread.is_connected():
                self.serial_thread.send_parameters_with_verification(
                    new_pid_params, 
                    self._handle_parameter_verification_result
                )
            else:
                self.apply_pid_params_button.config(state="normal", text="Anvend Alle Parametre")
                messagebox.showerror("Fejl", "Ingen seriel forbindelse.")
        else:
            self.status_widgets.update_run_status("Parametre uændrede.")

    def _handle_parameter_verification_result(self, success, message):
        """Håndter resultat af parameter verification"""
        # Genaktiver knap
        self.apply_pid_params_button.config(state="normal", text="Anvend Alle Parametre")
        
        if success:
            print(f"PARAMETER SUCCESS: {message}")
            
            # Gem parametre til session og fil
            new_pid_params = {
                "kp": self.kp_var.get(),
                "ki": self.ki_var.get(),
                "kd": self.kd_var.get(),
                "init_balance": self.init_balance_var.get(),
                "power_gain": self.power_gain_var.get(),
            }
            
            # Start new session
            old_session_data, old_session_id, old_pid_params = self.session_manager.start_new_session(new_pid_params)
            
            # Log old session if it had data
            if old_session_data:
                self._log_session_results(old_session_data, old_session_id, old_pid_params)
            
            # GEM alle parametre til fil
            best_config = self.session_manager.get_best_config()
            save_pid_settings(
                new_pid_params['kp'], 
                new_pid_params['ki'], 
                new_pid_params['kd'],
                new_pid_params['init_balance'],
                new_pid_params['power_gain'],
                best_config
            )
            
            # Update GUI
            self.status_widgets.update_session_info(self.session_manager)
            self.status_widgets.update_run_status("✅ Alle parametre verificeret og anvendt!")
            
        else:
            print(f"PARAMETER FEJL: {message}")
            self.status_widgets.update_run_status(f"❌ Fejl: {message}")
            messagebox.showerror("Parameter Fejl", 
                f"Kunne ikke anvende parametre:\n{message}\n\n"
                "Prøv igen eller tjek robot forbindelse.")

    def _send_manual_command(self):
        """Send manuel kommando"""
        cmd_to_send = self.manual_cmd_var.get().strip()
        if not cmd_to_send:
            messagebox.showinfo("Info", "Intet at sende. Indtast en kommando.")
            return
            
        if self.is_running_test and cmd_to_send.lower() not in ["csv_off", "stop"]:
            if not messagebox.askyesno("Advarsel", 
                f"En testkørsel er aktiv. Sikker på du vil sende '{cmd_to_send}'?"):
                return
        
        if self.serial_thread.is_connected():
            self.serial_thread.send_command(cmd_to_send)
            self.manual_cmd_var.set("")
        else:
            messagebox.showerror("Fejl", "Ingen seriel forbindelse til at sende kommando.")

    def _save_parameters_on_robot(self):
        """Gem parametre på robot"""
        if self.is_running_test:
            messagebox.showwarning("Advarsel", "Stop testkørsel før du gemmer på robotten.")
            return
            
        if messagebox.askyesno("Bekræft Gem", 
            "Gem robottens aktive tuning-parametre til NVS?\n"
            "(Sørg for at de ønskede værdier er aktive på robotten)"):
            
            if self.serial_thread.is_connected():
                self.serial_thread.send_command("save")
                self.status_widgets.update_run_status("Sendt 'save' kommando til robot.")
            else:
                messagebox.showerror("Fejl", "Ingen seriel forbindelse til 'save' kommando.")

    def _toggle_test_run(self):
        """Start/stop test kørsel"""
        if not self.is_running_test:
            self._start_test_run()
        else:
            self._stop_current_run("Manuelt stoppet")

    def _start_test_run(self):
        """Start ny test kørsel"""
        # Validate ALL parameters
        gui_pid_params = {
            "kp": self.kp_var.get(),
            "ki": self.ki_var.get(),
            "kd": self.kd_var.get(),
            "init_balance": self.init_balance_var.get(),
            "power_gain": self.power_gain_var.get(),
        }
        
        if gui_pid_params != self.session_manager.current_pid_params:
            messagebox.showwarning("Advarsel", "Parametre i GUI er ikke anvendt. Anvend dem først.")
            return
        
        # Check serial connection - debug output
        print(f"DEBUG: Checking serial connection...")
        print(f"DEBUG: serial_thread.running = {self.serial_thread.running}")
        print(f"DEBUG: serial_thread.serial_port = {self.serial_thread.serial_port}")
        if self.serial_thread.serial_port:
            print(f"DEBUG: serial_port.is_open = {self.serial_thread.serial_port.is_open}")
        print(f"DEBUG: is_connected() = {self.serial_thread.is_connected()}")
        
        if not self.serial_thread.is_connected():
            # Prøv at tjekke om vi kan sende en kommando alligevel
            print("DEBUG: is_connected() returned False, men prøver at sende kommando...")
            if self.serial_thread.send_command("status"):
                print("DEBUG: Kommando sendt på trods af is_connected() = False")
                # Fortsæt med test alligevel
            else:
                messagebox.showerror("Fejl", "Ingen seriel forbindelse. Kan ikke starte test.")
                return

        # Initialize run
        self.current_run_start_wallclock = datetime.datetime.now()
        self.is_running_test = True
        self.first_data_line_in_run_received = False
        self.previous_csv_timestamp_ms = None
        self.run_start_time_esp_ms = 0
        self.run_counter += 1
        
        # Update GUI
        self.start_stop_button.config(text="Stop Testkørsel")
        self.status_widgets.update_run_status("Testkørsel aktiv...")
        
        # Clear data
        self.current_run_data = []
        self.plot_time_data.clear()
        self.plot_pitch_data.clear()
        self.line.set_data([], [])
        self.canvas.draw_idle()

        # Start CSV logging on robot
        print("DEBUG: Sender csv_on kommando...")
        success = self.serial_thread.send_command("csv_on")
        print(f"DEBUG: csv_on kommando sendt, success = {success}")

    def _stop_current_run(self, reason="Ukendt"):
        """Stop current test run"""
        if not self.is_running_test:
            return

        self.is_running_test = False
        
        # Stop CSV logging on robot
        if self.serial_thread.is_connected():
            self.serial_thread.send_command("csv_off")
        
        # Update GUI
        self.start_stop_button.config(text="Start Testkørsel")
        self.status_widgets.update_run_status(f"Testkørsel stoppet: {reason}")

        if not self.current_run_data:
            self.status_widgets.update_run_status(f"Testkørsel stoppet: {reason}. Ingen data modtaget.")
            self.status_widgets.update_run_results(None, None)
            return

        # Calculate score
        run_results = self.score_calculator.calculate_run_score(self.current_run_data)
        score, valid_time, total_duration, oscillation_metrics = run_results
        
        # Update GUI with results
        self.status_widgets.update_run_results(score, valid_time)

        # Add to session if valid
        if valid_time >= MIN_VALID_RUN_DURATION_S:
            # Gem tidligere bedste score for sammenligning
            previous_best = self.session_manager.get_best_config()
            previous_best_score = previous_best['avg_score'] if previous_best else float('-inf')
            
            self.session_manager.add_run_result(run_results)
            
            # Check om der er ny bedste konfiguration
            current_best = self.session_manager.get_best_config()
            if current_best and current_best['avg_score'] > previous_best_score:
                self.status_widgets.highlight_new_best_config()
            
            # Log detailed data
            self.data_logger.write_detailed_run_data(
                self.session_manager.get_detailed_log_filename(),
                self.current_run_data
            )
            
            # Update session display
            self.status_widgets.update_session_info(self.session_manager)
        else:
            self.status_widgets.update_run_status(
                f"Testkørsel stoppet: {reason}. "
                f"Kørsel for kort ({valid_time:.2f}s) til session/log."
            )

    def _log_session_results(self, session_data, session_id, pid_params):
        """Log session resultater"""
        if not session_data:
            return
            
        # Calculate session stats
        session_stats = self.score_calculator.calculate_session_stats(session_data)
        
        # Print summary
        print(f"\n--- PID Session Opsummering (Afsluttet) ---")
        print(f"Session #{session_id}")
        print(f"Parametre: KP={pid_params['kp']:.4f}, KI={pid_params['ki']:.4f}, KD={pid_params['kd']:.4f}")
        if 'init_balance' in pid_params:
            print(f"           Init={pid_params['init_balance']:.4f}, Gain={pid_params.get('power_gain', 0.0):.4f}")
        print(f"Antal kørsler: {session_stats['num_runs']}")
        print(f"Gns. Score: {session_stats['avg_score']:.2f}")
        print(f"Max Score: {session_stats.get('max_score', 0):.2f}")
        print(f"Min Score: {session_stats.get('min_score', 0):.2f}")
        print(f"-------------------------------------------\n")
        
        # Write to file - brug korrekt score fil navngivning
        init_str = f"_I{pid_params.get('init_balance', 0.0):.2f}" if 'init_balance' in pid_params else ""
        gain_str = f"_G{pid_params.get('power_gain', 0.0):.2f}" if 'power_gain' in pid_params else ""
        prev_pid_str = f"KP{pid_params['kp']:.2f}_KI{pid_params['ki']:.2f}_KD{pid_params['kd']:.2f}{init_str}{gain_str}"
        filename = f"data/score_{session_id:03d}_{prev_pid_str}.csv"
        
        self.data_logger.write_session_summary(filename, session_id, pid_params, session_stats)

    def _periodic_gui_update(self):
        """Periodisk GUI opdatering"""
        if self.plot_time_data:
            max_plot_points = int(PLOT_HISTORY_SECONDS / 0.015)
            while len(self.plot_time_data) > max_plot_points:
                self.plot_time_data.popleft()
                self.plot_pitch_data.popleft()
            
            current_plot_time = list(self.plot_time_data)
            current_plot_pitch = list(self.plot_pitch_data)
            self.line.set_data(current_plot_time, current_plot_pitch)
            
            if current_plot_time:
                max_time_on_plot = max(PLOT_HISTORY_SECONDS, 
                                     current_plot_time[-1] if current_plot_time else PLOT_HISTORY_SECONDS)
                min_time_on_plot = (current_plot_time[0] 
                                  if len(self.plot_time_data) >= max_plot_points else 0)
                self.ax.set_xlim(min_time_on_plot, max_time_on_plot + 1)
            else:
                self.ax.set_xlim(0, PLOT_HISTORY_SECONDS)
            
            try:
                self.canvas.draw_idle()
            except Exception as e:
                print(f"Fejl under opdatering af plot: {e}")
        
        self.root.after(100, self._periodic_gui_update)

    def on_closing(self):
        """Håndter lukning af applikation"""
        if messagebox.askokcancel("Luk", "Vil du afslutte programmet?"):
            if self.is_running_test:
                self._stop_current_run("Program lukket")
            
            # Gem alle aktuelle parametre før lukning
            current_params = {
                "kp": self.kp_var.get(),
                "ki": self.ki_var.get(),
                "kd": self.kd_var.get(),
                "init_balance": self.init_balance_var.get(),
                "power_gain": self.power_gain_var.get(),
            }
            best_config = self.session_manager.get_best_config()
            save_pid_settings(
                current_params['kp'], 
                current_params['ki'], 
                current_params['kd'],
                current_params['init_balance'],
                current_params['power_gain'],
                best_config
            )
            print("Alle parametre gemt før lukning")
            
            # Gem parametre på robot (NVS) 
            if self.serial_thread.is_connected():
                print("Gemmer parametre på robot...")
                self.serial_thread.save_parameters_to_robot(self._handle_robot_save_callback)
                # Vent kort på at kommandoen sendes
                time.sleep(0.5)
            else:
                print("Ikke forbundet til robot - spring NVS gem over")
            
            # Log current session if it has data
            if self.session_manager.has_run_data():
                session_info = self.session_manager.get_current_session_info()
                self._log_session_results(
                    self.session_manager.session_run_details,
                    session_info['session_id'],
                    session_info['pid_params']
                )
            
            # Stop serial thread
            if self.serial_thread.is_alive():
                self.serial_thread.stop()
                self.serial_thread.join(timeout=1)
            
            self.root.destroy()

    def _handle_robot_save_callback(self, success, message):
        """Callback for robot save operation"""
        if success:
            print(f"Robot save: {message}")
        else:
            print(f"Robot save fejl: {message}")

    def _try_load_pid_from_robot(self):
      """Forsøg at læse PID parametre fra robot ved startup"""
      try:
          print("DEBUG: _try_load_pid_from_robot startet")
          
          if self.serial_thread.is_connected():
              print("DEBUG: Serial er forbundet, sender request...")
              self.status_widgets.update_run_status("Læser PID parametre fra robot...")
              
              # SIMPLE VERSION - bare send print uden callback
              success = self.serial_thread.send_command("print")
              print(f"DEBUG: Print kommando sendt, success = {success}")
              
              # Vent lidt og opdater status
              self.root.after(3000, lambda: self.status_widgets.update_run_status("PID læsning afsluttet"))
              
          else:
              print("DEBUG: Ikke forbundet til robot - bruger gemte/default PID værdier")
              
          print("DEBUG: _try_load_pid_from_robot afsluttet")
          
      except Exception as e:
          print(f"FEJL i _try_load_pid_from_robot: {e}")
          import traceback
          traceback.print_exc()

    def _handle_pid_from_robot(self, pid_params, error):
        """Håndter PID parametre læst fra robot"""
        try:
            if error:
                print(f"Kunne ikke læse PID fra robot: {error}")
                self.status_widgets.update_run_status("Bruger gemte PID værdier")
                return
            
            if pid_params:
                print(f"Parametre læst fra robot:")
                print(f"  KP={pid_params['kp']}, KI={pid_params['ki']}, KD={pid_params['kd']}")
                if 'init_balance' in pid_params:
                    print(f"  Init Balance={pid_params['init_balance']}")
                if 'power_gain' in pid_params:
                    print(f"  Power Gain={pid_params['power_gain']}")
                
                current_params = self.session_manager.current_pid_params
                print(f"Current session parametre:")
                print(f"  KP={current_params['kp']}, KI={current_params['ki']}, KD={current_params['kd']}")
                print(f"  Init={current_params.get('init_balance', 0.0)}, Gain={current_params.get('power_gain', 0.0)}")
                
                # Opdater GUI værdier med alle tilgængelige parametre
                self.kp_var.set(pid_params['kp'])
                self.ki_var.set(pid_params['ki'])
                self.kd_var.set(pid_params['kd'])
                
                # Opdater Init Balance hvis modtaget fra robot
                if 'init_balance' in pid_params:
                    self.init_balance_var.set(pid_params['init_balance'])
                
                # Opdater Power Gain hvis modtaget fra robot
                if 'power_gain' in pid_params:
                    self.power_gain_var.set(pid_params['power_gain'])
                
                # Saml alle parametre
                full_params = {
                    "kp": pid_params['kp'],
                    "ki": pid_params['ki'],
                    "kd": pid_params['kd'],
                    "init_balance": pid_params.get('init_balance', self.init_balance_var.get()),
                    "power_gain": pid_params.get('power_gain', self.power_gain_var.get()),
                }
                
                # Gem til fil for næste gang
                best_config = self.session_manager.get_best_config()
                save_pid_settings(
                    full_params['kp'], 
                    full_params['ki'], 
                    full_params['kd'],
                    full_params['init_balance'],
                    full_params['power_gain'],
                    best_config
                )
                
                # Opdater session manager hvis forskelligt fra current
                if full_params != self.session_manager.current_pid_params:
                    old_session_data, old_session_id, old_pid_params = self.session_manager.start_new_session(full_params)
                    if old_session_data:
                        self._log_session_results(old_session_data, old_session_id, old_pid_params)
                    self.status_widgets.update_session_info(self.session_manager)
                
                self.status_widgets.update_run_status("Alle parametre hentet fra robot")
                
        except Exception as e:
            print(f"FEJL i _handle_pid_from_robot: {e}")
            import traceback
            traceback.print_exc()

    def _find_latest_session_file(self):
        """Find den seneste session detailed CSV fil"""
        try:
            # Find alle session_*_detailed.csv filer
            pattern = os.path.join(DATA_DIR, "session_*_detailed.csv")
            session_files = glob.glob(pattern)
            
            if not session_files:
                return None
            
            # Sorter efter ændringsdato (seneste først)
            session_files.sort(key=os.path.getmtime, reverse=True)
            latest_file = session_files[0]
            
            print(f"Seneste session fil fundet: {latest_file}")
            return latest_file
            
        except Exception as e:
            print(f"Fejl ved søgning efter session filer: {e}")
            return None

    def _open_grafplot_latest_session(self):
        """Åbn grafplot.py med den seneste session fil"""
        try:
            # Find seneste session fil
            latest_session_file = self._find_latest_session_file()
            
            if not latest_session_file:
                messagebox.showwarning(
                    "Ingen Session Filer", 
                    "Ingen session filer fundet i data/ mappen.\n"
                    "Kør en test først for at generere data."
                )
                return
            
            # Kontroller at grafplot.py eksisterer
            grafplot_path = "grafplot.py"
            if not os.path.exists(grafplot_path):
                messagebox.showerror(
                    "Grafplot Ikke Fundet",
                    f"grafplot.py ikke fundet i {os.getcwd()}\n"
                    "Sørg for at filen eksisterer."
                )
                return
            
            # Start grafplot.py med session filen
            cmd = ["python", grafplot_path, "--file", latest_session_file]
            
            print(f"Starter grafplot.py med kommando: {' '.join(cmd)}")
            
            # Start som separat proces
            subprocess.Popen(cmd, cwd=os.getcwd())
            
            # Vis besked til bruger
            session_name = os.path.basename(latest_session_file)
            messagebox.showinfo(
                "Grafplot Startet", 
                f"Grafplot.py er startet med:\n{session_name}\n\n"
                "Grafplot åbner i et nyt vindue."
            )
            
        except Exception as e:
            print(f"Fejl ved start af grafplot: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror(
                "Fejl", 
                f"Kunne ikke starte grafplot.py:\n{e}"
            )

    def _print_current_session(self):
        """Print nuværende session resultat til console og log fil"""
        try:
            if not self.session_manager.has_run_data():
                print("INGEN SESSION DATA - Ingen kørsler at udskrive")
                messagebox.showinfo("Info", "Ingen kørsler i nuværende session at udskrive")
                return
            
            # Hent session info
            session_info = self.session_manager.get_current_session_info()
            session_data = self.session_manager.session_run_details
            
            # Beregn statistikker
            session_stats = self.score_calculator.calculate_session_stats(session_data)
            
            # Print til console
            print("\n" + "="*60)
            print(f"AKTUEL SESSION RESULTAT - Session #{session_info['session_id']}")
            print("="*60)
            print(f"Parametre:")
            print(f"  KP={session_info['pid_params']['kp']:.4f}")
            print(f"  KI={session_info['pid_params']['ki']:.4f}")
            print(f"  KD={session_info['pid_params']['kd']:.4f}")
            if 'init_balance' in session_info['pid_params']:
                print(f"  Init Balance={session_info['pid_params']['init_balance']:.4f}")
            if 'power_gain' in session_info['pid_params']:
                print(f"  Power Gain={session_info['pid_params']['power_gain']:.4f}")
            
            print(f"\nResultater:")
            print(f"  Antal kørsler: {session_stats['num_runs']}")
            print(f"  Gennemsnit Score: {session_stats['avg_score']:.2f}")
            print(f"  Højeste Score: {session_stats.get('max_score', 0):.2f}")
            print(f"  Laveste Score: {session_stats.get('min_score', 0):.2f}")
            print(f"  Gns. Valid Tid: {session_stats['avg_valid_time']:.2f}s")
            print(f"  Gns. Total Varighed: {session_stats['avg_total_duration']:.2f}s")
            
            if session_stats['avg_amplitude_rms'] != float('inf'):
                print(f"  Gns. Oscillation Amplitude: {session_stats['avg_amplitude_rms']:.3f}°")
            if session_stats['avg_frequency'] > 0:
                print(f"  Gns. Oscillation Frekvens: {session_stats['avg_frequency']:.2f} Hz")
            if session_stats['avg_degradation'] > 0:
                print(f"  Gns. Degradation: {session_stats['avg_degradation']:.3f}")
            
            print("\nIndividuelle kørsler:")
            for i, run_result in enumerate(session_data, 1):
                if len(run_result) >= 4:
                    score, valid_time, total_duration, metrics = run_result
                    amp = metrics.get('amplitude_rms', 0) if isinstance(metrics, dict) else 0
                    print(f"  Kørsel {i}: Score={score:.2f}, Valid={valid_time:.2f}s, "
                          f"Total={total_duration:.2f}s, Amp={amp:.2f}°")
                else:
                    # Fallback for gamle data
                    score, time_upright, total_duration = run_result[:3]
                    print(f"  Kørsel {i}: Score={score:.2f}, Oprejst={time_upright:.2f}s, "
                          f"Total={total_duration:.2f}s")
            
            print("="*60)
            
            # Skriv også til CSV fil
            self._log_session_results(
                session_data, 
                session_info['session_id'], 
                session_info['pid_params']
            )
            
            # Gem også PID indstillinger med opdateret bedste config
            current_params = {
                "kp": self.kp_var.get(),
                "ki": self.ki_var.get(),
                "kd": self.kd_var.get(),
                "init_balance": self.init_balance_var.get(),
                "power_gain": self.power_gain_var.get(),
            }
            best_config = self.session_manager.get_best_config()
            save_pid_settings(
                current_params['kp'], 
                current_params['ki'], 
                current_params['kd'],
                current_params['init_balance'],
                current_params['power_gain'],
                best_config
            )
            print("PID indstillinger gemt ved session udskrift")
            
            # Vis besked til bruger
            messagebox.showinfo(
                "Session Udskrevet", 
                f"Session #{session_info['session_id']} resultat udskrevet til console og gemt til CSV.\n\n"
                f"Kørsler: {session_stats['num_runs']}\n"
                f"Gns. Score: {session_stats['avg_score']:.2f}\n"
                f"Højeste Score: {session_stats.get('max_score', 0):.2f}"
            )
            
        except Exception as e:
            print(f"FEJL ved udskrivning af session: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("Fejl", f"Kunne ikke udskrive session: {e}")