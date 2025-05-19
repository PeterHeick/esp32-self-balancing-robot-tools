#ifndef PID_TUNER_H
#define PID_TUNER_H

#include <PID_v1.h> // Inkluder PID biblioteket
#include "Motor.h"  // Inkluder din Motor klasse
#include <Stream.h> // For at kunne bruge Serial som parameter

// Definer et namespace for at holde tingene organiseret
namespace PIDTuner {

/**
 * @brief Interaktiv funktion til at tune en motors hastigheds-PID via seriel port.
 *
 * @param serialPort Reference til den serielle port der skal bruges (f.eks. Serial).
 * @param motor Reference til det Motor objekt der skal styres.
 * @param pid Reference til det PID objekt der skal tunes.
 * @param pidInput Reference til den double variabel der bruges som PID Input (faktisk RPM).
 * @param pidOutput Reference til den double variabel hvor PID Output (PWM) gemmes.
 * @param pidSetpoint Reference til den double variabel der bruges som PID Setpoint (ønsket RPM).
 */
void tuneMotorSpeed(Stream &serialPort, Motor &motor, PID &pid,
                      double &pidInput, double &pidOutput, double &pidSetpoint);

} // namespace PIDTuner

#endif // PID_TUNER_H