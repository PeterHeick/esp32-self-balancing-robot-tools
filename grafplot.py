
# filePlot.py
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, CheckButtons
import argparse
import numpy as np
import os
import glob
import configparser

# --- Constants ---
MIN_WIN_SIZE_DISPLAY = 2
DEFAULT_INITIAL_POINTS = 100
MIN_AUTO_Y_SPAN = 1.0
DEFAULT_Y_SPAN_NO_DATA = 14.0
ZOOM_MIN = 0.2
ZOOM_MAX = 5.0
ZOOM_INIT_VAL = (ZOOM_MIN + ZOOM_MAX) / 2.0 # Visuel midte af slideren
DEFAULT_CONFIG_FILENAME = "plot_config.ini"

# --- Config funktioner ---
def read_config(config_path):
    config = configparser.ConfigParser()
    data_source_specifier = None
    default_header_from_config = None

    if not os.path.exists(config_path):
        print(f"Info: Konfigurationsfil '{config_path}' ikke fundet.")
        return None, None

    try:
        config.read(config_path)
        if 'General' in config:
            if config['General'].get('data_file'):
                data_source_specifier = config['General']['data_file'].strip()
                if not data_source_specifier: data_source_specifier = None
            elif config['General'].get('data_directory'):
                data_source_specifier = config['General']['data_directory'].strip()
                if not data_source_specifier: data_source_specifier = None
            
            default_header_from_config = config['General'].get('default_header', fallback=None)
            if default_header_from_config is not None:
                default_header_from_config = default_header_from_config.strip()
                if not default_header_from_config: default_header_from_config = None

        print(f"Info: Konfiguration læst fra '{config_path}':")
        print(f"  - Data kilde: '{data_source_specifier if data_source_specifier else 'Ikke specificeret'}'")
        print(f"  - Standard header: '{default_header_from_config if default_header_from_config else 'Ikke specificeret'}'")
        return data_source_specifier, default_header_from_config
    except configparser.Error as e:
        print(f"Fejl: Kunne ikke læse konfigurationsfil '{config_path}': {e}")
        return None, None

def find_latest_file_in_dir(directory_path, extensions=('.csv', '.txt', '.dat')):
    if not os.path.isdir(directory_path):
        print(f"Fejl: Datakatalog '{directory_path}' er ikke et gyldigt katalog.")
        return None
    
    files = []
    for ext in extensions:
        files.extend(glob.glob(os.path.join(directory_path, f"*{ext}")))
        files.extend(glob.glob(os.path.join(directory_path, f"*{ext.upper()}")))

    if not files:
        print(f"Info: Ingen filer med udvidelserne {extensions} fundet i kataloget '{directory_path}'.")
        return None
    
    try:
        latest_file = max(files, key=os.path.getmtime)
        print(f"Info: Seneste fil fundet i '{directory_path}': '{latest_file}'")
        return latest_file
    except Exception as e:
        print(f"Fejl under søgning efter seneste fil i '{directory_path}': {e}")
        return None

# --- Argument parsing ---
parser = argparse.ArgumentParser(description="Plot data fra en fil.")
parser.add_argument('--file', type=str, required=False, default=None,
                    help="Sti til datafilen (har forrang over konfigurationsfilen).")
parser.add_argument('--config', type=str, default=DEFAULT_CONFIG_FILENAME,
                    help=f"Sti til konfigurationsfil (default: {DEFAULT_CONFIG_FILENAME}).")
args = parser.parse_args()

