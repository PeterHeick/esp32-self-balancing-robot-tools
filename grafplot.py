# filePlot.py
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, CheckButtons # Importer CheckButtons
import argparse
import numpy as np

# --- Constants ---
MIN_WIN_SIZE_DISPLAY = 2 # Minimum antal punkter at vise ved maksimal zoom-ind
DEFAULT_INITIAL_POINTS = 100 # Standard antal punkter at vise initielt, hvis data er lang nok

# --- Argument parsing (uændret) ---
parser = argparse.ArgumentParser(description="Plot data fra en fil.")
parser.add_argument('--file', type=str, required=True, help="Sti til datafilen.")
args = parser.parse_args()

# --- load_data funktion (MODIFICERET for robust fejlhåndtering og overspringning af linjer) ---
def load_data(file_path):
    valid_data = []
    header = ""
    first_line_is_header_candidate = True # Antag at første linje KAN være header
    expected_num_columns = None # Bruges til at tjekke konsistens i antal kolonner

    with open(file_path, 'r') as file:
        for line_number, line_content in enumerate(file, 1): # Start linjenummer fra 1
            line_stripped = line_content.strip()

            if not line_stripped: # Skip helt tomme linjer
                print(f"Info: Springer tom linje {line_number} over.")
                continue

            # Håndter potentiel header
            if first_line_is_header_candidate:
                try:
                    # Prøv at parse som data for at se, om det er en "kun-tal" header
                    potential_data_header = list(map(float, line_stripped.split(',')))
                    # Hvis det lykkes, OG vi ikke har en forventet kolonneantal endnu,
                    # eller hvis det matcher, så er det nok en datalinje.
                    if expected_num_columns is None:
                        expected_num_columns = len(potential_data_header)
                        valid_data.append(potential_data_header)
                        print(f"Info: Linje {line_number} behandlet som første datalinje (lignede ikke tekst-header). Antal kolonner sat til: {expected_num_columns}")
                        first_line_is_header_candidate = False # Ikke længere en header kandidat
                        continue
                    elif len(potential_data_header) == expected_num_columns:
                        valid_data.append(potential_data_header)
                        print(f"Info: Linje {line_number} behandlet som datalinje (lignede ikke tekst-header).")
                        first_line_is_header_candidate = False
                        continue
                    else:
                        # Lignede data, men passede ikke med forventet kolonneantal (hvis sat)
                        # Dette scenarie er mindre sandsynligt her, men vi anser det som header.
                        header = line_stripped
                        print(f"Info: Linje {line_number} ('{line_stripped}') antaget som header (lignede tal, men kolonneantal passede ikke tidligere data).")
                        first_line_is_header_candidate = False
                        continue

                except ValueError:
                    # Kunne ikke konverteres til float, så det er en rigtig header
                    header = line_stripped
                    print(f"Info: Linje {line_number} ('{line_stripped}') antaget som header.")
                    first_line_is_header_candidate = False
                    continue # Gå til næste linje

            # Behandl datalinjer
            try:
                data_line = list(map(float, line_stripped.split(',')))

                if expected_num_columns is None:
                    # Dette er den første gyldige datalinje efter en eventuel header
                    expected_num_columns = len(data_line)
                    valid_data.append(data_line)
                    print(f"Info: Første gyldige datalinje ({line_number}) fundet. Antal kolonner sat til: {expected_num_columns}")
                elif len(data_line) == expected_num_columns:
                    valid_data.append(data_line)
                else:
                    # Uensartet antal kolonner
                    print(f"Advarsel: Springer datalinje {line_number} over. Forventede {expected_num_columns} kolonner, "
                          f"men fik {len(data_line)}. Linjens indhold: '{line_stripped}'")
                    continue # Spring denne linje over

            except ValueError:
                # Kunne ikke konvertere data til tal
                print(f"Advarsel: Springer datalinje {line_number} over. Kunne ikke konvertere til tal. "
                      f"Linjens indhold: '{line_stripped}'")
                continue # Spring denne linje over

    if not valid_data and not header:
        # Dette er nu mindre sandsynligt at være en fejl, hvis filen kun indeholdt ugyldige linjer.
        # Vi returnerer tomme arrays, og resten af koden skal håndtere det.
        print("Advarsel: Filen er tom eller indeholdt ingen gyldige data eller header efter filtrering.")
    elif not valid_data and header:
        print(f"Info: Filen indeholder kun en header ('{header}') og ingen gyldige datalinjer efter filtrering.")
        # Returner tomt np.array([]) og headeren
    elif valid_data and not header:
        print("Info: Indlæst data uden en separat header-linje.")
    elif valid_data and header:
        print(f"Info: Indlæst data med header: '{header}'.")


    # Konverter til NumPy array til sidst, hvis der er data
    if valid_data:
        return np.array(valid_data), header
    else:
        return np.array([]), header # Returner altid et (potentielt tomt) numpy array

