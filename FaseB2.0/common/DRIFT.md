# Deriva del controllore scelto — Fase B2.0 (T5)

**Cosa misura.** Di quanto l'accelerazione prodotta dal **blocco deployato su FPGA** si scosta
dall'ideale, sul dataset, in **open-loop** (ogni control-step valutato in modo indipendente sugli
ingressi registrati — nessun accumulo d'anello). L'accel è la grandezza rilevante per la sicurezza:
è ciò che pilota il veicolo; i 5 parametri IDM contano solo a valle, attraverso l'IDM.

## Blocco vs ideale

| | Normalizzazione | Forward SNN | Decode | IIDM |
|---|---|---|---|---|
| **Blocco** (`Donatello_SNN_IIDM`, su FPGA) | `local_normalize` **FISSA** | B2 time-mux | LUT-64 | R17 |
| **Ideale** (riferimento) | `snn_normalize` **float** | B2 time-mux | LUT-64 | R17 |

L'**unica** differenza è la normalizzazione: fissa nel blocco (aritmetica a virgola fissa, con i suoi
arrotondamenti interni) vs float nel riferimento. La deriva è quindi la **quantizzazione dello stadio
di normalizzazione**, propagata a valle fino all'accel. Tutto il resto (pesi, forward, decode LUT-64,
IIDM R17) è identico fra i due lati.

## Metodo

- **Blocco** = `acciidm_m_traj` (golden fedele: `local_normalize` + ingresso tenuto, clock-per-clock).
- **Ideale** = `snn_traj_b2` (`snn_normalize`) → `snn_decode_lut(·,64)` → `collect_step` (IIDM).
- **Fase 0 (cancello):** prima di fidarsi del golden, lo si confronta clock-per-clock con il blocco
  **reale** `Donatello_SNN_IIDM` della libreria, in streaming Simulink → `dmax = 0`. Il golden **è**
  il blocco scelto. Senza questo, la deriva sarebbe attendibile solo per supposizione.
- **Fase 1:** `|Δaccel|` su tutto `test_dataset.mat` (60 traiettorie, 60 000 control-step).
- Riproduzione: `matlab -batch "addpath('FaseB2.0/common'); drift_chosen"` → `drift_chosen.mat`.

## Numeri

Deriva sull'accel, controllore scelto `Donatello_SNN_IIDM` vs ideale float
(`test_dataset.mat`, 60 traiettorie, 60 000 control-step):

| statistica | `\|Δaccel\|` [m/s²] |
|---|---|
| max | **0.9766** |
| p99 | **0.1875** |
| mediana | **0** |
| media | **0.0168** |

## Interpretazione

Il metro è il **budget E_snn** = footprint in accel della quantizzazione della rete **già accettata**
(da `acc_types.m`, 60 000 campioni): `p99 = 0.2721`, `max = 1.4843` m/s².

| | deriva | budget E_snn | deriva / budget |
|---|---|---|---|
| p99 | 0.1875 | 0.2721 | **68.9 %** |
| max | 0.9766 | 1.4843 | **65.8 %** |

- La **mediana è 0**: nella maggior parte dei control-step il blocco fisso e l'ideale float danno
  accel **bit-identica**.
- Anche il **caso peggiore** (max 0.977) resta **sotto** il peggior footprint di quantizzazione della
  rete (1.484). La `local_normalize` fissa **non aggiunge deriva oltre** a quella già accettata quando
  si è quantizzata la rete.
- **Conseguenza di deploy:** confermato che il blocco può andare su FPGA **così com'è** (normalize
  FISSA sull'hardware, I/O fisici). La deriva del deploy è dominata dalla rete stessa → trascurabile.

## Nota — deriva sui 5 parametri (bench solo-SNN)

Non è misurata qui. Il golden lato-parametri `snn_traj_champion` è **stale**: estrae dal blocco
`Donatello_Champion`, **rimosso** nel riordino a 8 blocchi (2026-07-27). La fedeltà del bench solo-SNN
(`Donatello_Tier@BALANCED`) è una **parità RTL bit-exact** (`dmax = 0`, RTL vs golden), verificata nel
suo harness (T6); la fedeltà end-to-end rilevante per la sicurezza è la deriva **sull'accel** qui sopra.
