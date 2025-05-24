#!/usr/bin/env python3
# main.py
"""
Robot Performance Analysis System - Entry Point

Dette er hovedindgangen til Robot Performance Analysis systemet.
Systemet analyserer og logger performance data fra en balancerende robot.

Funktionalitet:
- Real-time data visualisering
- PID parameter tuning
- Session-baseret data logging
- Performance score beregning
- Serial kommunikation med ESP32

Brug:
    python main.py

Krav:
    - Python 3.7+
    - Se requirements.txt for pakke afhængigheder
    - ESP32 robot forbundet via USB/serial

Forfatter: Robot Performance Team
Version: 0.9.0
"""

import sys
import os
import tkinter as tk
from tkinter import messagebox

# Tilføj src til Python path hvis nødvendigt
if os.path.exists('src'):
    sys.path.insert(0, 'src')
    sys.path.insert(0, '.')
try:
    from gui.main_window import RobotPerformanceApp
    from config.settings import SERIAL_PORT, BAUD_RATE
except ImportError as e:
    print(f"Import fejl: {e}")
    print("Sørg for at alle nødvendige moduler er tilstede og src/ er i Python path")
    sys.exit(1)


def check_dependencies():
    """
    Kontroller at alle nødvendige pakker er installeret
    """
    required_packages = [
        'tkinter',
        'serial',
        'numpy',
        'matplotlib',
        'scipy'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            if package == 'tkinter':
                import tkinter
            elif package == 'serial':
                import serial
            elif package == 'numpy':
                import numpy
            elif package == 'matplotlib':
                import matplotlib
            elif package == 'scipy':
                import scipy
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("Følgende pakker mangler:")
        for package in missing_packages:
            print(f"  - {package}")
        print("\nInstaller dem med:")
        print("pip install " + " ".join(missing_packages).replace('tkinter', 'tk'))
        return False
    
    return True


def check_serial_port():
    """
    Kontroller at serial port er tilgængelig (hvis muligt)
    """
    try:
        import serial.tools.list_ports
        available_ports = [port.device for port in serial.tools.list_ports.comports()]
        
        if not available_ports:
            print("ADVARSEL: Ingen serial porte fundet")
            return True  # Fortsæt alligevel, da det kan være OS specifikt
        
        if SERIAL_PORT not in available_ports:
            print(f"ADVARSEL: Konfigureret port {SERIAL_PORT} ikke fundet")
            print(f"Tilgængelige porte: {available_ports}")
            return True  # Fortsæt alligevel
        
        return True
        
    except ImportError:
        print("Kan ikke kontrollere serial porte (pyserial mangler?)")
        return True
    except Exception as e:
        print(f"Fejl ved kontrol af serial porte: {e}")
        return True


def setup_error_handling():
    """
    Setup global error handling
    """
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            # Håndter Ctrl+C gracefully
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        error_msg = f"Uventet fejl: {exc_type.__name__}: {exc_value}"
        print(error_msg)
        
        # Vis fejl i messagebox hvis tkinter er tilgængeligt
        try:
            root = tk.Tk()
            root.withdraw()  # Skjul hovedvindue
            messagebox.showerror("Kritisk Fejl", error_msg)
            root.destroy()
        except:
            pass  # Tkinter måske ikke tilgængeligt
    
    sys.excepthook = handle_exception


def create_data_directory():
    """
    Opret data mappe hvis den ikke eksisterer
    """
    if not os.path.exists('data'):
        try:
            os.makedirs('data')
            print("Oprettet data/ mappe")
        except OSError as e:
            print(f"Kunne ikke oprette data/ mappe: {e}")
            return False
    return True


def print_startup_info():
    """
    Print startup information
    """
    print("=" * 60)
    print("Robot Performance Analysis System v0.9.0")
    print("=" * 60)
    print(f"Serial port: {SERIAL_PORT}")
    print(f"Baud rate: {BAUD_RATE}")
    print(f"Python version: {sys.version}")
    print("=" * 60)


def main():
    """
    Hovedfunktion - starter applikationen
    """
    print_startup_info()
    
    # Setup error handling
    setup_error_handling()
    
    # Check dependencies
    if not check_dependencies():
        print("Afslutter på grund af manglende afhængigheder")
        sys.exit(1)
    
    # Check serial port
    check_serial_port()
    
    # Create data directory
    if not create_data_directory():
        print("Advarsel: Kunne ikke oprette data mappe")
    
    try:
        # Opret hovedvindue
        print("Starter GUI...")
        root = tk.Tk()
        
        # Opret applikation
        app = RobotPerformanceApp(root)
        
        # Setup window close handler
        root.protocol("WM_DELETE_WINDOW", app.on_closing)
        
        # Center window on screen
        root.update_idletasks()
        width = root.winfo_width()
        height = root.winfo_height()
        x = (root.winfo_screenwidth() // 2) - (width // 2)
        y = (root.winfo_screenheight() // 2) - (height // 2)
        root.geometry(f'{width}x{height}+{x}+{y}')
        
        print("GUI startet - applikation klar til brug")
        print("Tryk Ctrl+C i terminalen for at afslutte")
        
        # Start GUI event loop
        root.mainloop()
        
    except KeyboardInterrupt:
        print("\nAfslutter applikation (Ctrl+C)")
        sys.exit(0)
    except Exception as e:
        print(f"Fejl ved start af applikation: {e}")
        sys.exit(1)
    
    print("Applikation afsluttet")


if __name__ == "__main__":
    main()