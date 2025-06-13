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
                # Opdateret header med position control
                header = "Time_ms,Pitch,PitchRate,BalanceCmd,PTerm,ITerm,DTerm,ScaledOutput,Position,PositionSetpoint,PositionError,PositionOutput,PositionCorrection\n"
                if not file_exists or os.path.getsize(filename) == 0:
                    f.write(header)
                
                for data_point_tuple in run_data_list:
                    # Håndter både gamle og nye format
                    if len(data_point_tuple) == 8:
                        # Gammelt format: (time_ms_esp, relative_s, pitch, pitch_rate, pid_out, p, i, d)
                        time_ms_esp, _relative_s, pitch, pitch_rate, balance_cmd, p, i, d = data_point_tuple
                        f.write(
                            f"{time_ms_esp:.0f},"
                            f"{pitch:.3f},"
                            f"{pitch_rate:.3f},"
                            f"{balance_cmd:.3f},"
                            f"{p:.3f},"
                            f"{i:.3f},"
                            f"{d:.3f},"
                            f"0.000,"  # scaled_output placeholder
                            f"0.000,"  # position placeholder
                            f"0.000,"  # position_setpoint placeholder
                            f"0.000,"  # position_error placeholder
                            f"0.000,"  # position_output placeholder
                            f"0.000\n"  # position_correction placeholder
                        )
                    else:
                        # Nyt format: (time_ms_esp, relative_s, pitch, pitch_rate, balance_cmd, p, i, d, scaled_output, position, pos_setpoint, pos_error, pos_output, pos_correction)
                        time_ms_esp, _relative_s, pitch, pitch_rate, balance_cmd, p, i, d, scaled_output, position, pos_setpoint, pos_error, pos_output, pos_correction = data_point_tuple
                        f.write(
                            f"{time_ms_esp:.0f},"
                            f"{pitch:.3f},"
                            f"{pitch_rate:.3f},"
                            f"{balance_cmd:.3f},"
                            f"{p:.3f},"
                            f"{i:.3f},"
                            f"{d:.3f},"
                            f"{scaled_output:.3f},"
                            f"{position:.3f},"
                            f"{pos_setpoint:.3f},"
                            f"{pos_error:.3f},"
                            f"{pos_output:.3f},"
                            f"{pos_correction:.3f}\n"
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
                         "MaxScore,MinScore,AvgValidTime_s,AvgTotalDuration_s,"
                         "AvgAmplitudeRMS_deg,AvgFrequency_Hz,AvgDegradation\n")
                
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
                    f"{session_stats['avg_valid_time']:.2f},"
                    f"{session_stats['avg_total_duration']:.2f},"
                    f"{format_metric(session_stats.get('avg_amplitude_rms', float('inf')))},"
                    f"{session_stats.get('avg_frequency', 0):.2f},"
                    f"{session_stats.get('avg_degradation', 0):.3f}\n"
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