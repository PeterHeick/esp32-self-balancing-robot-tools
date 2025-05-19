#include "SpeedCalibration.h"
#include <Arduino.h>
#include "Motor.h"
#include <Stream.h>
#include "config.h" // For DEADZONE, MAX_RPM etc.
#include <cmath>     // For round()

// --- Konstruktør ---
SpeedCalibration::SpeedCalibration(int motorId) : _motorId(motorId) {
    _initializeTables();
}

// --- Privat: Initialiser Tabeller ---
void SpeedCalibration::_initializeTables() {
    // Initialiser den ØNSKEDE lineære RPM profil
    // Går fra 0 RPM (ved DEADZONE-1) til MAX_RPM (ved 255)
    for (int i = 0; i < INDEX_TABLE_SIZE; ++i) {
        if (i < DEADZONE) {
            _targetRpmProfile[i] = 0;
        } else {
            // Brug float til map for bedre præcision
            float mappedRpm = map((float)i, (float)DEADZONE, 255.0f, 0.0f, (float)MAX_RPM);
            _targetRpmProfile[i] = (int)round(mappedRpm);
        }
        // Initialiser korrektionstabellen til 1:1 map (eller 0)
        _correctedPwmForIndex[i] = i; // Eller 0
    }

    // Initialiser den endelige opslagstabel til 0 (eller -1 for at se huller)
    for (int i = 0; i < RPM_LOOKUP_TABLE_SIZE; ++i) {
        _rpmToPwmLookup[i] = 0; // Eller -1
    }
}

// --- Privat: Læs Stabil RPM ---
// (Bruger _motorPtr som skal være sat i runCalibration)
int SpeedCalibration::_readStableRpm(int stabilityTolerance, unsigned long checkIntervalMs, unsigned long maxWaitMs) {
    if (!_motorPtr) return 0; // Sikkerhedstjek

    int prevActual = -1000; // Start langt fra en mulig værdi
    int actual = _motorPtr->getActualRpm();
    unsigned long startWait = millis();

    while (millis() - startWait < maxWaitMs) {
        // Tjek om retningen er negativ, hvis ja, tag absolut værdi for stabilitetstjek
        int abs_actual = abs(actual);
        int abs_prevActual = abs(prevActual);

        if (abs(abs_actual - abs_prevActual) <= stabilityTolerance) {
            return actual; // Returner den faktiske værdi (med fortegn)
        }
        prevActual = actual;
        delay(checkIntervalMs); // Vent før næste tjek
        actual = _motorPtr->getActualRpm();
    }
    // Timeout
    if(_serialPtr) { // Print kun hvis Serial er tilgængelig
      //_serialPtr->printf(" [Timeout i readStableRpm, sidste RPM: %d] ", actual);
    }
    return actual; // Returner den sidst læste værdi
}

// --- Privat: Generer Index -> PWM Tabel ---
// (Bruger _motorPtr og _serialPtr som skal være sat)
void SpeedCalibration::_generateIndexToPwmTable() {
    if (!_motorPtr || !_serialPtr) return;

    _serialPtr->printf("\n--- Genererer Index->PWM Tabel for Motor %d ---\n", _motorId);
    _serialPtr->println("Idx, TargetRPM, GuessPWM, InitialRPM, FinalPWM, FinalRPM");

    int diff = 0; // Heuristik

    _motorPtr->setDirection(true); // Altid fremad under denne kalibrering
    _motorPtr->applyRawPwm(0);
    delay(500);

    // for (int speedIndex = DEADZONE; speedIndex < INDEX_TABLE_SIZE; ++speedIndex) {
    for (int speedIndex = INDEX_TABLE_SIZE; speedIndex > 0; --speedIndex) {
        int targetRpm = _targetRpmProfile[speedIndex];
        if (targetRpm <= 0) {
             _correctedPwmForIndex[speedIndex] = 0;
             continue;
        }

        int korrPwm = speedIndex + diff;
        korrPwm = constrain(korrPwm, 0, 255);
        int initialGuessPwm = korrPwm;

        _motorPtr->applyRawPwm(korrPwm);
        int actualRPM_initial = _readStableRpm(2, 150, 2500); // Længere ventetid/tolerance for initial
        int actualRPM = actualRPM_initial;

        // Juster ned
        while (actualRPM > targetRpm) {
            if (korrPwm <= 0) break;
             _motorPtr->applyRawPwm(--korrPwm);
             actualRPM = _readStableRpm(2, 100, 1000); // Hurtigere tjek under justering
        }

        // Juster op
        while (actualRPM < targetRpm) {
            if (korrPwm >= 255) break;
             _motorPtr->applyRawPwm(++korrPwm);
            actualRPM = _readStableRpm(2, 100, 1000);
        }

        _correctedPwmForIndex[speedIndex] = korrPwm;
        diff = korrPwm - speedIndex;

        _serialPtr->printf("%d,%d,%d,%d,%d,%d\n",
                          speedIndex, targetRpm, initialGuessPwm, actualRPM_initial, korrPwm, actualRPM);
    }
     _motorPtr->applyRawPwm(0);
     _motorPtr->stop();
     _serialPtr->println("--- Index->PWM Tabel Generering Færdig ---");
}

