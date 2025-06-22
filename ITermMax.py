import os
import pandas as pd

def find_iterm_stats():
    results = {}
    for file in os.listdir('.'):
        if file.endswith('.csv'):
            try:
                df = pd.read_csv(file)
                if 'ITerm' in df.columns:
                    max_val = df['ITerm'].max()
                    min_val = df['ITerm'].min()
                    spread = max_val - min_val
                    results[file] = (max_val, min_val, spread)
            except Exception:
                continue
    return results

result = find_iterm_stats()
for file, (max_val, min_val, spread) in result.items():
    print(f"{file}: Max ITerm = {max_val}, Min ITerm = {min_val}, Spredning = {spread}")

