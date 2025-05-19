/**
 * PIDTuner.cpp
 *
 * Implementering af interaktiv PID tuning funktion.
 */

#include "PIDTuner.h"
#include "config.h" // For LOOP_TIME_MS, SPEED_KP, SPEED_KI, SPEED_KD
#include <Arduino.h>
#include <stdlib.h> // For atof
#include <PID_v1.h> // Dobbelttjek om nødvendig her, hvis allerede i .h
#include "Motor.h"  // Dobbelttjek om nødvendig her, hvis allerede i .h
#include <Stream.h> // Dobbelttjek om nødvendig her, hvis allerede i .h

namespace PIDTuner
{

  // Hjælpefunktion til at læse en linje fra seriel port (uændret)
  String readSerialLine(Stream &serialPort)
  {
    String line = "";
    unsigned long startTime = millis();
    // Vent max 100ms på en hel linje for at undgå at blokere for evigt
    while (millis() - startTime < 100)
    {
      if (serialPort.available())
      {
        char c = serialPort.read();
        if (c == '\n' || c == '\r')
        {
          if (line.length() > 0)
            break;
        }
        else
        {
          line += c;
        }
        startTime = millis(); // Nulstil timeout hvis tegn modtages
      }
      delay(1); // Undgå 100% CPU brug
    }
    line.trim();
    return line;
  }

  // Funktion til at udskrive hjælp (uændret)
  void printHelp(Stream &serialPort)
  {
    serialPort.println(F("\n--- PID Tuning Hjælp ---"));
    serialPort.println(F("Send kommandoer efterfulgt af Enter:"));
    serialPort.println(F("  p <værdi>  : Sæt Kp gain (f.eks. p1.25)"));
    serialPort.println(F("  i <værdi>  : Sæt Ki gain (f.eks. i0.05)"));
    serialPort.println(F("  d <værdi>  : Sæt Kd gain (f.eks. d0.8)"));
    serialPort.println(F("  s <værdi>  : Sæt mål RPM (Setpoint) (f.eks. s100)"));
    serialPort.println(F("  g          : Start/Genoptag PID-loop og motor"));
    serialPort.println(F("  x          : Stop PID-loop og motor (sæt PWM=0)"));
    serialPort.println(F("  h          : Vis denne hjælp"));
    serialPort.println(F("  q          : Afslut tuning og fortsæt program"));
    serialPort.println(F("------------------------"));
    serialPort.println(F("Output format (når 'g' er aktiv):"));
    serialPort.println();
    serialPort.println(F("Tid(ms),KP, KI, KD, Setpoint,Input(RPM),Output(PWM)"));
  }

