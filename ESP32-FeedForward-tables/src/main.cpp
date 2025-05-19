#include <Arduino.h>
#include "config.h"
#include "ESP32.h"
#include "Motor.h"
#include "SpeedCalibration.h" // Inkluder den nye klasse

// --- Globale Objekter ---
Motor motor1(MOTOR1_IN1, MOTOR1_IN2, MOTOR1_ENA, MOTOR1_HALL_A, PWM_CHANNEL1, MOTOR_MIN_MEASURE_TIME_MS);
Motor motor2(MOTOR2_IN3, MOTOR2_IN4, MOTOR2_ENB, MOTOR2_HALL_A, PWM_CHANNEL2, MOTOR_MIN_MEASURE_TIME_MS);

// Opret SpeedCalibration objekter
SpeedCalibration calibration1(1);
SpeedCalibration calibration2(2);

// --- ISR Funktioner ---
void IRAM_ATTR motor1_isrA() { motor1.incrementPulseCount(); }
void IRAM_ATTR motor2_isrA() { motor2.incrementPulseCount(); }
#define NOOFLOOPS 5

void genrpmtabel1()
{
  Serial.println("Genererer RPM -> PWM tabel for Motor 2");
  double tabel[256];
  int rpmToPwmLookup[256];
  int rpm;
  int last = 250;
  for (int pwm = 255; pwm >= 0; --pwm)
    tabel[pwm] = 0;
  for (int gens = 0; gens < NOOFLOOPS; gens++)
  {
    Serial.printf("\nLoop nr %d\n", gens);
    for (int pwm = 255; pwm >= 0; --pwm)
    {
      motor2.applyRawPwm(pwm);
      delay(150);
      rpm = motor2.getActualRpm();
      Serial.printf("i: %d, rpm: %d", pwm, rpm);
      Serial.print("  ");
      if ((pwm + 1) % 7 == 0)
        Serial.print("\n   ");
      else
        Serial.print(" "); // Mellemrum
      if (rpm == 0)
      {
        rpm = last;
      }
      else
      {
        last = rpm;
      }
      tabel[pwm] += (double)rpm;
    }
    Serial.printf("\n");
  }
  /*
  for (int i = 0; i < 256; ++i)
  {
    Serial.printf("%d, %d\n", tabel[i], i);
  }
  */
  Serial.println("const int RPM_TO_PWM_MOTOR_%d[RPM_LOOKUP_TABLE_SIZE] = {");
  Serial.print("    ");
  for (int i = 0; i < 256; ++i)
    rpmToPwmLookup[i] = 0;
  for (int i = 0; i < 256; ++i)
  {
    rpmToPwmLookup[(int)(tabel[i] / NOOFLOOPS)] = i;
  }
  for (int i = 1; i < 256; ++i)
  {
    // if (rpmToPwmLookup[i] == 0) {
    // rpmToPwmLookup[i] = rpmToPwmLookup[i-1];
    // }
    Serial.print(rpmToPwmLookup[i]);
    if (i < 256 - 1)
    {
      Serial.print(",");
      if ((i + 1) % 16 == 0)
      { // Linjeskift hver 16. værdi
        Serial.print("\n    ");
      }
      else
      {
        Serial.print(" "); // Mellemrum
      }
    }
  }
  Serial.printf("\n};\n");
  motor2.stop();
}