# --- load_data funktion ---
def load_data(file_path, config_header_str=None):
    valid_data = []
    file_header_candidate = None
    expected_num_columns = None
    found_data_yet = False
    final_header_to_use = ""

    if file_path is None or not os.path.isfile(file_path):
        if file_path: print(f"Fejl: Datafil '{file_path}' ikke fundet eller er ikke en fil.")
        else: print("Fejl: Ingen datafil specificeret til indlæsning.")
        return np.array([]), ""

    print(f"Info: Forsøger at indlæse data fra: '{file_path}'")

    if config_header_str:
        num_cols_from_config = len(config_header_str.split(','))
        if num_cols_from_config > 0:
            expected_num_columns = num_cols_from_config
            print(f"DEBUG load_data: `expected_num_columns` sat til {expected_num_columns} baseret på config_header: '{config_header_str}'")
        else:
             print(f"DEBUG load_data: config_header_str ('{config_header_str}') er tom, `expected_num_columns` ikke sat herfra.")

    with open(file_path, 'r') as file:
        for line_number, line_content in enumerate(file, 1):
            line_stripped = line_content.strip()
            if not line_stripped: continue

            try:
                parts = [p.strip() for p in line_stripped.split(',')]
                data_line_floats = list(map(float, parts))
                found_data_yet = True
                current_line_num_cols = len(data_line_floats)

                if expected_num_columns is None:
                    expected_num_columns = current_line_num_cols
                    valid_data.append(data_line_floats)
                    print(f"DEBUG load_data: Linje {line_number} (første datalinje) sætter expected_num_columns til {expected_num_columns}. Data: {str(data_line_floats[:10])[:100]}...")
                elif current_line_num_cols == expected_num_columns:
                    valid_data.append(data_line_floats)
                else:
                    print(f"Advarsel load_data: Springer datalinje {line_number} over. Forventede {expected_num_columns} kolonner, "
                          f"men fik {current_line_num_cols}. Indhold: '{line_stripped[:100]}...'")
                    continue
            except ValueError:
                if not found_data_yet:
                    file_header_candidate = line_stripped
                else:
                    print(f"Info load_data: Springer tekstlinje {line_number} over (efter data fundet): '{line_stripped[:100]}...'")
                continue

    if config_header_str:
        final_header_to_use = config_header_str
        print(f"Info load_data: Bruger header fra konfigurationen: '{final_header_to_use}'")
    elif file_header_candidate:
        final_header_to_use = file_header_candidate
        print(f"Info load_data: Bruger header fundet i filen: '{final_header_to_use}'")
    else:
        print("Info load_data: Ingen header fra konfig/fil. Standardkolonnenavne bruges hvis data findes.")

    if not valid_data:
        if final_header_to_use:
             print(f"Advarsel load_data: Fil ('{file_path}') har header ('{final_header_to_use}') men ingen gyldige datalinjer.")
        else:
             print(f"Advarsel load_data: Fil ('{file_path}') tom eller ingen gyldige data/header.")
        return np.array([]), final_header_to_use
    
    loaded_np_array = np.array(valid_data)
    print(f"DEBUG load_data: Returnerer data med form: {loaded_np_array.shape}")
    return loaded_np_array, final_header_to_use

# --- Hovedlogik for filvalg og header ---
effective_file_to_load = None
config_data_source_specifier, config_default_header = read_config(args.config)

if args.file:
    effective_file_to_load = args.file
    print(f"Info: Bruger datafil specificeret via kommandolinje: '{effective_file_to_load}'")
elif config_data_source_specifier:
    if os.path.isfile(config_data_source_specifier):
        effective_file_to_load = config_data_source_specifier
        print(f"Info: Bruger datafil specificeret som 'data_file' i config: '{effective_file_to_load}'")
    elif os.path.isdir(config_data_source_specifier):
        print(f"Info: Søger efter seneste fil i katalog specificeret som 'data_directory' i config: '{config_data_source_specifier}'")
        effective_file_to_load = find_latest_file_in_dir(config_data_source_specifier)
        if not effective_file_to_load:
            print(f"Fejl: Kunne ikke finde en passende datafil i kataloget '{config_data_source_specifier}'.")
    else:
        print(f"Fejl: Kilde ('{config_data_source_specifier}') i config er hverken en gyldig fil eller et katalog.")
else:
    print("Fejl: Ingen datafil specificeret via kommandolinje eller i konfigurationsfilen.")
    print(f"       Brug --file <filnavn> eller konfigurer 'data_file'/'data_directory' i '{args.config}'")
    exit(1)

# --- Indlæs data ---
try:
    data, header_string_from_load = load_data(effective_file_to_load, config_default_header)
except Exception as e:
    print(f"Uventet fejl under den overordnede indlæsning af data fra '{effective_file_to_load}': {str(e)}")
    data, header_string_from_load = np.array([]), ""

print(f"DEBUG Main: data.shape efter load_data kald: {data.shape}")
print(f"DEBUG Main: header_string_from_load: '{header_string_from_load}'")

# --- Definer initial vinduesstørrelse ---
if data.size > 0:
    num_data_points = data.shape[0]
    initial_win_size = min(DEFAULT_INITIAL_POINTS, num_data_points)
    initial_win_size = max(1, initial_win_size)
else:
    num_data_points = 0
    initial_win_size = DEFAULT_INITIAL_POINTS

# --- Initialiser plot ---
fig, ax = plt.subplots(figsize=(18, 12))
plt.subplots_adjust(left=0.25, bottom=0.18, right=0.80, top=0.9)
ax.set_title(header_string_from_load if header_string_from_load else "Data Plot")

