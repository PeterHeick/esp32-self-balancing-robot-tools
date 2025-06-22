# plot_3d_results.py (Version 4.0 med Interaktiv KI Slider)
"""
Script til at visualisere resultaterne fra auto-tuneren i et 3D-plot,
med en interaktiv slider til at vælge KI-værdi.
"""

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider
from matplotlib.ticker import MaxNLocator
import argparse
import os
import numpy as np

# Gem den indlæste data globalt, så update-funktionen kan tilgå den
try:
    # Gør scriptet klar til at håndtere forskellige filnavne
    parser = argparse.ArgumentParser(description="Visualiser auto-tuner resultater i 3D.")
    parser.add_argument('--file', type=str, default='autotune_results.csv', help='Sti til CSV-fil.')
    parser.add_argument('--min-score', type=float, default=None, help='Minimum score, der skal vises.')
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"Fejl: Filen '{args.file}' blev ikke fundet.")
        exit()

    full_df = pd.read_csv(args.file)
    if args.min_score is not None:
        full_df = full_df[full_df['Score'] >= args.min_score]
        print(f"Viser kun resultater med score >= {args.min_score}")
    
    # Find de unikke KI værdier, som slideren skal kunne vælge imellem
    available_ki_values = sorted(full_df['KI'].unique())

except (FileNotFoundError, pd.errors.EmptyDataError) as e:
    print(f"Fejl: Kunne ikke indlæse data. {e}")
    exit()

if not available_ki_values:
    print("Ingen gyldige data fundet at visualisere.")
    exit()

# --- Plot Setup ---
fig = plt.figure(figsize=(12, 10))
# Juster hovedplottets position for at gøre plads til slideren i bunden
ax = fig.add_subplot(111, projection='3d', position=[0.1, 0.2, 0.8, 0.7])

# Opret en akse til slideren i bunden af figuren
ax_slider = fig.add_axes([0.2, 0.05, 0.65, 0.03]) # [left, bottom, width, height]

# Opret selve slider-widget'en
# Den vil gå fra 0 til antallet af unikke KI-værdier - 1
ki_slider = Slider(
    ax=ax_slider,
    label='Vælg KI Værdi',
    valmin=0,
    valmax=len(available_ki_values) - 1,
    valinit=0,
    valstep=1, # Sørger for at slideren "snapper" til hele tal
)

def format_ki_label(val):
    """Formaterer teksten ved siden af slideren til at vise den faktiske KI-værdi."""
    # Hent den faktiske KI-værdi, der svarer til sliderens indeks
    ki_value = available_ki_values[int(val)]
    return f'{ki_value:.2f}'

# Opdater sliderens label-format
ki_slider.valtext.set_text(format_ki_label(ki_slider.val))


def update(slider_val):
    """
    Funktion der kaldes, hver gang slideren ændres.
    Den rydder og gentegner 3D-plottet med data for den valgte KI-værdi.
    """
    # Hent den valgte KI-værdi baseret på sliderens heltals-position
    selected_ki = available_ki_values[int(slider_val)]
    
    # Opdater sliderens tekst
    ki_slider.valtext.set_text(format_ki_label(slider_val))
    
    # Vælg den "skive" af data, der matcher den valgte KI
    df_slice = full_df[np.isclose(full_df['KI'], selected_ki)]

    # Ryd det eksisterende plot
    ax.cla()

    # Tegn det nye scatter plot med den filtrerede data
    if not df_slice.empty:
        scatter = ax.scatter(df_slice['KP'], df_slice['KD'], df_slice['Score'], 
                             c=df_slice['Score'], cmap='viridis', marker='o', s=50, alpha=0.8)
    
    # Sæt titler og labels igen (da .cla() fjerner dem)
    title = f'3D Visualisering af PID Performance (for KI ≈ {selected_ki:.2f})'
    if args.min_score is not None: title += f'\n(Scores >= {args.min_score})'
    ax.set_title(title, fontsize=16, pad=20)
    ax.set_xlabel('KP Værdi', fontweight='bold')
    ax.set_ylabel('KD Værdi', fontweight='bold')
    ax.set_zlabel('Opnået Score', fontweight='bold')
    ax.xaxis.set_major_locator(MaxNLocator(nbins=6))
    ax.yaxis.set_major_locator(MaxNLocator(nbins=6))
    
    # Sørg for at Z-aksen har samme grænser, så man kan sammenligne højder
    if not full_df.empty:
        ax.set_zlim(full_df['Score'].min(), full_df['Score'].max())

    # Gentegn lærredet
    fig.canvas.draw_idle()

# Forbind sliderens 'on_changed' event til vores update-funktion
ki_slider.on_changed(update)

# Tegn den indledende graf med den første KI-værdi
update(0)

# Vis det interaktive plot
plt.show()