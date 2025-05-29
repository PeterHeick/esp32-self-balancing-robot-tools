# data/data_logger.py
"""
CSV logging funktionalitet for robot performance data
"""

import os
import datetime
from tkinter import messagebox


class DataLogger:
    """
    Håndterer logging af data til CSV filer
    """
    
    @staticmethod
    def write_detailed_run_data(filename, run_data_list):
        """
        Log detaljerede kørsel data til CSV
        
        Args:
            filename: Filnavn for CSV fil
            run_data_list: Liste af data tuples
        """
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        if not run_data_list:
            print("ROBOT INFO: Ingen detaljerede data at logge for seneste kørsel.")
            return False

        file_exists = os.path.exists(filename)
        try:
            with open(filename, 'a', newline='') as f:
                header = "Pitch,PitchRate,pPIDout,PTerm,ITerm,DTerm\n"
                if not file_exists or os.path.getsize(filename) == 0:
                    f.write(header)
                
                for data_point_tuple in run_data_list:
                    # run_data_list indeholder: (time_ms_esp, relative_s, pitch, pid_out, p, i, d)
                    _time_ms_esp, _relative_s, pitch, pitch_rate, pid_out, p, i, d = data_point_tuple
                    
                    f.write(
                        f"{pitch:.3f},"
                        f"{pitch_rate:.3f},"
                        f"{pid_out:.3f},"
                        f"{p:.3f},"
                        f"{i:.3f},"
                        f"{d:.3f}\n"
                    )
            
            print(f"ROBOT INFO: Detaljeret kørsel logget til {filename}")
            return True
            
        except IOError as e:
            print(f"ROBOT ERROR: Kunne ikke skrive til detaljeret logfil {filename}: {e}")
            messagebox.showerror("Filfejl", f"Kunne ikke skrive til detaljeret logfil:\n{e}")
            return False

    @staticmethod
    def write_session_summary(filename, session_id, pid_params, session_stats):
        """
        Log session sammendrag til CSV
        
        Args:
            filename: Filnavn for session CSV
            session_id: Session ID nummer
            pid_params: Dict med PID parametre
            session_stats: Dict med session statistikker
        """
        file_exists = os.path.exists(filename)
        try:
            with open(filename, 'a', newline='') as f:
                header = ("LogTimestamp,SessionID,KP,KI,KD,NumRuns,AvgScore,"
                         "MaxScore,MinScore,AvgTimeUpright_s,AvgTotalDuration_s,"
                         "AvgPitchDev_deg,AvgStability_deg\n")
                
                if not file_exists or os.path.getsize(filename) == 0:
                    f.write(header)
                
                log_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                def format_metric(value, precision=3):
                    return f"{value:.{precision}f}" if value != float('inf') else "N/A"
                
                data_row = (
                    f"{log_time},"
                    f"{session_id},"
                    f"{pid_params['kp']:.4f},{pid_params['ki']:.4f},{pid_params['kd']:.4f},"
                    f"{session_stats['num_runs']},"
                    f"{session_stats['avg_score']:.2f},"
                    f"{session_stats.get('max_score', 0):.2f},"
                    f"{session_stats.get('min_score', 0):.2f},"
                    f"{session_stats['avg_time_upright']:.2f},"
                    f"{session_stats['avg_total_duration']:.2f},"
                    f"{format_metric(session_stats['avg_pitch_dev'])},"
                    f"{format_metric(session_stats['avg_stability_metric'])}\n"
                )
                f.write(data_row)
            
            print(f"ROBOT INFO: Session resultat logget til {filename}")
            return True
            
        except IOError as e:
            print(f"ROBOT ERROR: Kunne ikke skrive til logfil {filename}: {e}")
            messagebox.showerror("Filfejl", f"Kunne ikke skrive til logfil {filename}:\n{e}")
            return False

    @staticmethod
    def write_run_log_entry(filename, run_number, timestamp, pid_params, run_results):
        """
        Log enkelt kørsel til run log
        
        Args:
            filename: Filnavn for run log
            run_number: Løbenummer for kørslen
            timestamp: Tidsstempel for kørslen
            pid_params: PID parametre brugt
            run_results: Resultat tuple fra kørslen
        """
        score, time_upright, total_duration, avg_abs_pitch_dev, stability_metric = run_results
        
        file_exists = os.path.exists(filename)
        try:
            with open(filename, 'a', newline='') as f:
                header = ("Timestamp,RunNumber,KP,KI,KD,Score,TimeUpright_s,"
                         "TotalDuration_s,AvgPitchDev_deg,Stability_deg\n")
                
                if not file_exists or os.path.getsize(filename) == 0:
                    f.write(header)
                
                log_time = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                
                def format_metric(value, precision=3):
                    return f"{value:.{precision}f}" if value != float('inf') else "N/A"
                
                data_row = (
                    f"{log_time},"
                    f"{run_number},"
                    f"{pid_params['kp']:.4f},{pid_params['ki']:.4f},{pid_params['kd']:.4f},"
                    f"{score:.2f},"
                    f"{time_upright:.2f},"
                    f"{total_duration:.2f},"
                    f"{format_metric(avg_abs_pitch_dev)},"
                    f"{format_metric(stability_metric)}\n"
                )
                f.write(data_row)
            
            return True
            
        except IOError as e:
            print(f"ROBOT ERROR: Kunne ikke skrive run log: {e}")
            return False