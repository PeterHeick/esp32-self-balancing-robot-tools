# RobotPerformanceMåler.py
# Robot Performance Måler v0.5

import tkinter as tk
from tkinter import ttk, messagebox
import serial
import threading
import time
import numpy as np
from collections import deque
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from scipy.signal import find_peaks

# --- Konfigurationsparametre ---
SERIAL_PORT = '/dev/ttyUSB0'
BAUD_RATE = 115200
CSV_EXPECTED_COLUMNS_NAMES = ["time_ms", "pitch", "pid_output", "p_term", "i_term", "d_term"]
NUM_EXPECTED_CSV_COLUMNS = len(CSV_EXPECTED_COLUMNS_NAMES)

BALANCED_PITCH_THRESHOLD_DEG = 2.5
FALLEN_PITCH_THRESHOLD_DEG = 30.0
MIN_VALID_RUN_DURATION_S = 2.0
PLOT_HISTORY_SECONDS = 10
TARGET_LOOP_TIME_MS = 15.0
LOOP_TIME_WARNING_THRESHOLD_MS = TARGET_LOOP_TIME_MS + 1.0 # Advarsel hvis > 16ms

# --- Tags (skal matche ESP32 output) ---
TAG_CSV = "TAG_CSV:"
TAG_FALLEN = "TAG_FALLEN"
TAG_INFO = "TAG_INFO:"
TAG_ERROR = "TAG_ERROR:"


class SerialThread(threading.Thread):
    def __init__(self, port, baudrate, data_callback, status_callback_gui):
        super().__init__(daemon=True)
        self.port_name = port
        self.baudrate = baudrate
        self.data_callback = data_callback
        self.status_callback_gui = status_callback_gui
        self.serial_port = None
        self.running = False
        self._stop_event = threading.Event()

    def connect(self):
        try:
            self.serial_port = serial.Serial(self.port_name, self.baudrate, timeout=1)
            self.running = True
            self.status_callback_gui(f"Forbundet til {self.port_name}")
            return True
        except serial.SerialException as e:
            self.status_callback_gui(f"Fejl ved forbindelse: {e}")
            self.running = False
            return False

    def run(self):
        if not self.serial_port or not self.serial_port.is_open:
            if not self.connect():
                self.status_callback_gui("Initiel forbindelse fejlede. Tråd afslutter.")
                return
        while not self._stop_event.is_set():
            if self.serial_port and self.serial_port.is_open:
                try:
                    line = self.serial_port.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        self.data_callback(line)
                except serial.SerialException:
                    self.status_callback_gui("Seriel forbindelse tabt. Prøver at genoprette...")
                    self.close_connection()
                    time.sleep(2)
                    if not self._stop_event.is_set() and not self.connect():
                        self.status_callback_gui("Genopretning fejlede. Vent venligst.")
                        time.sleep(3)
                except Exception as e: 
                    if not self._stop_event.is_set():
                        self.status_callback_gui(f"Ukendt seriel læsefejl: {e}")
                        time.sleep(0.1) 
            else: 
                if not self._stop_event.is_set():
                    self.status_callback_gui("Port ikke åben. Forsøger at genoprette...")
                    time.sleep(2)
                    if not self._stop_event.is_set() and not self.connect(): 
                        self.status_callback_gui("Genopretning fejlede. Vent venligst.")
                        time.sleep(3)
        self.close_connection()

    def send_command(self, command_str):
        if self.serial_port and self.serial_port.is_open and self.running:
            try:
                full_command = command_str + '\n'
                self.serial_port.write(full_command.encode('utf-8'))
                print(f"PYTHON SENT: {command_str}") 
                self.status_callback_gui(f"Sendt: {command_str}")
            except serial.SerialException as e:
                self.status_callback_gui(f"Fejl ved send: {e}")
        else:
            self.status_callback_gui("Kan ikke sende: Ikke forbundet.")

    def close_connection(self):
        if self.serial_port and self.serial_port.is_open:
            try: self.serial_port.close()
            except Exception: pass
        self.serial_port = None

    def stop(self):
        self._stop_event.set()
        self.running = False