# --- Indlæs data med den opdaterede funktion ---
try:
    data, header = load_data(args.file)
    # data.size check er stadig relevant. Hvis data er tom efter load_data,
    # betyder det, at ingen gyldige datalinjer blev fundet.
    if data.size == 0 and not header:
        print("Fejl: Ingen gyldige data eller header kunne indlæses fra filen. Grafen kan ikke vises.")
        # Overvej om du vil exit(1) her, eller lade programmet forsøge at vise en helt tom graf.
        # For nu lader vi den fortsætte og vise en tom graf med en besked.
    elif data.size == 0 and header:
        print("Info: Kun header indlæst. Viser en tom graf med titlen fra headeren.")
    elif data.size > 0:
        print(f"Info: Indlæst {data.shape[0]} datalinjer med {data.shape[1]} kolonner hver.")

except Exception as e:
    # Denne generelle exception fanger nu kun uventede fejl i load_data eller fil I/O.
    print(f"Uventet fejl under indlæsning af datafil: {str(e)}")
    exit(1)

# --- Definer initial vinduesstørrelse ---
if data.size > 0:
    num_data_points = len(data) # Antal rækker
    initial_win_size = min(DEFAULT_INITIAL_POINTS, num_data_points)
    initial_win_size = max(1, initial_win_size) # Sikrer mindst 1, hvis der er data
else:
    num_data_points = 0
    initial_win_size = DEFAULT_INITIAL_POINTS # Vil blive clippet korrekt senere

# --- Initialiser plot ---
fig, ax = plt.subplots(figsize=(18, 12))
plt.subplots_adjust(left=0.25, bottom=0.30, right=0.80, top=0.9)
ax.set_title(header if header else "PID Controller Data")

# Få kolonne-navne
if header:
    column_names = [name.strip() for name in header.split(',')]
elif data.size > 0:
    column_names = [f'Data {i+1}' for i in range(data.shape[1])]
else:
    column_names = []

# --- Tegn initial graf ---
lines = []
line_labels = []
# plot_win_size for initial plot er den faktiske win_size
plot_win_size_init = min(initial_win_size, num_data_points) if num_data_points > 0 else 0

if num_data_points > 0:
    # Sikrer at vi har nok kolonnenavne, selvom headeren var mangelfuld
    if len(column_names) < data.shape[1]:
        for i in range(len(column_names), data.shape[1]):
            column_names.append(f'Data {i+1}')

    for i, col_data in enumerate(data.T):
        label = column_names[i] # Vi har sikret os, at column_names er lang nok
        line, = ax.plot(np.arange(plot_win_size_init), col_data[:plot_win_size_init], label=label)
        lines.append(line)
        line_labels.append(label)
else:
    ax.text(0.5, 0.5, "Ingen gyldige data at vise", ha='center', va='center', transform=ax.transAxes)


# --- Tilføj hjælpelinjer (uændret) ---
ax.axhline(y=0, color='black', linestyle='-')
ax.axhline(y=6, color='black', linestyle='--')
ax.axhline(y=-6, color='black', linestyle='--')

# --- Sæt aksegrænser ---
if data.size > 0:
    y_min_data = np.min(data) if data.size > 0 else -1 # Undgå fejl på tomt array
    y_max_data = np.max(data) if data.size > 0 else 1
    y_range = y_max_data - y_min_data
    y_margin = y_range * 0.1 if y_range > 0 else 0.1
else:
    y_min_data = -7 # Sæt default y-grænser så hjælpelinjer (-6, 0, 6) er synlige
    y_max_data = 7
    y_margin = 0.2 # Dette vil blive brugt, men sliderne vil bruge y_min_data/y_max_data

ax.set_xlim(0, plot_win_size_init if plot_win_size_init > 0 else 1)
ax.set_ylim(y_min_data - y_margin, y_max_data + y_margin)


