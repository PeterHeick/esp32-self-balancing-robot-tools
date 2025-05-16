import numpy as np
import matplotlib.pyplot as plt

# Simulationsparametre
dt = 0.01  # tidsinterval i sekunder
T = 10.0  # samlet simuleringsperiode i sekunder
N = int(T / dt)  # antal tidstrin

# Robotparametre
m = 1.0  # masse
l = 0.5  # længde til tyngdepunkt
g = 9.81  # tyngdekraft

# PID-parametre
Kp = 20.0
Ki = 2.0
Kd = 1.0

# Initialtilstand [vinkel, vinkelhastighed]
state = np.array([0.1, 0.0])
integral = 0.0
derivative = 0.0
prev_error = 0.0

# Til at gemme data for plotting
angles = []

# Simulationsløkke
for i in range(N):
    # PID-controller
    error = 0.0 - state[0]  # fejl (ønsket vinkel - nuværende vinkel)
    integral += error * dt
    derivative = (error - prev_error) / dt
    control_input = Kp * error + Ki * integral + Kd * derivative
    prev_error = error

    # Simuler robotdynamik
    torque = control_input
    acceleration = (torque / (m * l ** 2)) - (g * np.sin(state[0]) / l)
    state[1] += acceleration * dt  # opdater vinkelhastighed
    state[0] += state[1] * dt  # opdater vinkel

    # Gem data for plotting
    angles.append(state[0])

# Plot resultater
plt.plot(np.linspace(0, T, N), angles)
plt.xlabel('Tid [s]')
plt.ylabel('Vinkel [rad]')
plt.title('Balancerende Robot Simulation')
plt.show()

