#ifndef MOTOR_H
#define MOTOR_H

#include <Arduino.h>
#include "config.h" // For konstanter

#define RPM_TIMEOUT_MS 500 // Timeout for RPM måling
#define MOTOR_MIN_MEASURE_TIME_MS LOOP_TIME_MS // Minimum måletid for RPM måling i ms
#define DEADZONE 21
#define COUNTS_PER_REV 16 // Antal pulser pr. omdrejning
#define GEAR_RATIO 43.7f // Gearforhold motor til hjul motor drejer 43.7 gange hurtigere end hjulene
#define MAX_RPM 238 // Maks RPM for motoren (juster efter behov)

class Motor {
private:
    int _pinIN1;
    int _pinIN2;
    int _pinENA;
    int _hallPinA;
    int _pwmChannel;
    int _pwmMax = 244;
    int _minMeasurementTimeMs; // Fra konstruktør

    volatile unsigned long _pulseCount;
    int _actualRpm = 0;
    unsigned long _lastRpmUpdateTime = 0;
    unsigned long _startMeasurementTime = 0;
    bool _currentDirectionForward = false;
    int _lastValidRpm;

    void updateRPM(); // Privat hjælpefunktion

public:
    Motor(int pinIN1, int pinIN2, int pinENA, int hallPinA, int pwmChannel, int minMeasurementTimeMs = MOTOR_MIN_MEASURE_TIME_MS); // Brug konstant fra config.h

    void begin();
    void setDirection(bool forward);
    void stop();
    void applyRawPwm(int pwm);
    int getActualRpm();
    void IRAM_ATTR incrementPulseCount();
    void resetPulseCount();
};

#endif // MOTOR_H