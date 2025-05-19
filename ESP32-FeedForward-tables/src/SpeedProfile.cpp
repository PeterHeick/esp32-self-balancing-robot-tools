#include "SpeedProfile.h"
#include <Arduino.h> // For millis, delay etc.
#include "Motor.h"   // Sikrer at Motor klassen er kendt
#include <Stream.h>  // For Serial


SpeedProfile::SpeedProfile(int motorId) : _motorId(motorId) {
    initializeTables();
}

void SpeedProfile::initializeTables() {
    // Initialiser korrektionstabellen til en 1:1 map som udgangspunkt
    for (int i = 0; i < TABLE_SIZE; ++i) {
        _correctedPwmTable[i] = i;
    }
    // Du kan evt. sætte værdier under DEADZONE til 0 her, hvis ønsket
     for (int i = 0; i < DEADZONE; ++i) { // DEADZONE skal være defineret i config.h
         _correctedPwmTable[i] = 0;
     }
}

// Privat hjælpefunktion til at vente på stabil RPM
int SpeedProfile::readStableRpm(Motor &motor, int stabilityTolerance, unsigned long checkIntervalMs, unsigned long maxWaitMs) {
    int prevActual = -1000; // Start langt fra en mulig værdi
    int actual = motor.getActualRpm();
    unsigned long startWait = millis();

    while (millis() - startWait < maxWaitMs) {
        if (abs(actual - prevActual) <= stabilityTolerance) {
            // Stabiliseret (inden for tolerancen)
            // Måske kræv et par stabile aflæsninger i træk? For nu returnerer vi straks.
            // serialPort.printf("RPM Stabil: %d (prev: %d)\n", actual, prevActual); // Debug
            return actual;
        }
        prevActual = actual;
        delay(checkIntervalMs); // Vent før næste tjek
        actual = motor.getActualRpm();
        // serialPort.printf("RPM Venter: %d (prev: %d)\n", actual, prevActual); // Debug
    }
    // Timeout - returner den sidst læste værdi
    // serialPort.printf("RPM Timeout: %d (prev: %d)\n", actual, prevActual); // Debug
    return actual;
}


void SpeedProfile::generateCorrectionTable(Motor &motor, Stream &serialPort) {
    serialPort.printf("\n*** Starter Kalibrering for Motor ID %d ***\n", _motorId);
    serialPort.println("Format: SpeedIdx, TargetRPM, InitialGuessPWM, StableRPM_Initial, FinalAdjPWM, StableRPM_Final");

    initializeTables(); // Start med en ren tabel
    int diff = 0;       // Heuristik for næste gæt

    // Kør motoren fremad under kalibrering
    motor.setDirection(true);
    motor.applyRawPwm(0); // Sørg for at starte fra 0
    delay(500); // Lille pause

    // Start kalibrering fra efter dødzone
    for (int speedIndex = DEADZONE; speedIndex < TABLE_SIZE; ++speedIndex) {
        int targetRpm = TARGET_RPM_PROFILE[speedIndex];
        if (targetRpm <= 0) { // Spring over hvis målet er 0 eller negativt
             _correctedPwmTable[speedIndex] = 0; // Sæt til 0 i tabellen
             continue;
        }

        // 1. Startgæt for PWM (korrPwm)
        int korrPwm = speedIndex + diff;
        korrPwm = constrain(korrPwm, 0, 255); // Begræns gæt

        // 2. Anvend gæt og vent på stabil RPM
        motor.applyRawPwm(korrPwm);
        int actualRPM_initial = readStableRpm(motor); // Vent på stabilitet

        int actualRPM = actualRPM_initial; // Gem start RPM

        // Gem start-PWM for logning
        int initialGuessPwm = korrPwm;

        // 3. Finjuster nedad (hvis nødvendigt)
        while (actualRPM > targetRpm) {
            if (korrPwm <= 0) break; // Kan ikke gå lavere
            motor.applyRawPwm(--korrPwm);
            actualRPM = readStableRpm(motor, 2, 100); // Brug kortere interval/tolerance under finjustering?
        }

        // 4. Finjuster opad (hvis nødvendigt)
        while (actualRPM < targetRpm) {
            if (korrPwm >= 255) { // Kan ikke gå højere
                 // Evt. log en advarsel her, hvis actualRPM stadig er langt fra targetRpm
                 break;
            }
            motor.applyRawPwm(++korrPwm);
             actualRPM = readStableRpm(motor, 2, 100); // Brug kortere interval/tolerance under finjustering?
        }

        // 5. Gem resultat og beregn diff
        _correctedPwmTable[speedIndex] = korrPwm;
        diff = korrPwm - speedIndex;

        // 6. Log resultatet for dette trin
        serialPort.printf("%d,%d,%d,%d,%d,%d\n",
                          speedIndex, targetRpm, initialGuessPwm, actualRPM_initial, korrPwm, actualRPM);

        // Lille pause mellem hvert trin for at undgå overophedning?
        // delay(50);

    } // End for loop

    motor.applyRawPwm(0); // Stop motoren efter kalibrering
    motor.stop();
    serialPort.printf("*** Kalibrering Færdig for Motor ID %d ***\n", _motorId);

    // Valgfrit: Udskriv den færdige tabel
    // printCorrectionTable(serialPort);
}