if header_string_from_load:
    column_names = [name.strip() for name in header_string_from_load.split(',')]
elif data.size > 0:
    column_names = [f'Data {i+1}' for i in range(data.shape[1])]
else:
    column_names = []

print(f"DEBUG Main: Initial column_names (fra header/data): {column_names}")

# --- Tegn initial graf ---
lines = []
line_labels = []
plot_win_size_init = min(initial_win_size, num_data_points) if num_data_points > 0 else 0

if num_data_points > 0:
    if len(column_names) < data.shape[1]:
        print(f"Advarsel Main: Header har {len(column_names)} navne, men data har {data.shape[1]} kolonner. Udfylder manglende navne.")
        for i in range(len(column_names), data.shape[1]):
            column_names.append(f'Data {i+1}')
    elif len(column_names) > data.shape[1]:
        print(f"Advarsel Main: Header har {len(column_names)} navne, men data har kun {data.shape[1]} kolonner. Ekstra headernavne ignoreres.")
        column_names = column_names[:data.shape[1]]

    print(f"DEBUG Main: Endelige column_names for plotning: {column_names}")
    print(f"DEBUG Main: Antal kolonner at plotte (data.shape[1]): {data.shape[1]}")

    for i, col_data in enumerate(data.T):
        if i < len(column_names):
            label = column_names[i]
            line, = ax.plot(np.arange(plot_win_size_init), col_data[:plot_win_size_init], label=label)
            lines.append(line)
            line_labels.append(label)
            print(f"DEBUG Main: Plottet linje {i+1} med label: '{label}'")
        else:
            print(f"Advarsel Main: Forsøgte at plotte kolonne {i+1}, men mangler column_name.")
else:
    ax.text(0.5, 0.5, "Ingen gyldige data at vise", ha='center', va='center', transform=ax.transAxes)

ax.axhline(y=0, color='black', linestyle='-')
ax.axhline(y=6, color='black', linestyle='--')
ax.axhline(y=-6, color='black', linestyle='--')

y_min_overall = np.nanmin(data) if data.size > 0 and np.any(np.isfinite(data)) else -DEFAULT_Y_SPAN_NO_DATA / 2
y_max_overall = np.nanmax(data) if data.size > 0 and np.any(np.isfinite(data)) else DEFAULT_Y_SPAN_NO_DATA / 2
y_has_finite_data_overall = np.any(np.isfinite(data)) if data.size > 0 else False

ax.set_xlim(0, plot_win_size_init if plot_win_size_init > 0 else 1)
initial_y_range_overall = y_max_overall - y_min_overall if y_has_finite_data_overall and y_max_overall > y_min_overall else DEFAULT_Y_SPAN_NO_DATA
initial_y_margin = initial_y_range_overall * 0.1 if initial_y_range_overall > 0 else MIN_AUTO_Y_SPAN / 2
if y_min_overall == y_max_overall and y_has_finite_data_overall:
    ax.set_ylim(y_min_overall - MIN_AUTO_Y_SPAN / 2, y_max_overall + MIN_AUTO_Y_SPAN / 2)
else:
    ax.set_ylim(y_min_overall - initial_y_margin, y_max_overall + initial_y_margin)

def get_current_win_size():
    if num_data_points == 0: return 0
    if 'slider_zoom' not in globals():
        base_ws = min(initial_win_size, num_data_points)
        return max(1, base_ws) if num_data_points > 0 else 0
    zoom_factor = slider_zoom.val
    base_for_zoom = min(DEFAULT_INITIAL_POINTS, num_data_points)
    base_for_zoom = max(1, base_for_zoom)
    current_ws = int(round(base_for_zoom / zoom_factor))
    min_allowed = min(MIN_WIN_SIZE_DISPLAY, num_data_points)
    min_allowed = max(1, min_allowed)
    current_ws = np.clip(current_ws, min_allowed, num_data_points)
    return int(current_ws)

