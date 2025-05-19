#ifndef SPEED_PROFILE_H
#define SPEED_PROFILE_H

#include <Arduino.h>
#include "config.h" // For diverse konstanter
#include "Motor.h"  // For at kunne kalibrere mod en motor
#include <Stream.h> // For Serial output

class SpeedProfile {
public:
    static const int TABLE_SIZE = 256; // Størrelse på tabellerne

    // Konstruktør - tager et ID for motoren (f.eks. 1 eller 2)
    SpeedProfile(int motorId);

    /**
     * @brief Genererer den korrigerede PWM tabel ved at køre motoren.
     * Indeholder logikken fra din gamle initMotorCorrections.
     * @param motor Reference til den Motor, der skal kalibreres.
     * @param serialPort Reference til Serial port for output under kalibrering.
     */
    void generateCorrectionTable(Motor &motor, Stream &serialPort);

    /**
     * @brief Henter den korrigerede PWM værdi for et givet hastighedsindeks.
     * @param speedIndex Ønsket hastighedsindeks (0-255).
     * @return Den kalibrerede PWM værdi (0-255) der bør give den ønskede hastighed.
     */
    int getCorrectedPwm(int speedIndex) const; // Gør den const

    /**
     * @brief Printer den genererede korrektionstabel til seriel port.
     * @param serialPort Reference til den serielle port.
     */
    void printCorrectionTable(Stream &serialPort) const; // Gør den const

    // --- Valgfri NVS funktionalitet ---
    /**
     * @brief Forsøger at indlæse korrektionstabellen fra NVS.
     * @return true hvis succes, false hvis fejl eller ingen gemt tabel.
     */
    // bool loadTableFromNvs();

    /**
     * @brief Gemmer den nuværende korrektionstabel til NVS.
     * @return true hvis succes, false hvis fejl.
     */
    // bool saveTableToNvs();


private:
    int _motorId; // ID for motoren (til f.eks. NVS nøgle)

    // Den ØNSKEDE lineære RPM profil (baseret på din indsatte data)
    // Gøres static const for at spare RAM, da den er ens for alle instanser.
    static const int TARGET_RPM_PROFILE[TABLE_SIZE];

    // Den KALIBREREDE tabel: Index = Ønsket hastigheds-indeks, Værdi = Nødvendig PWM
    int _correctedPwmTable[TABLE_SIZE];

    /**
     * @brief Privat hjælpefunktion til at læse en stabil RPM under kalibrering.
     * Indeholder logikken fra din readRpm funktion.
     * @param motor Reference til motor objektet.
     * @param stabilityTolerance Tilladt RPM udsving for at blive betragtet som stabil.
     * @param checkIntervalMs Millisekunder mellem stabilitetstjek.
     * @param maxWaitMs Maksimal tid at vente på stabilitet.
     * @return Den stabiliserede RPM værdi, eller sidste værdi hvis timeout.
     */
    int readStableRpm(Motor &motor, int stabilityTolerance = 2, unsigned long checkIntervalMs = 150, unsigned long maxWaitMs = 2000);

    /**
     * @brief Initialiserer tabellen til en standardtilstand (f.eks. 1:1 map).
     */
    void initializeTables();
};

#endif // SPEED_PROFILE_H