int SpeedProfile::getCorrectedPwm(int speedIndex) const {
    if (speedIndex < 0 || speedIndex >= TABLE_SIZE) {
        // Ugyldigt indeks, returner 0 eller en anden sikker værdi
        return 0;
    }
    // Slå op i den kalibrerede tabel
    return _correctedPwmTable[speedIndex];
}

void SpeedProfile::printCorrectionTable(Stream &serialPort) const {
     serialPort.printf("\n--- Korrigeret PWM Tabel for Motor ID %d ---\n", _motorId);
     serialPort.println("Index, KorrigeretPWM");
     for (int i = 0; i < TABLE_SIZE; ++i) {
         serialPort.printf("%d,%d\n", i, _correctedPwmTable[i]);
     }
     serialPort.println("----------------------------------------");
}


// --- Implementering af NVS funktioner (hvis du vil bruge dem) ---
/*
#include "nvs_flash.h"
#include "nvs.h"

bool SpeedProfile::loadTableFromNvs() {
    nvs_handle_t my_handle;
    esp_err_t err;
    char nvs_key[15]; // Plads til "motorX_pwmTbl" + null terminator
    snprintf(nvs_key, sizeof(nvs_key), "motor%d_pwmTbl", _motorId);

    err = nvs_open("SpeedProfiles", NVS_READONLY, &my_handle);
    if (err != ESP_OK) return false;

    size_t required_size = sizeof(_correctedPwmTable);
    err = nvs_get_blob(my_handle, nvs_key, _correctedPwmTable, &required_size);

    nvs_close(my_handle);

    if (err == ESP_OK && required_size == sizeof(_correctedPwmTable)) {
        Serial.printf("Korrektionstabel for motor %d indlæst fra NVS.\n", _motorId);
        return true;
    } else {
        Serial.printf("Fejl ved indlæsning af tabel for motor %d fra NVS (%s), eller størrelse passer ikke.\n", _motorId, esp_err_to_name(err));
        initializeTables(); // Gendan default hvis fejl
        return false;
    }
}

bool SpeedProfile::saveTableToNvs() {
    nvs_handle_t my_handle;
    esp_err_t err;
     char nvs_key[15];
    snprintf(nvs_key, sizeof(nvs_key), "motor%d_pwmTbl", _motorId);

    // NVS skal være initialiseret i setup()!
    err = nvs_open("SpeedProfiles", NVS_READWRITE, &my_handle);
    if (err != ESP_OK) {
         Serial.printf("Fejl (%s) ved åbning af NVS handle for skrivning (Motor %d).\n", esp_err_to_name(err), _motorId);
         return false;
    }

    err = nvs_set_blob(my_handle, nvs_key, _correctedPwmTable, sizeof(_correctedPwmTable));
    if (err != ESP_OK) {
        nvs_close(my_handle);
        Serial.printf("Fejl (%s) ved skrivning af blob til NVS (Motor %d).\n", esp_err_to_name(err), _motorId);
        return false;
    }

    err = nvs_commit(my_handle);
    nvs_close(my_handle); // Luk altid handle

    if (err != ESP_OK) {
        Serial.printf("Fejl (%s) ved commit til NVS (Motor %d).\n", esp_err_to_name(err), _motorId);
        return false;
    }

    Serial.printf("Korrektionstabel for motor %d gemt til NVS.\n", _motorId);
    return true;
}
*/