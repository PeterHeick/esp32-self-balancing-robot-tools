# src/tuning/auto_tuner.py
import numpy as np

class AutoTuner:
    def __init__(self, tune_params):
        self.params = tune_params
        self.jobs = []
        self.current_job_index = 0
        self.total_jobs = 0
        self._generate_jobs()

    def _generate_jobs(self):
        """Laver en liste over alle PID-kombinationer, der skal testes."""
        kp_range = np.arange(self.params['kp_start'], self.params['kp_end'] + self.params['kp_step'], self.params['kp_step'])
        kd_range = np.arange(self.params['kd_start'], self.params['kd_end'] + self.params['kd_step'], self.params['kd_step'])
        ki_range = np.arange(self.params['ki_start'], self.params['ki_end'] + self.params['ki_step'], self.params['ki_step'])
        
        # Tre nested loops for at generere alle kombinationer
        for kp in kp_range:
            for kd in kd_range:
                for ki in ki_range:
                    pid_params = {'kp': kp, 'ki': ki, 'kd': kd}
                    self.jobs.append(pid_params)
        
        self.total_jobs = len(self.jobs)
        print(f"AutoTuner: Genereret {self.total_jobs} test-jobs.")

    def get_next_job(self):
        """Returnerer det næste sæt PID-parametre eller None, hvis der ikke er flere."""
        if self.current_job_index < self.total_jobs:
            job = self.jobs[self.current_job_index]
            self.current_job_index += 1
            return job
        else:
            return None

    def get_progress(self):
        """Returnerer en status-streng, f.eks. "5/125"."""
        return f"{self.current_job_index}/{self.total_jobs}"