#!/usr/bin/env python3

import sys
import os
import glob
import math
import numpy as np
import pandas as pd
from scipy.signal import welch, detrend
from scipy.interpolate import interp1d

_integrar = getattr(np, "trapezoid", getattr(np, "trapz", None))

ARCHIVO = "mon_1_reposo.csv"   
SALIDA = "resumen_hrv_mon_.csv"                   
#parametros
RR_MIN = 300
RR_MAX = 2000
UMBRAL_ECT = 0.20
FS_INTERP = 4.0
LF = (0.04, 0.15)
HF = (0.15, 0.40)
MIN_LATIDOS = 5


def extraer_rr(archivo):
    df = pd.read_csv(archivo)
    faltan = {"latido", "rr_ms"} - set(df.columns)
    if faltan:
        raise ValueError(f"'{archivo}' no tiene columnas {faltan}")
    mask = (df["latido"] == 1) & (df["rr_ms"] > 0)
    return df.loc[mask, "rr_ms"].to_numpy(dtype=float)


def limpiar(rr):
    if len(rr) == 0:
        return rr
    rango = (rr >= RR_MIN) & (rr <= RR_MAX)
    rr = rr[rango]
    if len(rr) == 0:
        return rr
    keep = [True]
    for i in range(1, len(rr)):
        cambio = abs(rr[i] - rr[i - 1]) / rr[i - 1]
        keep.append(cambio <= UMBRAL_ECT)
    return rr[np.array(keep)]


def lf_hf_y_resp(rr):
    t_latido = np.cumsum(rr) / 1000.0
    t_latido = t_latido - t_latido[0]

    clase = "cubic" if len(rr) > 3 else "linear"
    f_interp = interp1d(t_latido, rr, kind=clase, fill_value="extrapolate")
    tu = np.arange(t_latido[0], t_latido[-1], 1.0 / FS_INTERP)
    if len(tu) < 8:
        return float("nan"), float("nan")

    rru = detrend(f_interp(tu))
    nseg = min(len(rru), 256)
    f, pxx = welch(rru, fs=FS_INTERP, nperseg=nseg)

    def potencia(banda):
        m = (f >= banda[0]) & (f < banda[1])
        return float(_integrar(pxx[m], f[m])) if m.any() else 0.0

    lf, hf = potencia(LF), potencia(HF)
    lf_hf = (lf / hf) if hf > 0 else float("nan")

    mhf = (f >= HF[0]) & (f < HF[1])
    resp_rpm = float(f[mhf][np.argmax(pxx[mhf])] * 60.0) if mhf.any() else float("nan")

    return lf_hf, resp_rpm


def resumir_archivo(archivo):
    nombre = os.path.splitext(os.path.basename(archivo))[0]
    try:
        rr = limpiar(extraer_rr(archivo))
    except ValueError as e:
        return dict(archivo=nombre, latidos=0, FC_bpm=np.nan, RR_medio_ms=np.nan,
                    SDNN_ms=np.nan, LF_HF=np.nan, Resp_rpm=np.nan, nota=str(e))

    if len(rr) < MIN_LATIDOS:
        return dict(archivo=nombre, latidos=len(rr), FC_bpm=np.nan, RR_medio_ms=np.nan,
                    SDNN_ms=np.nan, LF_HF=np.nan, Resp_rpm=np.nan,
                    nota="menos de 5 latidos validos tras limpieza")

    rr_medio = rr.mean()
    fc = 60000.0 / rr_medio
    sdnn = rr.std(ddof=1)
    lf_hf, resp_rpm = lf_hf_y_resp(rr)

    return dict(
        archivo=nombre, latidos=len(rr),
        FC_bpm=round(fc, 1), RR_medio_ms=round(rr_medio, 1), SDNN_ms=round(sdnn, 1),
        LF_HF=round(lf_hf, 2) if not math.isnan(lf_hf) else np.nan,
        Resp_rpm=round(resp_rpm, 1) if not math.isnan(resp_rpm) else np.nan,
        nota="",
    )


def main():
    entrada = sys.argv[1] if len(sys.argv) > 1 else ARCHIVO
    salida = sys.argv[2] if len(sys.argv) > 2 else SALIDA

    if not os.path.exists(entrada):
        print(f"No existe '{entrada}'. Edita la variable ARCHIVO al inicio del script, "
              f"o pasa la ruta como argumento: python hrv_resumen.py archivo.csv")
        sys.exit(1)

    archivos = sorted(glob.glob(os.path.join(entrada, "*.csv"))) if os.path.isdir(entrada) else [entrada]
    if not archivos:
        print("No se encontraron archivos CSV.")
        sys.exit(1)

    filas = [resumir_archivo(a) for a in archivos]
    tabla = pd.DataFrame(filas)[["archivo", "latidos", "FC_bpm", "RR_medio_ms", "SDNN_ms", "LF_HF", "Resp_rpm", "nota"]]

    with pd.option_context("display.max_rows", None, "display.width", 120):
        print(tabla.to_string(index=False))

    if salida:
        tabla.to_csv(salida, index=False)
        print(f"\nGuardado en: {salida}")


if __name__ == "__main__":
    main()
