# plot_3d_results.py (Version 5.3 med rettet opdaterings-rækkefølge)
"""
Script til at visualisere resultaterne fra auto-tuneren som en 3D-overflade,
med en interaktiv slider til at vælge KI-værdi.
"""

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider
import argparse
import os
import numpy as np
from scipy.interpolate import griddata
from scipy.spatial import QhullError

def create_plot(file_path, min_score=None):
    """Hovedfunktion til at oprette og håndtere det interaktive plot."""
    try:
        if not os.path.exists(file_path):
            print(f"Fejl: Filen '{file_path}' blev ikke fundet.")
            return

        full_df = pd.read_csv(file_path)
        if min_score is not None:
            full_df = full_df[full_df['Score'] >= min_score]
            print(f"Viser kun resultater med score >= {min_score}")
        
        available_ki_values = sorted(full_df['KI'].unique())

        if full_df.empty or not available_ki_values:
            print("Ingen gyldige data fundet at visualisere med de nuværende filtre.")
            return
    except Exception as e:
        print(f"Fejl ved indlæsning af data: {e}")
        return

    # --- Plot Setup ---
    fig = plt.figure(figsize=(12, 10))
    ax = fig.add_subplot(111, projection='3d', position=[0.1, 0.2, 0.8, 0.7])
    ax_slider = fig.add_axes([0.2, 0.05, 0.65, 0.03])
    
    cbar = None 

    ki_slider = Slider(
        ax=ax_slider, label='Vælg KI Værdi', valmin=0,
        valmax=len(available_ki_values) - 1, valinit=0, valstep=1,
    )

    def format_ki_label(val):
        return f'{available_ki_values[int(val)]:.2f}'

    ki_slider.valtext.set_text(format_ki_label(ki_slider.val))

    def update(slider_val):
        """Kaldes når slideren ændres. Gentegner 3D-plottet."""
        nonlocal cbar

        selected_ki = available_ki_values[int(slider_val)]
        ki_slider.valtext.set_text(format_ki_label(slider_val))
        df_slice = full_df[np.isclose(full_df['KI'], selected_ki)]
        
        # =============================================================
        #   RETTELSE: Rækkefølgen er nu korrekt
        # =============================================================
        # 1. Fjern den gamle colorbar FØRST, hvis den eksisterer
        if cbar:
            cbar.remove()
        
        # 2. Ryd derefter hoved-aksen
        ax.cla()
        # =============================================================
        
        can_create_surface = False
        if not df_slice.empty and len(df_slice) >= 4:
            try:
                kp_vals, kd_vals, scores = df_slice['KP'], df_slice['KD'], df_slice['Score']
                grid_kp, grid_kd = np.mgrid[kp_vals.min():kp_vals.max():100j, kd_vals.min():kd_vals.max():100j]
                grid_score = griddata((kp_vals, kd_vals), scores, (grid_kp, grid_kd), method='linear')
                
                if np.any(np.isfinite(grid_score)):
                    surf = ax.plot_surface(grid_kp, grid_kd, grid_score, cmap='viridis', edgecolor='none', alpha=0.8)
                    cbar = fig.colorbar(surf, ax=ax, shrink=0.5, aspect=10, label='Score')
                    ax.scatter(kp_vals, kd_vals, scores, c='red', s=20, marker='o', depthshade=True, label='Målte Punkter')
                    ax.legend(loc='upper left')
                    can_create_surface = True

            except (QhullError, RuntimeError):
                can_create_surface = False
        
        if not can_create_surface and not df_slice.empty:
            scatter = ax.scatter(df_slice['KP'], df_slice['KD'], df_slice['Score'], c=df_slice['Score'], cmap='viridis', marker='o', s=50)
            cbar = fig.colorbar(scatter, ax=ax, shrink=0.5, aspect=10, label='Score')

        # Sæt titler og labels igen
        title = f'3D Performance Landskab (for KI ≈ {selected_ki:.2f})'
        if args.min_score is not None: title += f'\n(Scores >= {args.min_score})'
        ax.set_title(title, fontsize=16, pad=20)
        ax.set_xlabel('KP Værdi', fontweight='bold'); ax.set_ylabel('KD Værdi', fontweight='bold'); ax.set_zlabel('Opnået Score', fontweight='bold')
        
        if not full_df.empty:
            z_min = full_df['Score'].min() if args.min_score is None else args.min_score
            z_max = full_df['Score'].max()
            if z_max > z_min:
                ax.set_zlim(z_min, z_max)

        fig.canvas.draw_idle()

    ki_slider.on_changed(update)
    update(0)
    plt.show()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Visualiser auto-tuner resultater i 3D.")
    parser.add_argument('--file', type=str, default='autotune_results.csv', help='Sti til CSV-fil.')
    parser.add_argument('--min-score', type=float, default=None, help='Minimum score, der skal vises.')
    args = parser.parse_args()
    
    create_plot(args.file, args.min_score)