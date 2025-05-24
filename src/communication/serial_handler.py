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
        
        # Parameter verification functionality
        self.parameter_verification_active = False
        self.pending_parameters = {}
        self.verification_callback = None
        self.verification_timeout = None
        self.max_retries = 3
        self.current_retry = 0

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
                        
                        # Check for parameter verification
                        if self.parameter_verification_active:
                            self._handle_potential_verification_response(line)
                        
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
            
            # Check for parameter verification timeout
            if self.parameter_verification_active and time.time() > self.verification_timeout:
                self._handle_verification_timeout()
        
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
        # Check for både "KP=" og "KP:" formater samt Init og Power Gain
        has_pid = ("KP=" in line or "KP:" in line) and ("KI=" in line or "KI:" in line) and ("KD=" in line or "KD:" in line)
        
        if has_pid:
            try:
                pid_params = self._parse_pid_response(line)
                if pid_params:
                    self.waiting_for_pid_response = False
                    if self.pid_response_callback:
                        # Brug status_callback til at dispatche til main thread
                        param_str = f"{pid_params['kp']},{pid_params['ki']},{pid_params['kd']}"
                        if 'init_balance' in pid_params:
                            param_str += f",{pid_params['init_balance']}"
                        if 'power_gain' in pid_params:
                            param_str += f",{pid_params['power_gain']}"
                        
                        self.status_callback(f"PID_RESPONSE:{param_str}")
                        self.pid_response_callback = None
                    return True
            except Exception as e:
                print(f"Fejl ved parsing af PID response: {e}")
        
        return False

    def _parse_pid_response(self, line):
        """Parse PID værdier fra robot response - OPDATERET til at finde alle parametre"""
        # Find KP, KI, KD værdier med regex - støt både "=" og ":" format
        kp_match = re.search(r'KP[=:\s]+([0-9.]+)', line, re.IGNORECASE)
        ki_match = re.search(r'KI[=:\s]+([0-9.]+)', line, re.IGNORECASE)
        kd_match = re.search(r'KD[=:\s]+([0-9.]+)', line, re.IGNORECASE)
        
        # Find Init Balance og Power Gain (forskellige mulige navne)
        init_match = re.search(r'(?:Init|InitBal|Initial)[=:\s]+([0-9.-]+)', line, re.IGNORECASE)
        power_match = re.search(r'(?:Pow|Power|Gain)[=:\s]+([0-9.-]+)', line, re.IGNORECASE)
        
        if kp_match and ki_match and kd_match:
            try:
                parsed_params = {
                    "kp": float(kp_match.group(1)),
                    "ki": float(ki_match.group(1)),
                    "kd": float(kd_match.group(1))
                }
                
                # Tilføj Init Balance hvis fundet
                if init_match:
                    parsed_params["init_balance"] = float(init_match.group(1))
                    
                # Tilføj Power Gain hvis fundet
                if power_match:
                    parsed_params["power_gain"] = float(power_match.group(1))
                
                print(f"SUCCESS: Parsed parametre fra robot:")
                print(f"  KP={parsed_params['kp']}, KI={parsed_params['ki']}, KD={parsed_params['kd']}")
                if 'init_balance' in parsed_params:
                    print(f"  Init Balance={parsed_params['init_balance']}")
                if 'power_gain' in parsed_params:
                    print(f"  Power Gain={parsed_params['power_gain']}")
                
                return parsed_params
            except ValueError as e:
                print(f"Fejl ved konvertering af parameter værdier: {e}")
                return None
        
        print(f"DEBUG: Kunne ikke parse parametre fra linje: {line}")
        return None

    def send_parameters_with_verification(self, parameters, callback):
        """Send parametre til robot og verificer at de blev modtaget"""
        if not self.is_connected():
            callback(False, "Ikke forbundet til robot")
            return False
        
        # Gem parametre til verificering
        self.pending_parameters = parameters.copy()
        self.verification_callback = callback
        self.parameter_verification_active = True
        self.verification_timeout = time.time() + 5.0  # 5 sekunder timeout
        self.current_retry = 0
        
        print(f"SENDER PARAMETRE (forsøg {self.current_retry + 1}/{self.max_retries}):")
        for param, value in parameters.items():
            print(f"  {param}={value}")
        
        # Send alle parametre - EN ad gangen med pause
        success = True
        for param, value in parameters.items():
            if param == "kp":
                success &= self.send_command(f"kp={value}")
                time.sleep(0.05)  # Kort pause mellem kommandoer
            elif param == "ki":
                success &= self.send_command(f"ki={value}")
                time.sleep(0.05)
            elif param == "kd":
                success &= self.send_command(f"kd={value}")
                time.sleep(0.05)
            elif param == "init_balance":
                success &= self.send_command(f"init={value}")
                time.sleep(0.05)
            elif param == "gain":
                success &= self.send_command(f"gain={value}")
                time.sleep(0.05)
        
        if not success:
            self.parameter_verification_active = False
            callback(False, "Fejl ved sendning af kommandoer")
            return False
        
        # Send print kommando for at få bekræftelse
        time.sleep(0.5)  # Længere pause før print
        success = self.send_command("print")
        
        if not success:
            self.parameter_verification_active = False
            callback(False, "Fejl ved sendning af print kommando")
            return False
        
        return True

    def _handle_potential_verification_response(self, line):
        """Håndter potentiel verification response"""
        # Leder efter robot response med parametre - MERE FLEKSIBEL MATCHING
        if ("KP:" in line and "KI:" in line and "KD:" in line):
            
            try:
                received_params = self._parse_verification_response(line)
                if received_params:
                    print(f"MODTAGET VERIFICATION RESPONSE:")
                    for param, value in received_params.items():
                        print(f"  {param}={value}")
                    
                    # Sammenlign modtagne parametre med forventede
                    if self._verify_parameters_match(received_params, self.pending_parameters):
                        print("SUCCESS: Parametre bekræftet modtaget af robot!")
                        self.parameter_verification_active = False
                        if self.verification_callback:
                            self.verification_callback(True, "Parametre verificeret")
                            self.verification_callback = None
                        return True
                    else:
                        print("WARNING: Modtagne parametre matcher ikke sendte parametre!")
                        self._handle_verification_mismatch(received_params)
                        return True
            except Exception as e:
                print(f"Fejl ved parsing af verification response: {e}")
        
        return False

    def _parse_verification_response(self, line):
        """Parse verification response fra robot"""
        try:
            # Parse alle parametre fra robot response
            kp_match = re.search(r'KP[=:\s]+([0-9.-]+)', line, re.IGNORECASE)
            ki_match = re.search(r'KI[=:\s]+([0-9.-]+)', line, re.IGNORECASE)
            kd_match = re.search(r'KD[=:\s]+([0-9.-]+)', line, re.IGNORECASE)
            init_match = re.search(r'InitBal[=:\s]+([0-9.-]+)', line, re.IGNORECASE)
            power_match = re.search(r'(?:Pow|Power|Gain)[=:\s]+([0-9.-]+)', line, re.IGNORECASE)
            
            if kp_match and ki_match and kd_match:
                params = {
                    "kp": float(kp_match.group(1)),
                    "ki": float(ki_match.group(1)),
                    "kd": float(kd_match.group(1))
                }
                
                if init_match:
                    params["init_balance"] = float(init_match.group(1))
                if power_match:
                    params["gain"] = float(power_match.group(1))
                
                return params
        except ValueError as e:
            print(f"Fejl ved parsing af verification værdier: {e}")
        
        return None

    def _verify_parameters_match(self, received, expected):
        """Verificer at modtagne parametre matcher forventede"""
        tolerance = 0.01  # Øget tolerance for float sammenligning
        
        print(f"VERIFICERER PARAMETRE:")
        print(f"  Forventet: {expected}")
        print(f"  Modtaget:  {received}")
        
        for param, expected_value in expected.items():
            # Special handling for gain/power_gain mismatch
            if param == "power_gain" and param not in received and "gain" in received:
                received_value = received["gain"]
            elif param == "gain" and param not in received and "power_gain" in received:
                received_value = received["power_gain"]
            elif param not in received:
                print(f"MISMATCH: Parameter {param} ikke modtaget")
                return False
            else:
                received_value = received[param]
            
            diff = abs(received_value - expected_value)
            
            if diff > tolerance:
                print(f"MISMATCH: {param} forventet={expected_value}, modtaget={received_value}, diff={diff}")
                return False
            else:
                print(f"MATCH: {param} OK (diff={diff})")
        
        return True

    def _handle_verification_mismatch(self, received_params):
        """Håndter når parametre ikke matcher"""
        print("PARAMETER MISMATCH - Prøver igen...")
        print("Forventet:", self.pending_parameters)
        print("Modtaget:", received_params)
        
        # Prøv igen hvis vi har flere forsøg tilbage
        if self.current_retry < self.max_retries - 1:
            self.current_retry += 1
            self.verification_timeout = time.time() + 5.0
            
            print(f"RETRY {self.current_retry + 1}/{self.max_retries} - Sender parametre igen...")
            time.sleep(0.5)  # Længere pause
            
            # Send parametre igen - EN ad gangen
            for param, value in self.pending_parameters.items():
                if param == "kp":
                    self.send_command(f"kp={value}")
                    time.sleep(0.05)
                elif param == "ki":
                    self.send_command(f"ki={value}")
                    time.sleep(0.05)
                elif param == "kd":
                    self.send_command(f"kd={value}")
                    time.sleep(0.05)
                elif param == "init_balance":
                    self.send_command(f"init={value}")
                    time.sleep(0.05)
                elif param == "power_gain":
                    self.send_command(f"gain={value}")
                    time.sleep(0.05)
            
            time.sleep(0.2)
            self.send_command("print")
        else:
            # Opgiv efter max forsøg
            self.parameter_verification_active = False
            if self.verification_callback:
                self.verification_callback(False, f"Parametre ikke verificeret efter {self.max_retries} forsøg")
                self.verification_callback = None

    def _handle_verification_timeout(self):
        """Håndter timeout på parameter verification"""
        print(f"TIMEOUT på parameter verification (forsøg {self.current_retry + 1})")
        
        if self.current_retry < self.max_retries - 1:
            self.current_retry += 1
            self.verification_timeout = time.time() + 5.0
            
            print(f"RETRY {self.current_retry + 1}/{self.max_retries} - Prøver igen...")
            
            # Send parametre igen - EN ad gangen
            for param, value in self.pending_parameters.items():
                if param == "kp":
                    self.send_command(f"kp={value}")
                    time.sleep(0.05)
                elif param == "ki":
                    self.send_command(f"ki={value}")
                    time.sleep(0.05)
                elif param == "kd":
                    self.send_command(f"kd={value}")
                    time.sleep(0.05)
                elif param == "init_balance":
                    self.send_command(f"init={value}")
                    time.sleep(0.05)
                elif param == "power_gain":
                    self.send_command(f"gain={value}")
                    time.sleep(0.05)
            
            time.sleep(0.2)
            self.send_command("print")
        else:
            # Opgiv efter max forsøg
            self.parameter_verification_active = False
            if self.verification_callback:
                self.verification_callback(False, f"Timeout efter {self.max_retries} forsøg")
                self.verification_callback = None

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