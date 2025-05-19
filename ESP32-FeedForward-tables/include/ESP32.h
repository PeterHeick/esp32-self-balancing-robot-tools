#ifndef ESP32_PIN_DEFINITIONS_H
#define ESP32_PIN_DEFINITIONS_H


// ESP32 dev board pin definitions
// Motor A Pin Definitions
#define MOTOR1_IN1     27  // gul
#define MOTOR1_IN2     26  // grøn
#define MOTOR1_ENA     12  // blå    // PWM capable
#define MOTOR1_HALL_A  17
#define MOTOR1_HALL_B  16

// Motor B Pin Definitions
// Byt rundt så de kører samme vej
// #define MOTOR2_IN3     33  // gul
// #define MOTOR2_IN4     32  // grøn
#define MOTOR2_IN4     33  // grøn
#define MOTOR2_IN3     32  // gul
#define MOTOR2_ENB     25  // blå    // PWM capable
#define MOTOR2_HALL_A  35
#define MOTOR2_HALL_B  34

// I2C Gyroscope Pin Definitions
#define I2C_SDA        21  // Default I2C SDA pin
#define I2C_SCL        22  // Default I2C SCL pin

// SPI
#define SS              5  // Default SPI SS pin same as ULTRA_TRIG
#define SCK            18  // Default SPI SCK pin same as SD_SCK
#define MOSI           19  // Default SPI MOSI pin same as SD_MOSI
#define MISO           23  // Default SPI MISO pin same as SD_MISO

// RX / TX
#define RX              3
#define TX              1

// Analog diff
#define VP             36
#define VN             39

// Micro SD card
#define SD_CS           4
#define SD_SCK         18  // Same as SPI SCK
#define SD_MOSI        19  // Same as SPI MOSI
#define SD_MISO        23  // Same as SPI MISO


// Not used
#define nu1            13
#define nu2            14
#define nu3            15

// Ultrasonic Sensor Pin Definitions
#define ULTRA_TRIG      5  // same as SS
#define ULTRA_ECHO     18  // same as SCK

// PWM Configuration
#define PWM_FREQUENCY  5000    // 5 kHz
#define PWM_RESOLUTION 8       // 9-bit resolution (0-255)
#define PWM_CHANNEL1   0       // PWM channel for Motor 1
#define PWM_CHANNEL2   1       // PWM channel for Motor 2

// I2C Configuration
#define I2C_FREQUENCY  400000  // 400 kHz

#endif // ESP32_PIN_DEFINITIONS_H

  