void genrpmtabel2() {
  #define NOOFLOOPS 5
  double tabel[256];
  int rpmToPwmLookup[255];
  int rpm;
  int last = 250; // <-- Formål uklart, og startværdi 250 virker mærkelig. Lad os fjerne den.

  // --- Nulstil Sum Tabel ---
  // FEJL: Loop grænse. Skal være 255.
  // for (int pwm = 256; pwm >= 0; --pwm)
  for (int pwm = 255; pwm >= 0; --pwm) // Rettet
    tabel[pwm] = 0.0; // Nulstil double tabel

  Serial.println("Starter RPM måling (PWM 0 -> 255)...");
  for (int gens = 0; gens < NOOFLOOPS; gens++) {
    Serial.printf("  Gennemløb %d/%d:\n   ", gens + 1, NOOFLOOPS);
    for (int pwm = 0; pwm <= 255; ++pwm) { // Kør OPAD fra 0 til 255
        motor1.setDirection(true); // Sørg for retning er sat
        motor1.applyRawPwm(pwm);
        delay(150); // *** TUNING: Juster evt. denne delay ***
        rpm = motor1.getActualRpm();

        // Debug print (mindre hyppigt for at undgå for meget output)
        if (pwm % 16 == 0) Serial.printf("PWM %d->RPM %d | ", pwm, rpm);
        if (pwm == 255) Serial.println(); // Ny linje til sidst

        // Læg målingen til sum-tabellen
        tabel[pwm] += (double)rpm;
    }
    Serial.println("  Gennemløb færdig, stopper motor.");
    motor1.applyRawPwm(0); // Stop motor mellem gennemløb
    delay(1000); // Pause mellem gennemløb
  }
  Serial.println("RPM måling færdig.");

  // --- Beregn Gennemsnit ---
  Serial.println("Beregner gennemsnitlig RPM for hver PWM...");
  for (int pwm = 0; pwm <= 255; ++pwm) {
      tabel[pwm] = tabel[pwm] / NOOFLOOPS;
      // Udskriv evt. den gennemsnitlige PWM -> RPM tabel her for kontrol
      // Serial.printf("PWM %d, Avg RPM %.1f\n", pwm, tabel[pwm]);
  }

  // --- Invertering til RPM -> PWM Tabel ---
  Serial.println("Inverterer tabel til RPM -> PWM format...");
  // Initialiser output tabel. Brug -1 til at markere "ikke sat endnu".
  for (int r = 0; r < 255; ++r) {
      rpmToPwmLookup[r] = -1; // Eller 0 hvis du foretrækker
  }

  // Sæt PWM for RPM 0
  rpmToPwmLookup[0] = 0; // RPM 0 kræver PWM 0 (eller laveste PWM i dødzone)

  // Gå gennem den målte/gennemsnitlige PWM -> RPM tabel
  for (int p = 0; p <= 255; ++p) { // p = PWM værdi
      // Find den gennemsnitlige RPM for denne PWM, afrundet til nærmeste heltal
      int avgRpm = (int)round(tabel[p]);

      // Sørg for at RPM er indenfor grænserne for output-tabellen
      if (avgRpm >= 0 && avgRpm < 255) {
          // Gem KUN den FØRSTE (laveste) PWM værdi, der opnår denne RPM
          if (rpmToPwmLookup[avgRpm] == -1) { // Hvis denne RPM ikke er set før
              rpmToPwmLookup[avgRpm] = p;
          }
          // Hvis du altid vil gemme den SIDSTE (højeste) PWM for en RPM:
          // rpmToPwmLookup[avgRpm] = p;
      }
  }

  // --- Fyld Huller i RPM -> PWM Tabellen ---
  Serial.println("Fyldeder huller i RPM -> PWM tabellen...");
  // Sørg for at RPM 0 har en værdi (burde være 0 eller laveste PWM fra dødzone)
  if (rpmToPwmLookup[0] == -1) {
      rpmToPwmLookup[0] = 0; // Sikkerhedsforanstaltning
  }
  // Gå gennem tabellen og fyld huller (-1) med værdien fra forrige RPM
  for (int r = 1; r < 255; ++r) {
      if (rpmToPwmLookup[r] == -1) {
          rpmToPwmLookup[r] = rpmToPwmLookup[r-1];
      }
  }
  // Tjek evt. om den sidste værdi blev sat?
  if (rpmToPwmLookup[MAX_RPM] == -1 || rpmToPwmLookup[MAX_RPM] == 0) {
       // Hvis MAX_RPM ikke blev ramt præcist, sæt den evt. til max PWM?
       // rpmToPwmLookup[MAX_RPM] = 255; // Overvej dette
       Serial.println("Advarsel: MAX_RPM blev muligvis ikke ramt præcist under måling.");
  }


  // --- Udskriv den Færdige RPM -> PWM Tabel til Hardkodning ---
  // Brug _motorId her hvis relevant (skal hentes et sted fra)
  Serial.printf("\nconst int RPM_TO_PWM_MOTOR_X[%d] = {\n    ", 255);
  for (int i = 0; i < 255; ++i) {
    Serial.print(rpmToPwmLookup[i]);
    if (i < 255 - 1) {
      Serial.print(",");
      if ((i + 1) % 16 == 0) { // Linjeskift hver 16. værdi
        Serial.print("\n    ");
      } else {
        Serial.print(" "); // Mellemrum
      }
    }
  }
  Serial.printf("\n};\n");
}

