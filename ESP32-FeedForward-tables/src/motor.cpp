#include "Motor.h"
#include "config.h" // Eller "ESP32.h" - hvor dine konstanter er defineret
#include "ESP32.h"  // For ESP32 fejlmeddelelser
#include <Arduino.h>

// --- Konstruktør ---
Motor::Motor(int pinIN1, int pinIN2, int pinENA, int hallPinA, int pwmChannel, int minMeasurementTimeMs) : _pinIN1(pinIN1),
                                                                                                           _pinIN2(pinIN2),
                                                                                                           _pinENA(pinENA),
                                                                                                           _hallPinA(hallPinA),
                                                                                                           _pwmChannel(pwmChannel),
                                                                                                           _pwmMax(255), // Antager 8-bit opløsning defineret i config.h/ESP32.h
                                                                                                           _minMeasurementTimeMs(minMeasurementTimeMs),
                                                                                                           _pulseCount(0),
                                                                                                           _actualRpm(0),
                                                                                                           _lastRpmUpdateTime(0),
                                                                                                           _startMeasurementTime(0),
                                                                                                           _currentDirectionForward(true)
{
  // Tjek evt. om pin numre er valide her?
}

// --- Initialisering ---
void Motor::begin()
{
  // Motor pin setup
  pinMode(_pinIN1, OUTPUT);
  pinMode(_pinIN2, OUTPUT);

  // Opsæt PWM kanal og tilknyt pin
  // Konstanter hentes fra config.h / ESP32.h
  double frequency = ledcSetup(_pwmChannel, PWM_FREQUENCY, PWM_RESOLUTION);
  if (frequency == 0)
  {
    Serial.printf("[Motor %p] ERROR: ledcSetup failed for Chan %d!\n", this, _pwmChannel);
  }
  ledcAttachPin(_pinENA, _pwmChannel);

  // Hall sensor setup (kun pin A til simpel hastighed)
  pinMode(_hallPinA, INPUT_PULLUP);

  // Start motoren stoppet, men i en kendt retning
  setDirection(true); // Start fremad som standard
  digitalWrite(_pinIN1, HIGH);
  digitalWrite(_pinIN2, LOW);
  applyRawPwm(0);                // Start med PWM = 0
  resetPulseCount();             // Nulstil tæller og starttid
  _lastRpmUpdateTime = millis(); // Sæt en starttid for timeout
}

// --- Styring ---
void Motor::setDirection(bool forward)
{
  // Skift kun pin-tilstande hvis den ønskede retning er ny
  if (forward != _currentDirectionForward)
  {
    digitalWrite(_pinIN1, forward ? HIGH : LOW);
    digitalWrite(_pinIN2, forward ? LOW : HIGH);
    _currentDirectionForward = forward;

    // Overvej en meget kort pause hvis din H-bro kræver det efter retningsskift
    // delayMicroseconds(50); // Normalt ikke nødvendigt
  }
}

void Motor::stop()
{
  // Bremser motoren ved at sætte begge inputs lavt (for mange H-bro drivers)
  // Alternativt: digitalWrite(_pinIN1, LOW); digitalWrite(_pinIN2, LOW);
  // Sæt altid PWM til 0
  applyRawPwm(0);
  // For L298N kan det være bedre bare at sætte PWM til 0 og lade IN1/IN2 stå
}

// Anvender en rå PWM værdi - retning SKAL være sat FØR denne kaldes
void Motor::applyRawPwm(int pwm)
{
  // Serial.printf("[Motor %p] pwmChannel: %d, applyRawPwm: %d\n", this, _pwmChannel, pwm);
  pwm = constrain(pwm, 0, _pwmMax); // Sørg for at PWM er indenfor gyldigt område
  ledcWrite(_pwmChannel, pwm);      // Send PWM signalet
}

// --- Måling ---
int Motor::getActualRpm()
{
  updateRPM();

  // Returner 0 hvis der ikke har været en valid måling i et stykke tid
  // (f.eks. hvis motoren står stille og ingen pulser tælles)
  if (millis() - _lastRpmUpdateTime > RPM_TIMEOUT_MS)
  {
    // _actualRpm = 0;
    // return 0;
    return _lastValidRpm;
  }
  return _actualRpm;
}

// --- Interne Funktioner / ISR Hjælpere ---

// Denne funktion kaldes fra den globale ISR knyttet til _hallPinA
// SKAL være hurtig! Kun simpel optælling.
void IRAM_ATTR Motor::incrementPulseCount()
{
  _pulseCount++;
}

// Nulstiller pulstæller og tidtagning for en ny måleperiode
void Motor::resetPulseCount()
{
  // På ESP32 er direkte tildeling til volatile ofte okay for simple tællere
  // ellers brug atomic operationer eller deaktiver interrupts kortvarigt
  noInterrupts();
  _pulseCount = 0;
  _startMeasurementTime = micros(); // Brug micros for bedre præcision i tid
  interrupts();
}

// Beregner RPM baseret på akkumulerede pulser siden sidste reset
void Motor::updateRPM()
{
  unsigned long currentTimeMicros = micros();
  unsigned long timePassedMicros = currentTimeMicros - _startMeasurementTime;
  unsigned long currentPulseCount = 0;

  // Tjek om minimum måletid er gået
  if (timePassedMicros >= ((unsigned long)_minMeasurementTimeMs * 1000UL))
  { // Sammenlign i mikrosekunder

    // Serial.printf("[updateRPM %p] PulseCount=%lu, timepassed=%lu ms\n",
    // this, _pulseCount, timePassedMicros);
    // Læs og nulstil tælleren atomisk (eller med interrupts slået fra)
    noInterrupts();
    currentPulseCount = _pulseCount;
    _pulseCount = 0;
    _startMeasurementTime = currentTimeMicros;
    interrupts();

    // Beregn pulser per sekund
    // (float) cast er vigtigt for at få decimal-division
    float pulsesPerSecond = (float)currentPulseCount * 1000000.0f / timePassedMicros;

    // Beregn RPM baseret på motoraksel-pulser (COUNTS_PER_REV) og gear (GEAR_RATIO)
    float motorShaftRPM = (pulsesPerSecond * 60.0f) / COUNTS_PER_REV;
    int calculatedRpm = (int)(motorShaftRPM / GEAR_RATIO + 0.5);

    // Serial.printf("[Motor %p] RPM: %d, Pulses: %lu, Time: %lu us\n", this, calculatedRpm, currentPulseCount, timePassedMicros);
    // Gem den beregnede RPM og opdater tidspunkt
    _actualRpm = calculatedRpm;
    _lastRpmUpdateTime = millis(); // Brug millis() til timeout checket

    // Anvend fortegn baseret på kendt retning
    if (!_currentDirectionForward)
    {
      _actualRpm = -_actualRpm;
    }
  }
}