class RobotPerformanceApp:
    def __init__(self, root_window):
        self.root = root_window
        self.root.title(f"Robot Performance Måler v0.5 (Loop Tjek @{TARGET_LOOP_TIME_MS:.0f}ms)")

        self.current_run_data = []
        self.is_running_test = False
        self.first_data_line_in_run_received = False
        self.run_start_time_esp_ms = 0
        self.previous_csv_timestamp_ms = None # Til at tjekke loop tid

        self.current_session_runs_scores = []
        self.current_pid_params = {"kp": 3.3, "ki": 0.0, "kd": 0.20} 
        self.previous_pid_params_for_session = self.current_pid_params.copy()

        # --- GUI Opsætning (identisk med v0.4, undtagen titel) ---
        main_frame = ttk.Frame(root_window, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")
        root_window.grid_columnconfigure(0, weight=1)
        root_window.grid_rowconfigure(0, weight=1)

        left_panel = ttk.Frame(main_frame)
        left_panel.grid(row=0, column=0, padx=(0,10), pady=0, sticky="ns")
        main_frame.grid_columnconfigure(0, weight=0) 

        right_panel = ttk.Frame(main_frame) 
        right_panel.grid(row=0, column=1, pady=0, sticky="nsew")
        main_frame.grid_columnconfigure(1, weight=1) 
        main_frame.grid_rowconfigure(0, weight=1)

        param_frame = ttk.LabelFrame(left_panel, text="PID Parametre (KP, KI, KD)")
        param_frame.grid(row=0, column=0, padx=0, pady=(0,10), sticky="ew")
        ttk.Label(param_frame, text="KP:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.kp_var = tk.DoubleVar(value=self.current_pid_params["kp"])
        ttk.Entry(param_frame, textvariable=self.kp_var, width=10).grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(param_frame, text="KI:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.ki_var = tk.DoubleVar(value=self.current_pid_params["ki"])
        ttk.Entry(param_frame, textvariable=self.ki_var, width=10).grid(row=1, column=1, padx=5, pady=5)
        ttk.Label(param_frame, text="KD:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.kd_var = tk.DoubleVar(value=self.current_pid_params["kd"])
        ttk.Entry(param_frame, textvariable=self.kd_var, width=10).grid(row=2, column=1, padx=5, pady=5)
        self.apply_pid_params_button = ttk.Button(param_frame, text="Anvend PID Parametre", command=self.apply_pid_parameters)
        self.apply_pid_params_button.grid(row=3, column=0, columnspan=2, pady=(10,5))

        manual_cmd_frame = ttk.LabelFrame(left_panel, text="Manuel Kommando & Lagring")
        manual_cmd_frame.grid(row=1, column=0, padx=0, pady=(0,10), sticky="ew")
        self.manual_cmd_var = tk.StringVar()
        manual_entry = ttk.Entry(manual_cmd_frame, textvariable=self.manual_cmd_var, width=25)
        manual_entry.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        manual_cmd_frame.grid_columnconfigure(0, weight=1)
        self.send_manual_cmd_button = ttk.Button(manual_cmd_frame, text="Send Manuel", command=self.send_manual_command)
        self.send_manual_cmd_button.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.save_to_robot_button = ttk.Button(manual_cmd_frame, text="Gem på Robot (NVS)", command=self.save_parameters_on_robot)
        self.save_to_robot_button.grid(row=1, column=0, columnspan=2, padx=5, pady=(5,5), sticky="ew")

        control_frame = ttk.LabelFrame(left_panel, text="Test Kontrol")
        control_frame.grid(row=2, column=0, padx=0, pady=(0,10), sticky="ew")
        self.start_stop_button = ttk.Button(control_frame, text="Start Testkørsel", command=self.toggle_test_run)
        self.start_stop_button.pack(pady=5, padx=5, fill="x")

        status_frame = ttk.LabelFrame(left_panel, text="Status & Score")
        status_frame.grid(row=3, column=0, padx=0, pady=0, sticky="ew")
        status_frame.grid_columnconfigure(0, weight=1) 
        self.serial_status_label = ttk.Label(status_frame, text="Seriel Status: Initialiserer...")
        self.serial_status_label.grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.run_status_label = ttk.Label(status_frame, text="Kørsel Status: Standby")
        self.run_status_label.grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.current_score_label = ttk.Label(status_frame, text="Nuværende Score: -")
        self.current_score_label.grid(row=2, column=0, sticky="w", padx=5, pady=2)
        self.time_upright_label = ttk.Label(status_frame, text="Tid Oprejst: - s")
        self.time_upright_label.grid(row=3, column=0, sticky="w", padx=5, pady=2)
        self.session_score_label = ttk.Label(status_frame, text="Session Gns. Score: -")
        self.session_score_label.grid(row=4, column=0, sticky="w", padx=5, pady=2)
        self.session_runs_label = ttk.Label(status_frame, text="Kørsler i session: 0")
        self.session_runs_label.grid(row=5, column=0, sticky="w", padx=5, pady=2)

        self.fig = Figure(figsize=(8, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_ylim(-FALLEN_PITCH_THRESHOLD_DEG - 5, FALLEN_PITCH_THRESHOLD_DEG + 5)
        self.ax.set_xlabel("Tid relativt til start af kørsel (s)")
        self.ax.set_ylabel("Pitch (grader)")
        self.ax.grid(True)
        self.line, = self.ax.plot([], [], lw=1.5, color='dodgerblue')
        self.plot_time_data = deque()
        self.plot_pitch_data = deque()
        self.canvas = FigureCanvasTkAgg(self.fig, master=right_panel)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill=tk.BOTH, expand=True)
        self.canvas.draw()

        self.serial_thread = SerialThread(SERIAL_PORT, BAUD_RATE, self.dispatch_serial_data_to_gui, self.update_serial_status_gui)
        self.serial_thread.start()
        self.root.after(100, self.periodic_gui_update)

    def dispatch_serial_data_to_gui(self, line):
        self.root.after_idle(self.process_incoming_line, line)

    def update_serial_status_gui(self, message):
        self.root.after_idle(lambda: self.serial_status_label.config(text=f"Seriel Status: {message}"))

    def update_run_status_gui(self, message):
        self.run_status_label.config(text=f"Kørsel Status: {message}")

    def process_incoming_line(self, line):
        if line.startswith(TAG_CSV):
            if self.is_running_test:
                csv_data_part = line[len(TAG_CSV):].strip()
                try:
                    parts = csv_data_part.split(',')
                    if len(parts) == NUM_EXPECTED_CSV_COLUMNS:
                        time_ms_esp = float(parts[0])
                        pitch = float(parts[1])
                        pid_out = float(parts[2])
                        p_term = float(parts[3])
                        i_term = float(parts[4])
                        d_term = float(parts[5])

                        # Tjek for loop tid overskridelse
                        if self.first_data_line_in_run_received: # Vi har en forrige_timestamp
                            if self.previous_csv_timestamp_ms is not None: # Sikrer at den er sat
                                interval_ms = time_ms_esp - self.previous_csv_timestamp_ms
                                if interval_ms > LOOP_TIME_WARNING_THRESHOLD_MS:
                                    print(f"ROBOT WARNING: Loop tid på ESP32 > {TARGET_LOOP_TIME_MS:.0f}ms! Interval: {interval_ms:.1f} ms (ESP Timestamp: {time_ms_esp:.0f})")
                            self.previous_csv_timestamp_ms = time_ms_esp # Opdater for næste tjek
                        else: # Første CSV linje i denne kørsel
                            self.run_start_time_esp_ms = time_ms_esp
                            self.previous_csv_timestamp_ms = time_ms_esp # Initialiser for næste tjek
                            self.first_data_line_in_run_received = True
                        
                        current_time_s_relative = (time_ms_esp - self.run_start_time_esp_ms) / 1000.0

                        self.current_run_data.append((current_time_s_relative, pitch, pid_out, p_term, i_term, d_term))
                        self.plot_time_data.append(current_time_s_relative)
                        self.plot_pitch_data.append(pitch)

                        if abs(pitch) > FALLEN_PITCH_THRESHOLD_DEG:
                            self.stop_current_run("Væltet (Pitch Threshold)")
                    else:
                        print(f"ROBOT WARNING (Malformed CSV - wrong column count): {line}")
                except ValueError:
                    print(f"ROBOT WARNING (ValueError in CSV data part): {line}")
        
        elif line.startswith(TAG_FALLEN): 
            if self.is_running_test:
                self.stop_current_run("Væltet (Signal fra Robot)")
        elif line.startswith(TAG_INFO): 
            info_message = line[len(TAG_INFO):].strip()
            print(f"ROBOT INFO: {info_message}")
        elif line.startswith(TAG_ERROR): 
            error_message = line[len(TAG_ERROR):].strip()
            print(f"ROBOT ERROR: {error_message}")
            messagebox.showerror("Robot Fejl", error_message)
            self.update_serial_status_gui(f"Robot Fejl: {error_message[:50]}...")
        else:
            print(f"ROBOT UNTAGGED: {line}")

    def apply_pid_parameters(self):
        if self.is_running_test:
            messagebox.showerror("Fejl", "Stop testkørsel før PID parametre ændres.")
            return
        kp = self.kp_var.get()
        ki = self.ki_var.get()
        kd = self.kd_var.get()
        new_pid_params = {"kp": kp, "ki": ki, "kd": kd}
        if new_pid_params != self.previous_pid_params_for_session:
            self.update_run_status_gui(f"Anvender PID: KP={kp}, KI={ki}, KD={kd}")
            if self.serial_thread.running:
                self.serial_thread.send_command(f"kp={kp}")
                self.serial_thread.send_command(f"ki={ki}")
                self.serial_thread.send_command(f"kd={kd}")
            self.current_pid_params = new_pid_params
            if self.current_session_runs_scores:
                 self.log_session_summary(self.previous_pid_params_for_session) 
            self.current_session_runs_scores = []
            self.previous_pid_params_for_session = self.current_pid_params.copy()
            self.update_session_display()
            self.update_run_status_gui("PID parametre anvendt. Klar til ny session.")
        else:
            self.update_run_status_gui("PID parametre uændrede.")

    def send_manual_command(self):
        cmd_to_send = self.manual_cmd_var.get().strip()
        if not cmd_to_send:
            messagebox.showinfo("Info", "Intet at sende. Indtast en kommando.")
            return
        if self.is_running_test and cmd_to_send.lower() not in ["csv_off", "stop"]:
             if not messagebox.askyesno("Advarsel", f"En testkørsel er aktiv. Sikker på du vil sende '{cmd_to_send}'?"):
                return
        if self.serial_thread.running:
            self.serial_thread.send_command(cmd_to_send)
            self.manual_cmd_var.set("")
        else:
            messagebox.showerror("Fejl", "Ingen seriel forbindelse til at sende kommando.")

    def save_parameters_on_robot(self):
        if self.is_running_test:
            messagebox.showwarning("Advarsel", "Stop testkørsel før du gemmer på robotten.")
            return
        if messagebox.askyesno("Bekræft Gem", "Gem robottens aktive tuning-parametre til NVS?\n"
                                            "(Sørg for at de ønskede værdier er aktive på robotten)"):
            if self.serial_thread.running and self.serial_thread.serial_port and self.serial_thread.serial_port.is_open:
                self.serial_thread.send_command("save") 
                self.update_run_status_gui("Sendt 'save' kommando til robot.")
            else:
                messagebox.showerror("Fejl", "Ingen seriel forbindelse til 'save' kommando.")

    def toggle_test_run(self):
        if not self.is_running_test:
            gui_pid_params = {"kp": self.kp_var.get(), "ki": self.ki_var.get(), "kd": self.kd_var.get()}
            if gui_pid_params != self.current_pid_params:
                 messagebox.showwarning("Advarsel", "PID i GUI er ikke anvendt. Anvend dem først.")
                 return
            if not self.serial_thread.running or not self.serial_thread.serial_port or not self.serial_thread.serial_port.is_open:
                messagebox.showerror("Fejl", "Ingen seriel forbindelse. Kan ikke starte test.")
                return

            self.is_running_test = True
            self.first_data_line_in_run_received = False # Nulstil for hver kørsel
            self.previous_csv_timestamp_ms = None       # Nulstil for hver kørsel
            self.run_start_time_esp_ms = 0             
            self.start_stop_button.config(text="Stop Testkørsel")
            self.update_run_status_gui("Testkørsel aktiv...")
            self.current_run_data = []
            self.plot_time_data.clear(); self.plot_pitch_data.clear()
            self.line.set_data([], []); self.canvas.draw_idle()

            if self.serial_thread.running:
                self.serial_thread.send_command("csv_on")
        else:
            self.stop_current_run("Manuelt stoppet")

    def stop_current_run(self, reason="Ukendt"):
        if not self.is_running_test: return
        self.is_running_test = False
        if self.serial_thread.running and self.serial_thread.serial_port and self.serial_thread.serial_port.is_open:
             self.serial_thread.send_command("csv_off")
        self.start_stop_button.config(text="Start Testkørsel")
        self.update_run_status_gui(f"Testkørsel stoppet: {reason}")
        if not self.current_run_data:
            self.update_run_status_gui(f"Test stoppet: {reason}. Ingen data modtaget.")
            self.current_score_label.config(text="Nuv. Score: - (Ingen data)")
            self.time_upright_label.config(text="Tid Oprejst: - s")
            return
        score, time_upright, _, _ = self.calculate_run_score()
        self.current_score_label.config(text=f"Nuv. Score: {score:.2f}")
        self.time_upright_label.config(text=f"Tid Oprejst: {time_upright:.2f} s")
        if time_upright >= MIN_VALID_RUN_DURATION_S:
            self.current_session_runs_scores.append(score)
        else:
             self.update_run_status_gui(f"Test stoppet: {reason}. Kørsel for kort ({time_upright:.2f}s).")
        self.update_session_display()

    def calculate_run_score(self):
        if not self.current_run_data: return 0, 0, float('inf'), 0
        run_timestamps_relative, pitches, _, _, _, _ = zip(*self.current_run_data)
        pitches = np.array(pitches)
        run_timestamps_relative = np.array(run_timestamps_relative)
        if run_timestamps_relative.size == 0: return 0,0,float('inf'),0
        total_run_duration_recorded = run_timestamps_relative[-1] if run_timestamps_relative.size > 0 else 0
        time_upright = 0
        is_upright_sample = np.abs(pitches) < BALANCED_PITCH_THRESHOLD_DEG
        if run_timestamps_relative.size > 1:
            dt_intervals = np.diff(run_timestamps_relative)
            time_upright = np.sum(dt_intervals[is_upright_sample[:-1]])
            if is_upright_sample[-1]: time_upright += np.mean(dt_intervals) if dt_intervals.size > 0 else 0.015
        elif run_timestamps_relative.size == 1 and is_upright_sample[0]: time_upright = 0.015 
        upright_pitches = pitches[is_upright_sample]
        avg_abs_pitch_dev = np.mean(np.abs(upright_pitches)) if upright_pitches.size > 0 else float('inf')
        stability_metric = np.std(upright_pitches) if upright_pitches.size > 1 else float('inf')
        score = time_upright * 20
        if avg_abs_pitch_dev != float('inf'): score -= avg_abs_pitch_dev * 30
        if stability_metric != float('inf'): score -= stability_metric * 40
        if total_run_duration_recorded > 0.1:
            upright_ratio = time_upright / total_run_duration_recorded
            score += upright_ratio * 50 
        if time_upright < MIN_VALID_RUN_DURATION_S: score -= 100 
        score = max(-1000, min(1000, score))
        return score, time_upright, avg_abs_pitch_dev, stability_metric

    def update_session_display(self):
        num_runs = len(self.current_session_runs_scores)
        self.session_runs_label.config(text=f"Kørsler i session: {num_runs}")
        avg_score_text = np.mean(self.current_session_runs_scores) if num_runs > 0 else "-"
        self.session_score_label.config(text=f"Session Gns. Score: {avg_score_text if isinstance(avg_score_text, str) else f'{avg_score_text:.2f}'}")
    
    def log_session_summary(self, params_for_this_session):
        if self.current_session_runs_scores:
            avg_score = np.mean(self.current_session_runs_scores)
            print(f"\n--- Session Opsummering ---")
            print(f"Parametre (PID): KP={params_for_this_session['kp']}, KI={params_for_this_session['ki']}, KD={params_for_this_session['kd']}")
            print(f"Antal kørsler: {len(self.current_session_runs_scores)}")
            print(f"Gennemsnitlig Score: {avg_score:.2f}")
            print(f"Scores: {[f'{s:.2f}' for s in self.current_session_runs_scores]}")
            print(f"---------------------------\n")

    def periodic_gui_update(self):
        if self.plot_time_data:
            max_plot_points = int(PLOT_HISTORY_SECONDS / 0.015) 
            while len(self.plot_time_data) > max_plot_points:
                self.plot_time_data.popleft(); self.plot_pitch_data.popleft()
            current_plot_time = list(self.plot_time_data)
            current_plot_pitch = list(self.plot_pitch_data)
            self.line.set_data(current_plot_time, current_plot_pitch)
            if current_plot_time:
                max_time_on_plot = max(PLOT_HISTORY_SECONDS, current_plot_time[-1] if current_plot_time else PLOT_HISTORY_SECONDS)
                min_time_on_plot = current_plot_time[0] if len(self.plot_time_data) >= max_plot_points else 0
                self.ax.set_xlim(min_time_on_plot, max_time_on_plot +1)
            else: self.ax.set_xlim(0, PLOT_HISTORY_SECONDS)
            try: self.canvas.draw_idle()
            except Exception as e: print(f"Fejl under opdatering af plot: {e}")
        self.root.after(100, self.periodic_gui_update)

    def on_closing(self):
        if messagebox.askokcancel("Luk", "Vil du afslutte programmet?"):
            if self.is_running_test: self.stop_current_run("Program lukket")
            if self.current_session_runs_scores:
                 self.log_session_summary(self.current_pid_params) 
            if self.serial_thread.is_alive():
                self.serial_thread.stop()
                self.serial_thread.join(timeout=1)
            self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = RobotPerformanceApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()