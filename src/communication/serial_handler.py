# communication/serial_handler.py
"""
Serial kommunikation med ESP32 robot
"""

import serial
import threading
import time
import re


class SerialThread(threading.Thread):
    """
    Thread til håndtering af serial kommunikation med robotten
    """
    
    def __init__(self, port, baudrate, data_callback, status_callback):
        super().__init__(daemon=True)
        self.port_name = port
        self.baudrate = baudrate
        self.data_callback = data_callback
        self.status_callback = status_callback
        self.serial_port = None
        self.running = False
        self._stop_event = threading.Event()
        
        # PID læsning functionality
        self.pid_response_callback = None
        self.waiting_for_pid_response = False
        self.pid_response_timeout = None

    def connect(self):
        """Opret forbindelse til serial port"""
        try:
            self.serial_port = serial.Serial(self.port_name, self.baudrate, timeout=1)
            self.running = True
            self.status_callback(f"Forbundet til {self.port_name}")
            return True
        except serial.SerialException as e:
            self.status_callback(f"Fejl ved forbindelse: {e}")
            self.running = False
            return False

    def run(self):
        """Hovedløkke for serial læsning"""
        if not self.serial_port or not self.serial_port.is_open:
            if not self.connect():
                self.status_callback("Initiel forbindelse fejlede. Tråd afslutter.")
                return
                
        while not self._stop_event.is_set():
            if self.serial_port and self.serial_port.is_open:
                try:
                    line = self.serial_port.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        # Check for PID response først
                        if self.waiting_for_pid_response:
                            self._handle_potential_pid_response(line)
                        
                        # Derefter normal data callback
                        self.data_callback(line)
                        
                except serial.SerialException:
                    self.status_callback("Seriel forbindelse tabt. Prøver at genoprette...")
                    self.close_connection()
                    time.sleep(2)
                    if not self._stop_event.is_set() and not self.connect():
                        self.status_callback("Genopretning fejlede. Vent venligst.")
                        time.sleep(3)
                except Exception as e:
                    if not self._stop_event.is_set():
                        self.status_callback(f"Ukendt seriel læsefejl: {e}")
                        time.sleep(0.1)
            else:
                if not self._stop_event.is_set():
                    self.status_callback("Port ikke åben. Forsøger at genoprette...")
                    time.sleep(2)
                    if not self._stop_event.is_set() and not self.connect():
                        self.status_callback("Genopretning fejlede. Vent venligst.")
                        time.sleep(3)
            
            # Check for PID response timeout
            if self.waiting_for_pid_response and time.time() > self.pid_response_timeout:
                self.waiting_for_pid_response = False
                if self.pid_response_callback:
                    self.pid_response_callback(None, "Timeout - robot svarede ikke")
                    self.pid_response_callback = None
        
        self.close_connection()

    def request_pid_parameters(self, callback):
        """Anmod om PID parametre fra robot"""
        if not self.is_connected():
            callback(None, "Ikke forbundet til robot")
            return False
        
        self.pid_response_callback = callback
        self.waiting_for_pid_response = True
        self.pid_response_timeout = time.time() + 5.0  # 5 sekunder timeout
        
        # Send print kommando
        success = self.send_command("print")
        if not success:
            self.waiting_for_pid_response = False
            self.pid_response_callback = None
            callback(None, "Kunne ikke sende print kommando")
            return False
        
        return True

    def _handle_potential_pid_response(self, line):
        """Håndter potentielt PID response fra robot"""
        # Check for både "KP=" og "KP:" formater
        if ("KP=" in line or "KP:" in line) and ("KI=" in line or "KI:" in line) and ("KD=" in line or "KD:" in line):
            try:
                pid_params = self._parse_pid_response(line)
                if pid_params:
                    self.waiting_for_pid_response = False
                    if self.pid_response_callback:
                        # Kald callback i main thread for at undgå thread problemer
                        callback = self.pid_response_callback
                        self.pid_response_callback = None
                        # Brug status_callback til at dispatche til main thread
                        self.status_callback(f"PID_RESPONSE:{pid_params['kp']},{pid_params['ki']},{pid_params['kd']}")
                    return True
            except Exception as e:
                print(f"Fejl ved parsing af PID response: {e}")
        
        return False

    def _parse_pid_response(self, line):
        """Parse PID værdier fra robot response"""
        # Find KP, KI, KD værdier med regex - støt både "=" og ":" format
        kp_match = re.search(r'KP[=:\s]+([0-9.]+)', line, re.IGNORECASE)
        ki_match = re.search(r'KI[=:\s]+([0-9.]+)', line, re.IGNORECASE)
        kd_match = re.search(r'KD[=:\s]+([0-9.]+)', line, re.IGNORECASE)
        
        if kp_match and ki_match and kd_match:
            try:
                parsed_params = {
                    "kp": float(kp_match.group(1)),
                    "ki": float(ki_match.group(1)),
                    "kd": float(kd_match.group(1))
                }
                print(f"SUCCESS: Parsed PID fra robot: KP={parsed_params['kp']}, KI={parsed_params['ki']}, KD={parsed_params['kd']}")
                return parsed_params
            except ValueError as e:
                print(f"Fejl ved konvertering af PID værdier: {e}")
                return None
        
        print(f"DEBUG: Kunne ikke parse PID fra linje: {line}")
        return None

    def send_command(self, command_str):
        """Send kommando til robotten"""
        if self.serial_port and self.serial_port.is_open and self.running:
            try:
                full_command = command_str + '\n'
                self.serial_port.write(full_command.encode('utf-8'))
                print(f"PYTHON SENT: {command_str}")
                self.status_callback(f"Sendt: {command_str}")
                return True
            except serial.SerialException as e:
                self.status_callback(f"Fejl ved send: {e}")
                return False
        else:
            self.status_callback("Kan ikke sende: Ikke forbundet.")
            return False

    def save_parameters_to_robot(self, callback=None):
        """Gem parametre på robot (NVS) - bruges ved program lukning"""
        if not self.is_connected():
            if callback:
                callback(False, "Ikke forbundet til robot")
            return False
        
        success = self.send_command("save")
        if callback:
            if success:
                callback(True, "Save kommando sendt til robot")
            else:
                callback(False, "Kunne ikke sende save kommando")
        
        return success

    def close_connection(self):
        """Luk serial forbindelse"""
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.close()
            except Exception:
                pass
        self.serial_port = None

    def stop(self):
        """Stop serial thread"""
        self._stop_event.set()
        self.running = False

    def is_connected(self):
        """Check om forbindelse er aktiv"""
        return self.serial_port and self.serial_port.is_open and self.running

    def get_connection_status(self):
        """Få detaljeret connection status"""
        if not self.serial_port:
            return "Ikke forbundet"
        
        if not self.serial_port.is_open:
            return "Port lukket"
        
        if not self.running:
            return "Thread stoppet"
        
        return "Forbundet og aktiv"

    def get_port_info(self):
        """Få information om den aktuelle port"""
        if not self.serial_port:
            return None
        
        return {
            'port': self.port_name,
            'baudrate': self.baudrate,
            'is_open': self.serial_port.is_open,
            'timeout': self.serial_port.timeout
        }