def update(val):
    if num_data_points == 0:
        ax.set_xlim(0, 1)
        ax.set_ylim(-DEFAULT_Y_SPAN_NO_DATA / 2, DEFAULT_Y_SPAN_NO_DATA / 2)
        for line in lines: line.set_data([],[])
        fig.canvas.draw_idle()
        return

    current_win_size = get_current_win_size()
    if current_win_size == 0:
        ax.set_xlim(0, 1)
        ax.set_ylim(-DEFAULT_Y_SPAN_NO_DATA / 2, DEFAULT_Y_SPAN_NO_DATA / 2)
        for line in lines: line.set_data([],[])
        fig.canvas.draw_idle()
        return

    start_pos = int(slider_x.val)
    max_start_pos = max(0, num_data_points - current_win_size)
    start_pos = max(0, min(start_pos, max_start_pos))
    end_pos = start_pos + current_win_size
    end_pos = min(end_pos, num_data_points)

    current_view_min_y = np.inf
    current_view_max_y = -np.inf
    found_visible_finite_data_in_view = False

    for line_idx, (line_obj, d_col) in enumerate(zip(lines, data.T)):
        if start_pos >= end_pos :
            y_segment = np.array([])
        else:
            y_segment = d_col[start_pos:end_pos]
        x_plot_data = np.arange(start_pos, start_pos + len(y_segment))

        if line_obj.get_visible():
            line_obj.set_data(x_plot_data, y_segment)
            if y_segment.size > 0 and np.any(np.isfinite(y_segment)):
                seg_min = np.nanmin(y_segment)
                seg_max = np.nanmax(y_segment)
                if np.isfinite(seg_min):
                    current_view_min_y = min(current_view_min_y, seg_min)
                    found_visible_finite_data_in_view = True
                if np.isfinite(seg_max):
                    current_view_max_y = max(current_view_max_y, seg_max)
                    found_visible_finite_data_in_view = True
        else:
            line_obj.set_data([], [])

    ax.set_xlim(start_pos, end_pos if end_pos > start_pos else start_pos + 1)

    if found_visible_finite_data_in_view:
        if current_view_min_y == current_view_max_y:
            new_y_min_plot = current_view_min_y - MIN_AUTO_Y_SPAN / 2.0
            new_y_max_plot = current_view_max_y + MIN_AUTO_Y_SPAN / 2.0
        else:
            y_data_range_view = current_view_max_y - current_view_min_y
            margin = y_data_range_view * 0.05
            absolute_min_margin_component = MIN_AUTO_Y_SPAN * 0.05
            final_margin = max(margin, absolute_min_margin_component)
            final_margin = max(final_margin, 1e-5)
            new_y_min_plot = current_view_min_y - final_margin
            new_y_max_plot = current_view_max_y + final_margin
        current_plot_span = new_y_max_plot - new_y_min_plot
        if current_plot_span < MIN_AUTO_Y_SPAN:
            center = (new_y_max_plot + new_y_min_plot) / 2.0
            new_y_min_plot = center - MIN_AUTO_Y_SPAN / 2.0
            new_y_max_plot = center + MIN_AUTO_Y_SPAN / 2.0
        ax.set_ylim(new_y_min_plot, new_y_max_plot)
    else:
        if y_has_finite_data_overall:
            y_range_global = y_max_overall - y_min_overall
            if y_range_global <= 0: global_margin = MIN_AUTO_Y_SPAN / 2.0
            else:
                 global_margin = y_range_global * 0.1
                 global_margin = max(global_margin, MIN_AUTO_Y_SPAN / 2.0)
            ax.set_ylim(y_min_overall - global_margin, y_max_overall + global_margin)
        else:
            ax.set_ylim(-DEFAULT_Y_SPAN_NO_DATA / 2, DEFAULT_Y_SPAN_NO_DATA / 2)
    fig.canvas.draw_idle()

def update_zoom(val):
    if num_data_points == 0: return
    current_win_size = get_current_win_size()
    new_max_x = max(0, num_data_points - current_win_size)
    slider_x.valmax = new_max_x if new_max_x > 0 else 1
    if new_max_x == 0 and slider_x.valmin == 0: slider_x.valmax = 1
    if slider_x.val > new_max_x: slider_x.set_val(new_max_x)
    else: update(slider_x.val)

# --- Sliders ---
slider_ax_left, slider_ax_width, slider_ax_height, slider_spacing = 0.25, 0.55, 0.03, 0.01
ax_slider_zoom_ypos = 0.05
ax_slider_x_ypos = ax_slider_zoom_ypos + slider_ax_height + slider_spacing
ax_slider_zoom = plt.axes([slider_ax_left, ax_slider_zoom_ypos, slider_ax_width, slider_ax_height], facecolor='lightgoldenrodyellow')
slider_zoom = Slider(ax_slider_zoom, 'Zoom Faktor', ZOOM_MIN, ZOOM_MAX, valinit=ZOOM_INIT_VAL, valstep=0.05)
ax_slider_x = plt.axes([slider_ax_left, ax_slider_x_ypos, slider_ax_width, slider_ax_height], facecolor='lightgoldenrodyellow')
_initial_current_win_size_for_x_slider = get_current_win_size()
slider_x_max_val = max(0, num_data_points - _initial_current_win_size_for_x_slider)
slider_x = Slider(ax_slider_x, 'Position', 0, slider_x_max_val if slider_x_max_val > 0 else 1, valinit=0, valstep=1)
slider_x.on_changed(update)
slider_zoom.on_changed(update_zoom)

