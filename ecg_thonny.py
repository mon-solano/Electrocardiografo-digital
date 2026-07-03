from machine import ADC, Pin
import utime
import math

# ---------- PINES ----------
PIN_ECG    = 26   # GP26 = ADC0
PIN_LO_POS = 14   # LO+
PIN_LO_NEG = 15   # LO-

# ---------- MUESTREO ----------
FS         = 250
PERIODO_US = 1_000_000 // FS   # 4000 us

# ---------- FILTRO NOTCH 60 Hz (biquad IIR) ----------
F0 = 60.0
Q  = 30.0

def init_notch():
    w0    = 2.0 * math.pi * F0 / FS
    c     = math.cos(w0)
    alpha = math.sin(w0) / (2.0 * Q)
    a0    = 1.0 + alpha
    nb0   =  1.0 / a0
    nb1   = -2.0 * c / a0
    nb2   =  1.0 / a0
    na1   = -2.0 * c / a0
    na2   = (1.0 - alpha) / a0
    return nb0, nb1, nb2, na1, na2

nb0, nb1, nb2, na1, na2 = init_notch()

nx1 = 0.0; nx2 = 0.0
ny1 = 0.0; ny2 = 0.0

def notch(x):
    global nx1, nx2, ny1, ny2
    y   = nb0*x + nb1*nx1 + nb2*nx2 - na1*ny1 - na2*ny2
    nx2 = nx1; nx1 = x
    ny2 = ny1; ny1 = y
    return y

# ---------- PASA-ALTAS (quita DC y deriva) ----------
ALPHA_HP = 0.995
# El ADC de la Pico da 0-65535, el Arduino daba 0-1023
# Escalamos el valor inicial de baseline al rango 16-bit
baseline = 32768.0

# ---------- DETECCION R / BPM / R-R ----------
pico_max      = 0.0
umbral        = 0.0
en_pico       = False
t_ultimo_r    = 0
REFRACTARIO_MS = 250

bpm      = 0.0
ultimo_rr = 0

N_PROM = 5
rr_buf  = [0] * N_PROM
idx_rr  = 0
rr_lleno = False

def detectar_r(s, ahora_ms):
    global pico_max, umbral, en_pico, t_ultimo_r
    global bpm, ultimo_rr, idx_rr, rr_lleno

    latido = False

    if s > pico_max:
        pico_max = s
    else:
        pico_max *= 0.999

    umbral = pico_max * 0.6

    if (not en_pico) and (s > umbral) and ((ahora_ms - t_ultimo_r) > REFRACTARIO_MS):
        en_pico = True
        latido  = True

        if t_ultimo_r > 0:
            ultimo_rr    = ahora_ms - t_ultimo_r
            rr_buf[idx_rr] = ultimo_rr
            idx_rr = (idx_rr + 1) % N_PROM
            if idx_rr == 0:
                rr_lleno = True

            n    = N_PROM if rr_lleno else idx_rr
            suma = sum(rr_buf[:n])
            if suma > 0:
                bpm = 60000.0 * n / suma

        t_ultimo_r = ahora_ms

    if en_pico and s < umbral * 0.6:
        en_pico = False

    return latido

# ---------- HARDWARE ----------
adc    = ADC(Pin(PIN_ECG))
lo_pos = Pin(PIN_LO_POS, Pin.IN)
lo_neg = Pin(PIN_LO_NEG, Pin.IN)

# ---------- LOOP PRINCIPAL ----------
t_proximo = utime.ticks_us()

while True:
    # Temporizacion fija
    if utime.ticks_diff(utime.ticks_us(), t_proximo) < 0:
        continue
    t_proximo = utime.ticks_add(t_proximo, PERIODO_US)

    ahora_ms = utime.ticks_ms()

    # Electrodo suelto
    if lo_pos.value() == 1 or lo_neg.value() == 1:
        print("0,0,0,0")
        pico_max *= 0.95
        continue

    crudo = adc.read_u16()        # 0–65535

    # 1) Notch 60 Hz
    f = notch(float(crudo))

    # 2) Pasa-altas: quita DC y deriva
    baseline = ALPHA_HP * baseline + (1.0 - ALPHA_HP) * f
    ac = f - baseline

    # 3) Deteccion de R
    latido = detectar_r(ac, ahora_ms)

    # 4) Salida CSV: ecg,bpm,rr,latido
    print(f"{ac:.1f},{int(bpm)},{ultimo_rr},{1 if latido else 0}")