# analysis/score_calculator.py
"""
Score beregning og analyse af robot performance data
"""

import numpy as np
from config.settings import (
    BALANCED_PITCH_THRESHOLD_DEG,
    MIN_VALID_RUN_DURATION_S,
    SCORE_TIME_UPRIGHT_MULTIPLIER,
    SCORE_PITCH_DEV_MULTIPLIER,
    SCORE_STABILITY_MULTIPLIER,
    SCORE_UPRIGHT_RATIO_MULTIPLIER,
    SCORE_MIN_RUN_DURATION_MULTIPLIER
)


class ScoreCalculator:
    """
    Klasse til beregning af performance scores baseret på robot data
    """
    
    @staticmethod
    def calculate_run_score(run_data):
        """
        Beregn score for en enkelt testkørsel
        
        Args:
            run_data: Liste af tuples (time_ms_esp, relative_time_s, pitch, pid_out, p, i, d)
            
        Returns:
            tuple: (score, time_upright, total_duration, avg_abs_pitch_dev, stability_metric)
        """
        if not run_data:
            return 0, 0, 0, float('inf'), float('inf')
        
        # Udtræk data arrays
        esp_timestamps = np.array([item[0] for item in run_data])
        run_timestamps_relative = np.array([item[1] for item in run_data])
        pitches = np.array([item[2] for item in run_data])
        
        if run_timestamps_relative.size == 0:
            return 0, 0, 0, float('inf'), float('inf')

        # Beregn total varighed
        total_duration = run_timestamps_relative[-1] if run_timestamps_relative.size > 0 else 0
        
        # Beregn tid oprejst
        time_upright = ScoreCalculator._calculate_time_upright(
            run_timestamps_relative, pitches
        )
        
        # Beregn pitch statistikker
        avg_abs_pitch_dev, stability_metric = ScoreCalculator._calculate_pitch_stats(pitches)
        
        # Beregn samlet score
        score = ScoreCalculator._calculate_total_score(
            time_upright, total_duration, avg_abs_pitch_dev, stability_metric
        )
        
        print(f"ROBOT INFO: Kørsel score: {score:.2f} "
              f"(Tid Oprejst: {time_upright:.2f}s, "
              f"Total Varighed: {total_duration:.2f}s, "
              f"Gns. Pitch Dev: {avg_abs_pitch_dev:.3f} deg, "
              f"Stabilitet: {stability_metric:.3f} deg)")
        
        # Begræns score til rimelig interval
        score = max(-1000, min(1000, score))
        
        return score, time_upright, total_duration, avg_abs_pitch_dev, stability_metric

    @staticmethod
    def _calculate_time_upright(timestamps, pitches):
        """Beregn total tid robotten var oprejst"""
        time_upright = 0
        is_upright_sample = np.abs(pitches) < BALANCED_PITCH_THRESHOLD_DEG
        
        if timestamps.size > 1:
            dt_intervals = np.diff(timestamps)
            time_upright = np.sum(dt_intervals[is_upright_sample[:-1]])
            
            # Tilføj sidste interval hvis robot stadig er oprejst
            if is_upright_sample[-1]:
                time_upright += np.mean(dt_intervals) if dt_intervals.size > 0 else 0.015
                
        elif timestamps.size == 1 and is_upright_sample[0]:
            time_upright = 0.015  # Antag kort sample interval
            
        return time_upright

    @staticmethod
    def _calculate_pitch_stats(pitches):
        """Beregn pitch statistikker for oprejste perioder"""
        is_upright_sample = np.abs(pitches) < BALANCED_PITCH_THRESHOLD_DEG
        upright_pitches = pitches[is_upright_sample]
        
        # Gennemsnitlig absolut pitch deviation
        avg_abs_pitch_dev = (
            np.mean(np.abs(upright_pitches)) 
            if upright_pitches.size > 0 
            else float('inf')
        )
        
        # Stabilitet (standardafvigelse)
        stability_metric = (
            np.std(upright_pitches) 
            if upright_pitches.size > 1 
            else float('inf')
        )
        
        return avg_abs_pitch_dev, stability_metric

    @staticmethod
    def _calculate_total_score(time_upright, total_duration, avg_abs_pitch_dev, stability_metric):
        """Beregn samlet score baseret på forskellige faktorer"""
        score = time_upright * SCORE_TIME_UPRIGHT_MULTIPLIER
        
        # Træk fra for pitch deviation
        if avg_abs_pitch_dev != float('inf'):
            score -= avg_abs_pitch_dev * SCORE_PITCH_DEV_MULTIPLIER
            
        # Træk fra for ustabilitet
        if stability_metric != float('inf'):
            score -= stability_metric * SCORE_STABILITY_MULTIPLIER
            
        # Bonus for høj oprejst ratio
        if total_duration > 0.1:
            upright_ratio = time_upright / total_duration
            score += upright_ratio * SCORE_UPRIGHT_RATIO_MULTIPLIER
        else:
            score -= SCORE_UPRIGHT_RATIO_MULTIPLIER
            
        # Straf for for kort kørsel
        if time_upright < MIN_VALID_RUN_DURATION_S:
            score -= SCORE_MIN_RUN_DURATION_MULTIPLIER
            
        return score

    @staticmethod
    def calculate_session_stats(session_run_details):
        """
        Beregn statistikker for en hel session
        
        Args:
            session_run_details: Liste af (score, time_upright, total_duration, 
                                          avg_abs_pitch_dev, stability_metric) tuples
                                          
        Returns:
            dict: Session statistikker
        """
        if not session_run_details:
            return {}
            
        num_runs = len(session_run_details)
        scores = [d[0] for d in session_run_details]
        times_upright = [d[1] for d in session_run_details]
        total_durations = [d[2] for d in session_run_details]
        
        # Filtrer ugyldige værdier
        valid_pitch_devs = [d[3] for d in session_run_details if d[3] != float('inf')]
        valid_stability_metrics = [d[4] for d in session_run_details if d[4] != float('inf')]
        
        return {
            'num_runs': num_runs,
            'avg_score': np.mean(scores),
            'max_score': np.max(scores),
            'min_score': np.min(scores),
            'avg_time_upright': np.mean(times_upright),
            'avg_total_duration': np.mean(total_durations),
            'avg_pitch_dev': np.mean(valid_pitch_devs) if valid_pitch_devs else float('inf'),
            'avg_stability_metric': np.mean(valid_stability_metrics) if valid_stability_metrics else float('inf')
        }