# --- CheckButtons ---
if lines:
    rax_left, rax_bottom, rax_width, rax_height = 0.03, 0.20, 0.15, 0.70
    rax = plt.axes([rax_left, rax_bottom, rax_width, rax_height], facecolor='lightgoldenrodyellow')
    initial_visibility = [True] * len(lines)
    unique_line_labels_for_check = []
    temp_label_counts = {}
    print(f"DEBUG CheckButtons: line_labels før unikke labels: {line_labels}")
    for lbl in line_labels:
        if lbl in temp_label_counts:
            temp_label_counts[lbl] += 1
            unique_line_labels_for_check.append(f"{lbl} ({temp_label_counts[lbl]})")
        else:
            temp_label_counts[lbl] = 1
            unique_line_labels_for_check.append(lbl)
    
    print(f"DEBUG CheckButtons: unique_line_labels_for_check: {unique_line_labels_for_check}")
    print(f"DEBUG CheckButtons: Antal linjer (len(lines)): {len(lines)}, Antal unikke labels: {len(unique_line_labels_for_check)}")

    if len(lines) != len(unique_line_labels_for_check):
        print("KRITISK FEJL CheckButtons: Antal linjer og unikke labels stemmer ikke overens!")

    check = CheckButtons(rax, unique_line_labels_for_check, initial_visibility)
    
    lines_dict_for_check = {}
    for i, unique_lbl in enumerate(unique_line_labels_for_check):
        if i < len(lines):
            lines_dict_for_check[unique_lbl] = lines[i]
        else:
            print(f"FEJL i CheckButton opsætning: Index {i} er udenfor 'lines' array (længde {len(lines)}) for label '{unique_lbl}'")

    print(f"DEBUG CheckButtons: lines_dict_for_check oprettet med {len(lines_dict_for_check)} elementer. Nøgler: {list(lines_dict_for_check.keys())}")

    def toggle_visibility(label_from_check):
        print(f"--- toggle_visibility START for label: '{label_from_check}' ---")
        print(f"DEBUG toggle_visibility: Kendte labels i lines_dict_for_check: {list(lines_dict_for_check.keys())}")
        
        if label_from_check not in lines_dict_for_check:
            print(f"FEJL toggle_visibility: Label '{label_from_check}' IKKE fundet i lines_dict_for_check!")
            for known_label in lines_dict_for_check.keys():
                if label_from_check.lower() == known_label.lower():
                    print(f"  INFO: Der er en case-forskel: modtaget '{label_from_check}', kendt '{known_label}'")
                if label_from_check.strip() == known_label.strip():
                     print(f"  INFO: Der er en whitespace-forskel: modtaget '{label_from_check}', kendt '{known_label}'")
            print(f"--- toggle_visibility SLUT for label: '{label_from_check}' (FEJL) ---")
            return
            
        line = lines_dict_for_check[label_from_check]
        print(f"DEBUG toggle_visibility: Fundet linje-objekt for '{label_from_check}': {line}")
        
        current_visibility = line.get_visible()
        print(f"DEBUG toggle_visibility: Nuværende synlighed for '{label_from_check}': {current_visibility}")
        
        line.set_visible(not current_visibility)
        new_visibility = line.get_visible()
        print(f"DEBUG toggle_visibility: Ny synlighed for '{label_from_check}': {new_visibility}")
        
        if current_visibility == new_visibility:
            print(f"ADVARSEL toggle_visibility: Synlighed for '{label_from_check}' ændrede sig IKKE! Undersøg dette.")

        print(f"DEBUG toggle_visibility: Kalder update(slider_x.val={slider_x.val})...")
        update(slider_x.val)
        print(f"--- toggle_visibility SLUT for label: '{label_from_check}' ---")

    check.on_clicked(toggle_visibility)
else:
    print("Info: Ingen linjer at vise, CheckButtons springes over.")

if num_data_points > 0:
    update(slider_x.valinit)
else:
    update(0)

plt.show()