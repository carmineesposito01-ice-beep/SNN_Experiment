import torch

# ===========================================================
# CF_FSNN — Configurazione Car-Following
# Base: FSNN_Project_V5 adattata per ACC-IDM (con base IIDM) + V2X + PYNQ-Z1
# Modello fisico: Ch12 Sez.12.4 Treiber & Kesting 2025
# Estensione stocastica: T(t) via processo IDM-2d (Ch12.6) — vedi IDM2D_* sotto
# ===========================================================

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
SEED   = 42

def set_seed(seed=SEED):
    import random, numpy as np
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

set_seed(SEED)

# -----------------------------------------------------------
# Rete SNN — dimensioni per car-following
# -----------------------------------------------------------
# Input V2X:  [s, v, Δv, v_leader]  → 4 segnali
# Hidden:      32 neuroni ALIF
# Output:      5 parametri IDM [v0, T, s0, a, b] (comuni a IDM/IIDM/ACC-IDM)
CF_INPUT_SIZE  = 4
CF_HIDDEN_SIZE = 32
CF_OUTPUT_SIZE = 5      # parametri IDM appresi dalla rete
CF_RANK        = 8      # low-rank recurrence U(32x8) x V(8x32)
CF_MAX_DELAY   = 6      # delay assionico max = 6 x Dt = 0.6 s ≈ Tr (Ch13)

# -----------------------------------------------------------
# Training
# -----------------------------------------------------------
BATCH_SIZE     = 64
LEARNING_RATE  = 0.001
EPOCHS         = 50
TICKS_PER_STEP = 10     # tick SNN per ogni step di simulazione Dt

# Pesi loss PINN (Ch17: gap e' MoP primario)
LAMBDA_DATA  = 1.0      # SRMSE sul gap s
LAMBDA_PHYS  = 0.1      # residuo equazione ACC-IDM (con base IIDM)
LAMBDA_OU    = 0.05     # vincolo processo OU su T (estensione IDM-2d stocastica)
LAMBDA_BC    = 1.0      # crash prevention: s >= s0

# B5 — Spike-rate regularizer (applicato 2026-05-27 post-P6_T2_full)
# Aggiunge termine (avg_spike_rate - SPIKE_RATE_TARGET)^2 al loss.
# Motivazione: P6_T2_full ha mostrato firma "dead network degenerante" — la rete
# completa E1 con spike rate ~7%, poi degenera a ~3% in E2 e esplode (catena
# ricorrenza U·V amplifica gradiente concentrato su pochi neuroni attivi).
# Questo termine spinge attivamente la rete a mantenere ~15% di spike rate.
# Calibrazione: (spike_rate-target)^2 tipicamente in [1e-4, 1e-2].
# LAMBDA_SR=0.5 → contributo al loss in [5e-5, 5e-3], comparabile a L_phys (0.1*~0.2).
SPIKE_RATE_TARGET = 0.15    # 15% — centro della zona sana 10-25% (ch22 §22.5)
LAMBDA_SR    = 0.5

# -----------------------------------------------------------
# Simulazione ACC-IDM — parametri fisici (Ch12 Sez.12.4)
# -----------------------------------------------------------
DT = 0.1    # passo temporale [s], allineato a V2X 10 Hz

# Parametri per scenario highway
IDM_HWY = dict(v0=33.3, T=1.2, s0=2.5, a=1.1, b=1.5, delta=4)
# Parametri per scenario urbano
IDM_URB = dict(v0=15.0, T=1.0, s0=2.0, a=1.5, b=2.0, delta=4)
# Parametri per truck
IDM_TRK = dict(v0=22.2, T=1.8, s0=3.0, a=0.5, b=1.0, delta=4)

# IDM-2d (Ch12 Sez.12.6): banda stocastica su T del modello IDM
# Estensione che rende T(t) un processo stocastico OU invece di costante.
# Applicabile a IDM, IIDM e ACC-IDM — è una proprietà del time-gap, non del modello.
# I prefissi IDM2D_ sono mantenuti come riferimento al testo originale (Treiber Ch12.6).
IDM2D_T1  = 0.8    # T_min [s]
IDM2D_T2  = 1.6    # T_max [s]  ->  DeltaT = 0.8 s
IDM2D_TAU = 30.0   # tempo di correlazione del processo OU su T [s]

# -----------------------------------------------------------
# ACC-IDM con base IIDM (Ch12, Sez. 12.4 — modello fisico scelto)
# -----------------------------------------------------------
ACC_COOLNESS = 0.99   # c: peso della CAH (fisso — non predetto dalla rete)
                      # c≈1 → quasi sempre CAH attiva → risposta anticipatoria
ACC_AL_TAU   = 1.0    # tau filtro OU stima a_l dal segnale V2X [s]
                      # τ=1s → risposta rapida al rumore di differenziazione

# -----------------------------------------------------------
# Scenari cut-in (UC2 — Abrupt Cut-In)
# -----------------------------------------------------------
CUT_IN_RATIO   = 0.20   # frazione scenari con cut-in nel dataset (20%)
CUT_IN_S_MIN   = 5.0    # gap minimo subito dopo il cut-in [m]
CUT_IN_S_MAX   = 15.0   # gap massimo subito dopo il cut-in [m]
CUT_IN_DV_MAX  = 5.0    # massima differenza di velocita' al cut-in [m/s]

# Rumore OU sui segnali (modello errori umani — Ch13)
NOISE_GAP_REL = 0.10    # Vs = 10%  errore relativo su s
NOISE_VEL_OPT = 0.01    # sigma_r = 0.01 1/s  (errore stima v_leader)
NOISE_ACCEL   = 0.10    # sigma_a = 0.1 m/s^2  (rumore accelerazione)
NOISE_TAU_S   = 20.0    # tau correlazione errore gap [s]
NOISE_TAU_V   = 20.0    # tau correlazione errore vel leader [s]
NOISE_TAU_A   = 1.0     # tau correlazione rumore accel [s]

# Simulazione packet loss V2X (validato a 96% auto-healing in FSNN_V5)
V2X_PACKET_LOSS = 0.02  # probabilita' di frame mancante per step

# -----------------------------------------------------------
# Normalizzazione input SNN → [0, 1]
# -----------------------------------------------------------
NORM_S_MAX  = 150.0   # gap [m]
NORM_V_MAX  =  40.0   # velocita' ego [m/s]
NORM_DV_MAX =  20.0   # |Deltav| [m/s]
NORM_VL_MAX =  40.0   # velocita' leader [m/s]

# -----------------------------------------------------------
# Dataset sintetico ACC-IDM
# -----------------------------------------------------------
N_SCENARIOS_TRAIN = 5000    # traiettorie training
N_SCENARIOS_VAL   =  500    # traiettorie validazione
N_SCENARIOS_TEST  =  500    # traiettorie test
SIM_DURATION      = 120.0   # durata per traiettoria [s]
WARMUP_DURATION   =  20.0   # warmup escluso dalla loss (transitorio iniziale)

# Distribuzione scenari (somma = 1.0)
SCENARIO_MIX = dict(highway=0.50, urban=0.30, truck=0.10, mixed=0.10)