// --- Privat: Konverter til RPM -> PWM Tabel ---
void SpeedCalibration::_convertIndexTableToRpmTable() {
     _serialPtr->println("\n--- Konverterer til RPM->PWM Tabel ---");
     // Sæt PWM for RPM 0
     _rpmToPwmLookup[0] = _correctedPwmForIndex[0]; // Eller bare 0?

     // Gå gennem den genererede Index->PWM tabel
     for (int i = 1; i < INDEX_TABLE_SIZE; ++i) {
         int targetRpmForIndex = _targetRpmProfile[i]; // Den ideelle RPM for dette index
         int pwmForIndex = _correctedPwmForIndex[i];   // Den fundne PWM for dette index

         // Find start og slut RPM for dette PWM trin
         int prevTargetRpm = _targetRpmProfile[i-1];

         // Sæt PWM for alle RPM værdier mellem forrige og nuværende mål RPM
         // (inklusive nuværende target RPM)
         // Dette fylder hullerne ved at antage, at PWM-værdien er gyldig
         // for hele RPM-intervallet op til den næste ændring.
         for (int r = prevTargetRpm + 1; r <= targetRpmForIndex; ++r) {
             if (r >= 0 && r < RPM_LOOKUP_TABLE_SIZE) { // Bounds check
                 // Hvis vi ikke har sat en værdi for denne RPM endnu,
                 // eller hvis den nuværende PWM er *lavere* end en evt.
                 // tidligere sat værdi for samme RPM (sker hvis profilen ikke er monoton)
                 // vælger vi typisk den PWM der hører til det *index* der gav denne RPM.
                 // Simplificeret: Sæt PWM for dette RPM trin.
                 if (_rpmToPwmLookup[r] == 0) { // Undgå at overskrive hvis flere indices mapper til samme RPM?
                     _rpmToPwmLookup[r] = pwmForIndex;
                 }
                 // Alternativ: Tag altid den seneste?
                 // _rpmToPwmLookup[r] = pwmForIndex;
             }
         }
     }

     // Efterfyld evt. resterende huller i slutningen (hvis MAX_RPM > _targetRpmProfile[255])
     // eller i starten (hvis 0 ikke blev sat)
     for(int r = 1; r < RPM_LOOKUP_TABLE_SIZE; ++r) {
         if (_rpmToPwmLookup[r] == 0) {
             _rpmToPwmLookup[r] = _rpmToPwmLookup[r-1]; // Kopier forrige værdi
         }
     }
     _serialPtr->println("--- Konvertering til RPM->PWM Færdig ---");
}

// --- Public: Kør Hele Processen ---
bool SpeedCalibration::runCalibration(Motor &motor, Stream &serialPort) {
    _motorPtr = &motor;
    _serialPtr = &serialPort;

    _generateIndexToPwmTable();       // Generer Index -> PWM
    _convertIndexTableToRpmTable();   // Konverter til RPM -> PWM
    printRpmToPwmTable(serialPort); // Udskriv den endelige tabel

    _motorPtr = nullptr; // Ryd pointere
    _serialPtr = nullptr;
    return true; // Antager succes for nu
}

// --- Public: Opslag i RPM->PWM Tabel ---
int SpeedCalibration::getPwmForRpm(int targetRpm) const {
    // Sørg for at input er indenfor tabelgrænser
    targetRpm = abs(targetRpm); // Brug altid positiv RPM til opslag
    if (targetRpm >= RPM_LOOKUP_TABLE_SIZE) {
        targetRpm = RPM_LOOKUP_TABLE_SIZE - 1; // Klip til max
    }
    if (targetRpm < 0) {
        targetRpm = 0; // Klip til min
    }
    return _rpmToPwmLookup[targetRpm];
}

// --- Public: Udskriv RPM->PWM Tabel ---
void SpeedCalibration::printRpmToPwmTable(Stream &serialPort) const {
     serialPort.printf("\n--- RPM -> PWM Opslagstabel (Motor %d) ---\n", _motorId);
     serialPort.println("// Format: const int RPM_TO_PWM_MOTOR_%d[RPM_LOOKUP_TABLE_SIZE] = {");
     serialPort.print("    ");
     for (int i = 0; i < RPM_LOOKUP_TABLE_SIZE; ++i) {
         serialPort.print(_rpmToPwmLookup[i]);
         if (i < RPM_LOOKUP_TABLE_SIZE - 1) {
             serialPort.print(",");
             if ((i + 1) % 16 == 0) { // Linjeskift hver 16. værdi
                 serialPort.print("\n    ");
             } else {
                 serialPort.print(" "); // Mellemrum
             }
         }
     }
     serialPort.println("\n};");
     serialPort.println("-------------------------------------------------");
}


// --- Implementering af NVS funktioner her (hvis du vælger at bruge dem) ---
// bool SpeedCalibration::loadRpmPwmTableFromNvs() { ... }
// bool SpeedCalibration::saveRpmPwmTableToNvs() { ... }