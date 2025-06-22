# src/datalogger/data_logger.py
"""
CSV logging funktionalitet for robot performance data
"""
import os
import datetime
from tkinter import messagebox

class DataLogger:
    """Håndterer logging af data til CSV filer."""
    
    @staticmethod
    def write_detailed_run_data(filename, run_data_list):
        """Log detaljerede kørsel data til CSV."""
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        if not run_data_list: return False

        file_exists = os.path.exists(filename)
        try:
            with open(filename, 'a', newline='') as f:
                header = "Time_ms,Pitch,PitchRate,BalanceCmd,PTerm,ITerm,DTerm,ScaledOutput\n"
                if not file_exists or os.path.getsize(filename) == 0:
                    f.write(header)
                
                for data_point in run_data_list:
                    # Forventer nu et fast tuple-format med 9 elementer
                    # (esp_ms, rel_s, pitch, rate, cmd, p, i, d, scaled)
                    # Vi logger kun de 8 relevante kolonner
                    f.write(
                        f"{data_point[0]:.0f},"
                        f"{data_point[2]:.3f},{data_point[3]:.3f},"
                        f"{data_point[4]:.3f},{data_point[5]:.3f},"
                        f"{data_point[6]:.3f},{data_point[7]:.3f},"
                        f"{data_point[8]:.3f}\n"
                    )
            print(f"ROBOT INFO: Detaljeret kørsel logget til {filename}")
            return True
        except IOError as e:
            messagebox.showerror("Filfejl", f"Kunne ikke skrive til detaljeret logfil:\n{e}")
            return False

    @staticmethod
    def write_session_summary(filename, session_id, pid_params, session_stats):
        """Log session sammendrag til CSV."""
        file_exists = os.path.exists(filename)
        try:
            with open(filename, 'a', newline='') as f:
                header = ("LogTimestamp,SessionID,KP,KI,KD,NumRuns,AvgScore,MaxScore,"
                          "AvgValidTime_s,AvgAmplitudeRMS_deg,AvgFrequency_Hz,AvgDegradation\n")
                if not file_exists or os.path.getsize(filename) == 0:
                    f.write(header)
                
                log_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                def format_metric(value, precision=3):
                    return f"{value:.{precision}f}" if isinstance(value, (int, float)) and value != float('inf') else "N/A"

                data_row = (
                    f"{log_time},{session_id},"
                    f"{pid_params.get('kp',0):.4f},{pid_params.get('ki',0):.4f},{pid_params.get('kd',0):.4f},"
                    f"{session_stats.get('num_runs',0)},{format_metric(session_stats.get('avg_score',0), 2)},"
                    f"{format_metric(session_stats.get('max_score',0), 2)},{format_metric(session_stats.get('avg_valid_time',0), 2)},"
                    f"{format_metric(session_stats.get('avg_amplitude_rms',0))},"
                    f"{format_metric(session_stats.get('avg_frequency',0), 2)},"
                    f"{format_metric(session_stats.get('avg_degradation',0))}\n"
                )
                f.write(data_row)
            print(f"ROBOT INFO: Session resultat logget til {filename}")
            return True
        except IOError as e:
            messagebox.showerror("Filfejl", f"Kunne ikke skrive til logfil {filename}:\n{e}")
            return False