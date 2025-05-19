// Description: Robot configuration file
// Max pitch for balancing robot
#ifndef config_h
#define config_h

#include <Arduino.h>

#define MAXPITCH 5

// PID konstanter
#define BALANCE_KP 50.0
#define BALANCE_KI 220.0
#define BALANCE_KD 0.4

#define SPEED_KP 0.9
#define SPEED_KI 0.2
#define SPEED_KD 0.0

#define INITBALANCE 0

#define DIRECTION_MAX_LENGTH 10

// Lowpass filter definition (fjern det fra de andre filer)
#define LOWPASSFILTER(input, output, alpha) ((alpha * input) + ((1.0 - alpha) * output))
#define ALPHA 0.1

#define LOOP_TIME_MS 50 // Loop tid i ms
#define BALANCE_OUTPUT_TO_RPM_SCALE 0.1 // Skaleringsfaktor for balance output til RPM
#define BALANCE_PID_OUTPUT_LIMIT 100 // Maksimal output fra balance PID (juster efter behov)
#define MAX_TILT_ANGLE_SAFETY 5 // Maksimal hældningsvinkel for sikkerhedstjek (juster efter behov)


#endif