# --- Funktion til at beregne nuværende vinduesstørrelse baseret på zoom ---
def get_current_win_size():
    if num_data_points == 0:
        return 0

    if 'slider_zoom' not in globals(): # Før slider er defineret
        base_ws = min(initial_win_size, num_data_points)
        return max(1, base_ws) if num_data_points > 0 else 0 # Sikrer mindst 1 hvis data

    zoom_factor = slider_zoom.val
    # Brug DEFAULT_INITIAL_POINTS som base for zoom, clippet af faktiske datapunkter
    base_for_zoom = min(DEFAULT_INITIAL_POINTS, num_data_points)
    base_for_zoom = max(1, base_for_zoom) # Sikrer mindst 1 hvis data

    current_ws = int(round(base_for_zoom / zoom_factor))

    min_allowed = min(MIN_WIN_SIZE_DISPLAY, num_data_points)
    min_allowed = max(1, min_allowed) # Skal mindst være 1 hvis data

    current_ws = np.clip(current_ws, min_allowed, num_data_points)
    return int(current_ws)

# --- Opdater funktion til grafen ---
def update(val):
    if num_data_points == 0:
        # Sørg for at y-akselimitterne respekteres selvom der ikke er data
        ax.set_ylim(slider_y_min.val, slider_y_max.val)
        fig.canvas.draw_idle()
        return

    current_win_size = get_current_win_size()
    if current_win_size == 0: # Skulle ikke ske hvis num_data_points > 0
        ax.set_xlim(0,1)
        for line in lines: line.set_data([],[])
        ax.set_ylim(slider_y_min.val, slider_y_max.val) # Opdater også her
        fig.canvas.draw_idle()
        return

    start_pos = int(slider_x.val)
    max_start_pos = max(0, num_data_points - current_win_size)
    start_pos = max(0, min(start_pos, max_start_pos))

    end_pos = start_pos + current_win_size
    end_pos = min(end_pos, num_data_points)

    for line, d_col in zip(lines, data.T):
        if line.get_visible():
            x_display_data = np.arange(start_pos, end_pos)
            y_display_data = d_col[start_pos:end_pos]
            line.set_data(x_display_data, y_display_data)
        else:
            line.set_data([],[])

    ax.set_xlim(start_pos, end_pos if end_pos > start_pos else start_pos + 1)
    ax.set_ylim(slider_y_min.val, slider_y_max.val)
    fig.canvas.draw_idle()

# --- Ny funktion til at håndtere zoom slider ændringer ---
def update_zoom(val):
    if num_data_points == 0: return

    current_win_size = get_current_win_size()
    new_max_x = max(0, num_data_points - current_win_size)

    # Sikrer at valmax ikke er mindre end 0 eller valmin
    slider_x.valmax = new_max_x if new_max_x > 0 else 1 # Slider kan ikke have valmax <= valmin (0)
    if new_max_x == 0 and slider_x.valmin == 0: # Specialtilfælde for meget få punkter
        slider_x.valmax = 1 # Sørg for at der er et interval

    if slider_x.val > new_max_x:
        slider_x.set_val(new_max_x)
    else:
        update(slider_x.val)

# --- Sliders ---
slider_ax_left = 0.25
slider_ax_width = 0.55
slider_ax_height = 0.03
slider_spacing = 0.01

# X-akse slider
ax_slider_x_ypos = 0.15 + slider_ax_height + slider_spacing
ax_slider_x = plt.axes([slider_ax_left, ax_slider_x_ypos, slider_ax_width, slider_ax_height], facecolor='lightgoldenrodyellow')
# Initial slider_x_max_val beregnes med den _faktiske_ initial_win_size
_initial_current_win_size = get_current_win_size() # Den faktiske initiale størrelse
slider_x_max_val = max(0, num_data_points - _initial_current_win_size)
slider_x = Slider(ax_slider_x, 'Position', 0, slider_x_max_val if slider_x_max_val > 0 else 1, valinit=0, valstep=1)


# Zoom slider
ax_slider_zoom_ypos = ax_slider_x_ypos - slider_ax_height - slider_spacing
ax_slider_zoom = plt.axes([slider_ax_left, ax_slider_zoom_ypos, slider_ax_width, slider_ax_height], facecolor='lightgoldenrodyellow')
slider_zoom = Slider(ax_slider_zoom, 'Zoom Faktor', 0.2, 5.0, valinit=1.0, valstep=0.05)