  // --- Hoved Tuning Funktion ---
  void tuneMotorSpeed(Stream &serialPort, Motor &motor, PID &pid,
                      double &pidInput, double &pidOutput, double &pidSetpoint)
  {
    serialPort.println(F("\n*** Starter Interaktiv PID Tuning ***"));
    printHelp(serialPort);

    bool runPid = true; // Kører PID-loopet?
    unsigned long lastPidComputeTimeMicros = 0;
    const unsigned long pidIntervalMicros = LOOP_TIME_MS * 1000UL; // Brug UL for unsigned long

    // --- Lokale variabler til at holde styr på tunings under sessionen ---
    // Initialiser med værdier fra config.h (eller startværdier)
    // SØRG FOR AT SPEED_KP, SPEED_KI, SPEED_KD findes i config.h!
    double currentKp = SPEED_KP;
    double currentKi = SPEED_KI;
    double currentKd = SPEED_KD;
    // Sæt PID'ens tunings til disse startværdier
    pid.SetTunings(currentKp, currentKi, currentKd);
    serialPort.flush();
    serialPort.printf("\n");
    serialPort.printf("Tid(ms),KP, KI, KD, Setpoint,Input(RPM),Output(PWM)\n");
    serialPort.flush();

    // Gem oprindelig PID mode
    int originalMode = pid.GetMode();
    pid.SetMode(AUTOMATIC); // Sæt til AUTOMATIC under tuning

    // RAII Guard til at gendanne mode når funktionen forlades
    struct PidGuard
    {
      PID &pidRef;
      int modeRef;
      ~PidGuard()
      {
        pidRef.SetMode(modeRef); // Gendan mode
                                 // serialPort.printf("PID mode gendannet til: %d\n", modeRef); // Debug
      }
    } guard{pid, originalMode};

    // Sørg for at motoren er stoppet fra start
    motor.applyRawPwm(0);

    // --- Hoved Tuning Løkke ---
    while (true)
    {
      // --- Håndter Seriel Input ---
      if (serialPort.available() > 0)
      {
        String commandLine = readSerialLine(serialPort);

        if (commandLine.length() > 0)
        {
          serialPort.print(F("Modtaget: "));
          serialPort.println(commandLine);

          char command = commandLine.charAt(0);
          String valueStr = commandLine.substring(1);
          double value = atof(valueStr.c_str()); // Konverter værdi-del til double

          switch (command)
          {
          case 'p':
          case 'P':
            currentKp = value;                               // Opdater lokal Kp
            pid.SetTunings(currentKp, currentKi, currentKd); // Anvend alle lokale værdier
            serialPort.print(F("-> Ny Kp: "));
            serialPort.println(currentKp, 4);
            break;
          case 'i':
          case 'I':
            currentKi = value;                               // Opdater lokal Ki
            pid.SetTunings(currentKp, currentKi, currentKd); // Anvend alle lokale værdier
            serialPort.print(F("-> Ny Ki: "));
            serialPort.println(currentKi, 4);
            break;
          case 'd':
          case 'D':
            currentKd = value;                               // Opdater lokal Kd
            pid.SetTunings(currentKp, currentKi, currentKd); // Anvend alle lokale værdier
            serialPort.print(F("-> Ny Kd: "));
            serialPort.println(currentKd, 4);
            break;
          case 's':
          case 'S':
            pidSetpoint = value; // Opdater den eksterne Setpoint variabel direkte
            serialPort.print(F("-> Nyt Setpoint: "));
            serialPort.println(pidSetpoint, 2);
            // Sæt retning med det samme hvis PID kører
            if (runPid)
            {
              motor.setDirection(pidSetpoint >= 0);
            }
            break;
          case 'g':
          case 'G':
            if (pidSetpoint == 0)
            {
              serialPort.println(F("-> Advarsel: Setpoint er 0. Brug 's' til at sætte et mål RPM > 0 først."));
            }
            else
            {
              runPid = true;
              motor.setDirection(pidSetpoint >= 0); // Sæt retning baseret på setpoint
              serialPort.println(F("-> Starter/Genoptager PID loop..."));
              serialPort.println(F("Format: Tid(ms),Setpoint,Input(RPM),Output(PWM)"));
              lastPidComputeTimeMicros = micros(); // Nulstil timer for PID loop
            }
            break;
          case 'x':
          case 'X':
            runPid = false;
            motor.applyRawPwm(0); // Stop motoren aktivt
            serialPort.println(F("-> Stopper PID loop og motor."));
            break;
          case 'h':
          case 'H':
            printHelp(serialPort);
            break;
          case 'q':
          case 'Q':
            runPid = false;
            motor.applyRawPwm(0); // Stop motoren
            serialPort.println(F("-> Afslutter tuning..."));
            // PID mode gendannes automatisk af PidGuard destructor
            return; // Afslut funktionen
          default:
            serialPort.println(F("Ukendt kommando. Skriv 'h' for hjælp."));
            break;
          }
        }
        serialPort.printf("New Tunings: Kp=%.4f, Ki=%.4f, Kd=%.4f\n", currentKp, currentKi, currentKd);
        serialPort.printf("New Setpoint: %.2f RPM\n", pidSetpoint);
        serialPort.flush();
      }

      unsigned long nowMicros = micros();
      if (runPid && (nowMicros - lastPidComputeTimeMicros >= pidIntervalMicros))
      {
        lastPidComputeTimeMicros = nowMicros; // Opdater tidspunkt for sidste kørsel

        // 1. Læs faktisk RPM (bliver til PID input)
        double rawRpmInput = motor.getActualRpm();

        // 2. Beregn PID Output
        // Sikrer at Setpoint er positivt for Compute, da retning styres separat?
        // Eller lad PID håndtere negativt Setpoint hvis muligt?
        // Lad os antage, vi tuner med positivt Setpoint her for simpelheds skyld.
        // Hvis pidSetpoint kan være negativt, skal input/output måske justeres.
        // Vi bruger den 'pidSetpoint' der blev sat via 's' kommandoen.
        // Vi bruger 'pidInput' som lige er læst.
        // 'pidOutput' opdateres af Compute().
        // Vi skal bruge en static variabel til at huske den forrige filtrerede værdi

        static double filteredRpmInput = rawRpmInput;                                      // Initialiser første gang
        filteredRpmInput = LOWPASSFILTER(rawRpmInput, filteredRpmInput, ALPHA); // Brug ALPHA fra config.h (f.eks. 0.5 som start?)
        pidInput = filteredRpmInput;
                                                                                           // Du skal definere RPM_FILTER_ALPHA i config.h, f.eks. #define RPM_FILTER_ALPHA 0.5

        bool computeSuccess = pid.Compute();

        if (computeSuccess)
        {
          // 3. Anvend PWM Output
          // Vi antager her, at setDirection er sat korrekt baseret på pidSetpoint.
          // PID output er altid positivt pga. output limits (0-255).
          motor.applyRawPwm((int)pidOutput);

          // 4. Udskriv data til plotting/analyse
          serialPort.printf("%lu, %0.4f, %0.4f, %0.4f, %d, %d, %d\n", millis(), currentKp, currentKi, currentKd, (int)pidSetpoint, (int)pidInput, (int)pidOutput);
          serialPort.flush();
          serialPort.println();
        }
        else
        {
          serialPort.println("PID Compute failed?");
          runPid = false;
          motor.applyRawPwm(0);
        }
      }
      else if (!runPid)
      {
        // Sørg for at motoren er stoppet, når PID ikke kører
        motor.applyRawPwm(0);
      }

      // Undgå at CPU'en spinner 100% unødigt i while(true)
      delay(1);

    } // End while(true)
  }

} // namespace PIDTuner