// --- Setup ---
void setup()
{
  Serial.begin(115200);
  delay(2000);
  Serial.println("\n\n========================================");
  Serial.println("    Motor Kalibreringsprogram V2 Start");
  Serial.println("========================================");
  Serial.print("Core: ");
  Serial.println(xPortGetCoreID());
  Serial.printf("MOTOR_MIN_MEASURE_TIME_MS = %d ms\n", MOTOR_MIN_MEASURE_TIME_MS);
  Serial.println("Initialiserer motorer...");

  motor1.begin();
  motor2.begin();
  Serial.println("Motorer initialiseret.");

  attachInterrupt(digitalPinToInterrupt(MOTOR1_HALL_A), motor1_isrA, RISING);
  attachInterrupt(digitalPinToInterrupt(MOTOR2_HALL_A), motor2_isrA, RISING);
  Serial.println("Interrupts sat op.");

  // --- Mulighed for Tuning ---
  /*
  Serial.println("Send 't' inden for 3 sekunder for at starte PID tuning...");
  unsigned long setupStartTime = millis();
   while (millis() - setupStartTime < 3000 && !Serial.available()) { delay(10); }

  bool startTuning = false;
  if (Serial.available() > 0) {
      if (Serial.read() == 't') { startTuning = true; }
      while (Serial.available()) Serial.read(); // Tøm buffer
  }

  if (startTuning) {
       Serial.println("\n*** Går til Tuning Mode for Motor 1 ***");
       // Brug PID variablerne fra SpeedController klassen her? Nej, vi tuner den globale.
       // Vi skal bruge de globale speedPID variabler til tuning
       // Sørg for at speedPID_Mx objekterne er initialiseret FØR tuneren kaldes.
       // De globale PID objekter speedPID_M1/M2 bruges ikke direkte i loop,
       // men de skal eksistere for at tuneren kan justere deres parametre.
       PIDTuner::tuneMotorSpeed(Serial, motor1, speedCtrl1, speedInputM1, speedOutputM1, speedSetpointM1);
       PIDTuner::tuneMotorSpeed(Serial, motor2, speedCtrl2, speedInputM2, speedOutputM2, speedSetpointM2);

      Serial.println("\n*** Tuning afsluttet - Gem fundne værdier i config.h og genstart ***");
      delay(1000);
      ESP.restart();
  }
  // --- Tuning Slut ---
  */

  genrpmtabel2();

  delay(9999);
  // --- Kør Kalibrering & Konvertering ---
  calibration1.runCalibration(motor1, Serial);

  Serial.println("\nPause før næste motor...\n");
  motor1.stop(); // Stop motor 1 før vi starter motor 2
  delay(3000);

  calibration2.runCalibration(motor2, Serial);

  // --- Færdig ---
  Serial.println("\n========================================");
  Serial.println("   Kalibrering & Konvertering Fuldendt!");
  Serial.println("========================================");
  Serial.println("Kopier de udskrevne 'RPM -> PWM Opslagstabel' arrays");
  Serial.println("til dit hovedprojekt for hardkodning.");
  Serial.println("\nProgram færdigt.");
  Serial.println("========================================");
}

// --- Loop (Bruges ikke) ---
void loop()
{
  delay(1000);
}
