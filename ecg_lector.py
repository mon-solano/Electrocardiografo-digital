"""
Lector / graficador de ECG  -  AD8232 + Raspberry Pi Pico
----------------------------------------------------------
- Lee durante DURACION_SEG segundos y luego para solo
- Guarda UN solo CSV con timestamp en registros_ecg/
- Grafica ECG en tiempo real y tacograma R-R
"""

import serial
import csv
import time
import os
from collections import deque
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# ----------------- CONFIGURACION -----------------
PUERTO        = "COM3"
BAUD          = 115200
FS            = 250
VENTANA_SEG   = 5
MAX_LATIDOS   = 40
DURACION_SEG  = 60          # segundos de grabacion, luego para solo
CARPETA_CSV   = "registros_ecg"
# -------------------------------------------------

os.makedirs(CARPETA_CSV, exist_ok=True)

N = FS * VENTANA_SEG
tiempos = deque(maxlen=N)
valores = deque(maxlen=N)

rr_x = deque(maxlen=MAX_LATIDOS)
rr_y = deque(maxlen=MAX_LATIDOS)
n_latidos = 0
bpm_actual = 0
rr_actual  = 0

ser = serial.Serial(PUERTO, BAUD, timeout=1)
time.sleep(0.5)
ser.reset_input_buffer()
t0 = time.time()

# Un solo archivo CSV para toda la grabacion
nombre = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_ecg.csv"
ruta   = os.path.join(CARPETA_CSV, nombre)
archivo = open(ruta, "w", newline="")
writer  = csv.writer(archivo)
writer.writerow(["tiempo_s", "ecg", "bpm", "rr_ms", "latido"])
print(f"Grabando en: {ruta}")

fig, (ax1, ax2) = plt.subplots(
    2, 1, figsize=(11, 6), gridspec_kw={"height_ratios": [2, 1]}
)
fig.subplots_adjust(hspace=0.35)

linea_ecg, = ax1.plot([], [], lw=1.2, color="#c0392b")
ax1.set_ylabel("ECG (u.a.)")
ax1.grid(True, alpha=0.3)
titulo = ax1.set_title("ECG en tiempo real")

linea_rr, = ax2.plot([], [], "o-", lw=1, ms=4, color="#2471a3")
ax2.set_xlabel("Numero de latido")
ax2.set_ylabel("R-R (ms)")
ax2.grid(True, alpha=0.3)

texto_timer = fig.text(
    0.99, 0.01, "", ha="right", va="bottom",
    fontsize=9, color="gray"
)


def leer_serial():
    global bpm_actual, rr_actual, n_latidos
    while ser.in_waiting:
        try:
            cruda  = ser.readline().decode("utf-8", "ignore").strip()
            partes = cruda.split(",")
            if len(partes) != 4:
                continue

            # Ignorar linea de fin enviada por la Pico
            if partes[0] == "FIN":
                return

            ecg        = float(partes[0])
            bpm_actual = int(partes[1])
            rr_ms      = int(partes[2])
            latido     = partes[3]

            t = time.time() - t0
            tiempos.append(t)
            valores.append(ecg)
            writer.writerow([f"{t:.4f}", ecg, bpm_actual, rr_ms, latido])

            if latido == "1" and rr_ms > 0:
                n_latidos += 1
                rr_x.append(n_latidos)
                rr_y.append(rr_ms)
                rr_actual = rr_ms

        except (ValueError, UnicodeDecodeError):
            continue


def actualizar(frame):
    transcurrido = time.time() - t0
    restante     = max(0, DURACION_SEG - transcurrido)

    # Tiempo agotado -> cerrar todo
    if transcurrido >= DURACION_SEG:
        texto_timer.set_text("Grabacion finalizada")
        ani.event_source.stop()
        plt.close()
        return linea_ecg, linea_rr, titulo, texto_timer

    leer_serial()

    texto_timer.set_text(f"Tiempo restante: {int(restante)}s")

    if tiempos:
        linea_ecg.set_data(tiempos, valores)
        ax1.set_xlim(tiempos[0], tiempos[-1] + 0.01)
        ymin, ymax = min(valores), max(valores)
        m = (ymax - ymin) * 0.1 + 1
        ax1.set_ylim(ymin - m, ymax + m)
        titulo.set_text(
            f"ECG en tiempo real   |   BPM: {bpm_actual}   |   R-R: {rr_actual} ms"
        )

    if rr_y:
        linea_rr.set_data(rr_x, rr_y)
        ax2.set_xlim(rr_x[0] - 0.5, rr_x[-1] + 0.5)
        ax2.set_ylim(min(rr_y) - 50, max(rr_y) + 50)

    return linea_ecg, linea_rr, titulo, texto_timer


ani = FuncAnimation(fig, actualizar, interval=40, blit=False,
                    cache_frame_data=False)

try:
    plt.show()
finally:
    archivo.close()
    ser.close()
    print(f"Listo. Datos guardados en: {ruta}")