# Y-akse min slider
ax_slider_y_min_ypos = ax_slider_zoom_ypos - slider_ax_height - slider_spacing
ax_slider_y_min = plt.axes([slider_ax_left, ax_slider_y_min_ypos, slider_ax_width, slider_ax_height], facecolor='lightgoldenrodyellow')
# Brug de y_min_data/y_max_data som er sat tidligere, også for tom graf
slider_y_min_default_min = y_min_data - y_margin
slider_y_min_default_max = y_max_data + y_margin
# Sørg for at sliderens min/max ikke er det samme, hvis data er fladt eller tomt
if slider_y_min_default_min == slider_y_min_default_max:
    slider_y_min_default_min -= 0.5
    slider_y_min_default_max += 0.5
slider_y_min = Slider(ax_slider_y_min, 'Y-Min',
                      slider_y_min_default_min,
                      slider_y_min_default_max,
                      valinit=y_min_data - y_margin)

# Y-akse max slider
ax_slider_y_max_ypos = ax_slider_y_min_ypos - slider_ax_height - slider_spacing
ax_slider_y_max = plt.axes([slider_ax_left, ax_slider_y_max_ypos, slider_ax_width, slider_ax_height], facecolor='lightgoldenrodyellow')
slider_y_max_default_min = y_min_data - y_margin
slider_y_max_default_max = y_max_data + y_margin
if slider_y_max_default_min == slider_y_max_default_max:
    slider_y_max_default_min -= 0.5
    slider_y_max_default_max += 0.5
slider_y_max = Slider(ax_slider_y_max, 'Y-Max',
                      slider_y_max_default_min,
                      slider_y_max_default_max,
                      valinit=y_max_data + y_margin)


# Forbind sliders til update funktioner
slider_x.on_changed(update)
slider_y_min.on_changed(update)
slider_y_max.on_changed(update)
slider_zoom.on_changed(update_zoom)

# --- CheckButtons for at skjule/vise grafer ---
if lines:
    rax_left = 0.03
    rax_bottom = 0.35 # Justeret for at passe bedre med 4 sliders
    rax_width = 0.15
    rax_height = 0.55 # Justeret højde
    # Sørg for at rax_bottom + rax_height < top_of_sliders (ca. ax_slider_x_ypos + slider_ax_height)
    # ax_slider_x_ypos = 0.15 + 0.03 + 0.01 = 0.19. Top er 0.19 + 0.03 = 0.22
    # Vi skal justere plt.subplots_adjust(bottom=...) og slider placeringer omhyggeligt
    # Current plt.subplots_adjust(left=0.25, bottom=0.30, right=0.80, top=0.9)
    # Checkbuttons kan være fra bottom=0.35 op til 0.90.
    # Sliders er under 0.25.
    # Dette layout burde være ok.

    rax = plt.axes([rax_left, rax_bottom, rax_width, rax_height], facecolor='lightgoldenrodyellow')
    initial_visibility = [True] * len(lines)
    # Sørg for at line_labels er unikke for CheckButtons, hvis der er duplikerede kolonnenavne
    unique_line_labels_for_check = []
    temp_label_counts = {}
    for lbl in line_labels:
        if lbl in temp_label_counts:
            temp_label_counts[lbl] += 1
            unique_line_labels_for_check.append(f"{lbl} ({temp_label_counts[lbl]})")
        else:
            temp_label_counts[lbl] = 1
            unique_line_labels_for_check.append(lbl)

    check = CheckButtons(rax, unique_line_labels_for_check, initial_visibility)
    # lines_dict skal bruge de originale labels for at finde de korrekte linjer
    lines_dict_for_check = {unique_lbl: lines[i] for i, unique_lbl in enumerate(unique_line_labels_for_check)}


    def toggle_visibility(label_from_check): # label_from_check er den potentielt unikke label
        line = lines_dict_for_check[label_from_check]
        line.set_visible(not line.get_visible())
        # Hvis linjen bliver synlig, og den ikke havde data (f.eks. var zoomet helt ud)
        # skal vi måske kalde update for at sikre data er sat.
        # Men update() kaldes generelt fra sliders, så det er måske ikke nødvendigt her.
        # Et simpelt redraw er nok.
        update(slider_x.val) # Kald update for at sikre data genindlæses korrekt
        #fig.canvas.draw_idle() # update kalder allerede draw_idle

    check.on_clicked(toggle_visibility)
else:
    pass


# --- Vis plottet ---
plt.show()