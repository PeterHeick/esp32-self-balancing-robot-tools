#ifndef SPEED_CALIBRATION_H
#define SPEED_CALIBRATION_H

#include <Arduino.h>
#include "config.h" // For diverse konstanter (MAX_RPM, DEADZONE etc.)
#include "Motor.h"  // For at kunne kalibrere mod en motor
#include <Stream.h> // For Serial output

// Sørg for at MAX_RPM er defineret i config.h!
#ifndef MAX_RPM
#error "MAX_RPM skal være defineret i config.h!"
#endif

class SpeedCalibration {
public:
    // Størrelsen på de interne tabeller (indekseret 0-255)
    static const int INDEX_TABLE_SIZE = 256;
    // Størrelsen på den endelige opslagstabel (indekseret 0-MAX_RPM)
    static const int RPM_LOOKUP_TABLE_SIZE = MAX_RPM + 1;

    // Konstruktør - tager et ID for motoren (f.eks. 1 eller 2)
    SpeedCalibration(int motorId);

    /**
     * @brief Udfører hele kalibreringsprocessen for en given motor.
     * Genererer først Index->PWM tabellen, konverterer den så til RPM->PWM.
     * @param motor Reference til den Motor, der skal kalibreres.
     * @param serialPort Reference til Serial port for output under kalibrering.
     * @return true hvis kalibrering og konvertering lykkedes, false ellers.
     */
    bool runCalibration(Motor &motor, Stream &serialPort);

    /**
     * @brief Henter den nødvendige PWM for en given mål-RPM.
     * Slår op i den færdigkonverterede _rpmToPwmLookup tabel.
     * @param targetRpm Den ønskede RPM (heltal).
     * @return Den beregnede PWM værdi (0-255).
     */
    int getPwmForRpm(int targetRpm) const;

    /**
     * @brief Printer den endelige RPM->PWM opslagstabel til seriel port.
     * Designet til at være nem at kopiere til hardkodning.
     * @param serialPort Reference til den serielle port.
     */
    void printRpmToPwmTable(Stream &serialPort) const;

    // --- Valgfri NVS funktionalitet ---
    // bool loadRpmPwmTableFromNvs();
    // bool saveRpmPwmTableToNvs();

private:
    int _motorId;

    // Interne tabeller brugt under kalibrering/konvertering
    int _targetRpmProfile[INDEX_TABLE_SIZE];     // Index (0-255) -> Ønsket Ideal RPM
    int _correctedPwmForIndex[INDEX_TABLE_SIZE]; // Index (0-255) -> Fundet PWM

    // Den endelige opslagstabel
    int _rpmToPwmLookup[RPM_LOOKUP_TABLE_SIZE]; // Index (0-MAX_RPM) -> Fundet PWM

    // Poin­tere til motor/serial under kalibrering
    Motor* _motorPtr = nullptr;
    Stream* _serialPtr = nullptr;

    /**
     * @brief Initialiserer de interne tabeller (_targetRpmProfile, _corrected...).
     */
    void _initializeTables();

    /**
     * @brief Privat hjælpefunktion til at læse en stabil RPM under kalibrering.
     */
    int _readStableRpm(int stabilityTolerance = 2, unsigned long checkIntervalMs = 150, unsigned long maxWaitMs = 2500);

    /**
     * @brief Genererer den midlertidige Index->PWM tabel (_correctedPwmForIndex)
     * ved eksperimentelt at køre motoren mod _targetRpmProfile.
     */
    void _generateIndexToPwmTable();

    /**
     * @brief Konverterer den midlertidige _correctedPwmForIndex tabel
     * til den endelige _rpmToPwmLookup tabel og fylder huller.
     */
    void _convertIndexTableToRpmTable();
};

#endif // SPEED_CALIBRATION_H