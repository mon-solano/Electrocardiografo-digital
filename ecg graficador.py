#!/usr/bin/env python3


import sys
import os
import glob
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


ARCHIVO = "mon_1_reposo.csv"   
FS = 250.0            
VREF_MV = 3300.0        # mV, referencia del ADC
ADC_BITS = 10           
CONVERTIR_A_MV = True   

SEGUNDOS_OMITIR_INICIO = 2.0  
VENTANA_MUESTRAS = 2000        
CARPETA_SALIDA = "figuras_ecg"
# -------------------------------------------------------


def cargar(archivo):
    df = pd.read_csv(archivo)
    if "ecg" not in df.columns:
        raise ValueError(f"'{archivo}' no tiene columna 'ecg' (¿es un CSV de ecg_lector.py?)")
    ecg = df["ecg"].to_numpy(dtype=float)
    t_ms = np.arange(len(ecg)) * (1000.0 / FS)  
    return t_ms, ecg


def a_mv(ecg_cuentas):
    factor = VREF_MV / (2 ** ADC_BITS)   
    return ecg_cuentas * factor


def graficar_archivo(archivo, carpeta_salida=CARPETA_SALIDA):
    t_ms, ecg = cargar(archivo)

    inicio = int(SEGUNDOS_OMITIR_INICIO * FS)
    if inicio >= len(ecg):
        inicio = 0
    fin = inicio + VENTANA_MUESTRAS if VENTANA_MUESTRAS else len(ecg)
    fin = min(fin, len(ecg))

    t_ms = t_ms[inicio:fin]
    ecg = ecg[inicio:fin]

    if len(ecg) == 0:
        print(f"  [omitido] '{archivo}' no tiene suficientes muestras.")
        return

    y = a_mv(ecg) if CONVERTIR_A_MV else ecg
    etiqueta_y = "Amplitud (mV, referida al ADC)" if CONVERTIR_A_MV else "Amplitud (cuentas ADC filtradas)"

    plt.figure(figsize=(12, 4))
    plt.plot(t_ms - t_ms[0], y, color="black", lw=1.2)
    plt.title(f"ECG filtrado - {os.path.basename(archivo)}")
    plt.xlabel("Tiempo (ms)")
    plt.ylabel(etiqueta_y)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()

    os.makedirs(carpeta_salida, exist_ok=True)
    nombre_salida = os.path.splitext(os.path.basename(archivo))[0] + ".png"
    ruta_salida = os.path.join(carpeta_salida, nombre_salida)
    plt.savefig(ruta_salida, dpi=150)
    plt.close()
    print(f"  -> {ruta_salida}")


def main():
    
    entrada = sys.argv[1] if len(sys.argv) > 1 else ARCHIVO

    if not os.path.exists(entrada):
        print(f"No existe '{entrada}'. Edita la variable ARCHIVO al inicio del script, "
              f"o pasa la ruta como argumento: python ecg_graficador.py archivo.csv")
        sys.exit(1)

    archivos = sorted(glob.glob(os.path.join(entrada, "*.csv"))) if os.path.isdir(entrada) else [entrada]

    if not archivos:
        print("No se encontraron archivos CSV.")
        sys.exit(1)

    print(f"Procesando {len(archivos)} archivo(s)...")
    for archivo in archivos:
        try:
            graficar_archivo(archivo)
        except Exception as e:
            print(f"  [error] '{archivo}': {e}")


if __name__ == "__main__":
    main()
