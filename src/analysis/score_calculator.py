# analysis/score_calculator.py
"""
Score beregning og analyse af robot performance data
"""

import numpy as np
from scipy import signal
from config.settings import (
    BALANCED_PITCH_THRESHOLD_DEG,
    MIN_VALID_RUN_DURATION_S,
    MAX_OSCILLATION_CUTOFF_DEG,
    MAX_OSCILLATION_AMPLITUDE_RMS,
    SCORE_BASE_TIME_MULTIPLIER,
    SCORE_OSCILLATION_AMPLITUDE_PENALTY,
    SCORE_OSCILLATION_FREQUENCY_PENALTY,
    SCORE_DEGRADATION_PENALTY,
    SCORE_POSITION_RMSE_PENALTY,
    SCORE_SETTLING_TIME_S,
    OSCILLATION_WINDOW_SIZE_S
)


class ScoreCalculator:
    """
    Klasse til beregning af performance scores baseret på robot data
    """
    
    @staticmethod
    def calculate_run_score(run_data):
        """
        Beregn score baseret på vinkel-oscillation OG positionsstabilitet.
        """
        if not run_data:
            return 0, 0, 0, {}
        
        # Udtræk data arrays (antager position er den sidste kolonne)
        run_timestamps_relative = np.array([item[1] for item in run_data])
        pitches = np.array([item[2] for item in run_data])
        positions = np.array([item[-1] for item in run_data])
        
        if run_timestamps_relative.size == 0:
            return 0, 0, 0, {}

        total_duration = run_timestamps_relative[-1]
        start_index = 0
        if run_timestamps_relative[-1] > SCORE_SETTLING_TIME_S:
            # np.argmax finder det FØRSTE index hvor betingelsen er sand
            start_index = np.argmax(run_timestamps_relative >= SCORE_SETTLING_TIME_S)
        
        # Find valid scoring period (før robotten vælter)
        valid_end_idx = ScoreCalculator._find_oscillation_cutoff(pitches)
        
        print(f"ROBOT INFO: Start Index: {start_index}, Valid End Index: {valid_end_idx}, "
              f"Total Duration: {total_duration:.2f}s, "
              f"Run Timestamps: {run_timestamps_relative}, "
              f"Pitches: {pitches}, "
              f"Positions: {positions}\n")

        if valid_end_idx == 0:
            return -1000, 0, total_duration, {'reason': 'immediate_cutoff'}
            
        # Brug kun data fra den valide periode
        valid_timestamps = run_timestamps_relative[:valid_end_idx]
        valid_pitches = pitches[:valid_end_idx]
        valid_positions = positions[:valid_end_idx]
        valid_time = valid_timestamps[-1] if valid_timestamps.size > 0 else 0
        
        if valid_time < MIN_VALID_RUN_DURATION_S:
            return 0, valid_time, total_duration, {'reason': 'too_short'}
        
        # Beregn alle relevante metrikker
        oscillation_metrics = ScoreCalculator._analyze_oscillations(
            valid_timestamps, valid_pitches, valid_positions
        )
        
        # Beregn den samlede score
        score = ScoreCalculator._calculate_oscillation_score(
            valid_time, oscillation_metrics
        )
        
        # Opdateret print for bedre debugging
        print(f"ROBOT INFO: Score: {score:.2f} "
              f"(Valid Tid: {valid_time:.2f}s, "
              f"RMS Amp: {oscillation_metrics.get('amplitude_rms', 0):.3f}°, "
              f"Pos RMSE: {oscillation_metrics.get('position_rmse_m', 0):.4f}m)")
        
        score = max(-1000, min(1000, score))
        
        return score, valid_time, total_duration, oscillation_metrics

    @staticmethod
    def _find_oscillation_cutoff(pitches):
        """Find punkt hvor oscillationer bliver for store"""
        for i, pitch in enumerate(pitches):
            if abs(pitch) > MAX_OSCILLATION_CUTOFF_DEG:
                return i
        return len(pitches)
    
    @staticmethod
    def _analyze_oscillations(timestamps, pitches, positions):
        """Analysér vinkel-oscillation OG positionsafvigelse."""
        if len(timestamps) < 10:
            return {'amplitude_rms': float('inf'), 'avg_frequency': 0, 
                    'degradation_factor': 0, 'position_rmse_m': float('inf')}
        
        # Vinkel-analyse (som før)
        amplitude_rms = np.sqrt(np.mean(pitches**2))
        try:
            dt = np.mean(np.diff(timestamps))
            peaks, _ = signal.find_peaks(np.abs(pitches), height=0.5)
            avg_frequency = 1.0 / np.mean(np.diff(peaks) * dt) if len(peaks) > 1 else 0
        except:
            avg_frequency = 0
        degradation_factor = ScoreCalculator._calculate_degradation(timestamps, pitches)

        # NYT: Positions-analyse
        # RMSE måler den effektive gennemsnitlige afstand fra startpunktet (0)
        position_rmse_m = np.sqrt(np.mean(positions**2)) if len(positions) > 0 else 0
        print(f"SCORE DEBUG: positions: {positions}, positions_rmse_m: {position_rmse_m:.4f} m\n")
        
        return {
            'amplitude_rms': amplitude_rms,
            'avg_frequency': avg_frequency,
            'degradation_factor': degradation_factor,
            'position_rmse_m': position_rmse_m
        }

    @staticmethod
    def _calculate_degradation(timestamps, pitches):
        """Beregn om oscillationer forværres over tid"""
        if len(timestamps) < int(2 * OSCILLATION_WINDOW_SIZE_S / 0.015):  # Mindst 2 vinduer
            return 0
        
        try:
            # Del data i vinduer
            dt = np.mean(np.diff(timestamps)) if len(timestamps) > 1 else 0.015
            window_samples = int(OSCILLATION_WINDOW_SIZE_S / dt)
            
            if window_samples < 10:
                return 0
            
            # Beregn RMS for første og sidste vindue
            start_window = pitches[:window_samples]
            end_window = pitches[-window_samples:]
            
            start_rms = np.sqrt(np.mean(start_window**2))
            end_rms = np.sqrt(np.mean(end_window**2))
            
            # Degradation factor (positiv hvis det bliver værre)
            degradation = (end_rms - start_rms) / max(start_rms, 0.1)
            return max(0, degradation)  # Kun straf hvis det bliver værre
            
        except:
            return 0

    @staticmethod
    def _calculate_oscillation_score(valid_time, oscillation_metrics):
        """Beregn score baseret på vinkel-kvalitet OG positionsstabilitet."""
        score = 1000
        
        # Eksisterende straffe for VINKEL-opførsel
        score -= oscillation_metrics.get('amplitude_rms', 0) * SCORE_OSCILLATION_AMPLITUDE_PENALTY
        if oscillation_metrics.get('avg_frequency', 0) > 1.0:
            score -= (oscillation_metrics.get('avg_frequency', 0) - 1.0) * SCORE_OSCILLATION_FREQUENCY_PENALTY
        score -= oscillation_metrics.get('degradation_factor', 0) * SCORE_DEGRADATION_PENALTY
        
        # NYT: Straf for fysisk POSITIONS-afvigelse (rokken frem og tilbage)
        position_rmse = oscillation_metrics.get('position_rmse_m', 0)
        score -= position_rmse * SCORE_POSITION_RMSE_PENALTY
        
        # Bonusser (uændret)
        if oscillation_metrics.get('amplitude_rms', 0) < 1.0:
            score += (1.0 - oscillation_metrics.get('amplitude_rms', 0)) * 50
        if oscillation_metrics.get('avg_frequency', 0) < 0.5:
            score += (0.5 - oscillation_metrics.get('avg_frequency', 0)) * 30
            
        return score

    @staticmethod
    def calculate_session_stats(session_run_details):
        """
        Beregn statistikker for en hel session
        
        Args:
            session_run_details: Liste af (score, valid_time, total_duration, oscillation_metrics) tuples
                                          
        Returns:
            dict: Session statistikker
        """
        if not session_run_details:
            return {}
            
        num_runs = len(session_run_details)
        scores = [d[0] for d in session_run_details]
        valid_times = [d[1] for d in session_run_details]
        total_durations = [d[2] for d in session_run_details]
        
        # Saml oscillation metrics
        amplitudes = []
        frequencies = []
        degradations = []
        
        for d in session_run_details:
            if len(d) > 3 and isinstance(d[3], dict):
                metrics = d[3]
                if 'amplitude_rms' in metrics and metrics['amplitude_rms'] != float('inf'):
                    amplitudes.append(metrics['amplitude_rms'])
                if 'avg_frequency' in metrics:
                    frequencies.append(metrics['avg_frequency'])
                if 'degradation_factor' in metrics:
                    degradations.append(metrics['degradation_factor'])
        
        return {
            'num_runs': num_runs,
            'avg_score': np.mean(scores),
            'max_score': np.max(scores),
            'min_score': np.min(scores),
            'avg_valid_time': np.mean(valid_times),
            'avg_total_duration': np.mean(total_durations),
            'avg_amplitude_rms': np.mean(amplitudes) if amplitudes else float('inf'),
            'avg_frequency': np.mean(frequencies) if frequencies else 0,
            'avg_degradation': np.mean(degradations) if degradations else 0
        }