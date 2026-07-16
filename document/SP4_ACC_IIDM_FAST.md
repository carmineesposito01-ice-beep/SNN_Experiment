# SP4 — ACC-IIDM fast (recuperare l'Fmax)

> Doc di processo. Spec: `docs/superpowers/specs/2026-07-16-acc-iidm-fast-design.md` · piano
> `docs/superpowers/plans/2026-07-16-acc-iidm-fast.md`. Stato: **variante L chiusa (non viabile) → si va a M**.

## Problema (SP3, misurato)
`Donatello_ACC_IIDM` in fixed sintetizza a **2,0 MHz** (WNS −373 ns @8 MHz, timing non chiude). Path critico
`pR_idx_reg → acc_3_reg`, **1077 livelli logici**, di cui **CARRY4 = 820 (76%)** dai divisori digit-recurrence
combinatori, **incatenati** (`s_star` → `z=s_star/s_safe` → `a_iidm` → `dd`…). Bersaglio: **≥ 11,65 MHz** (pari
alla SNN). Studio A/B: **L (reciproci a LUT) prima, poi M (time-mux)**; si decide sui dati.

## Variante L — reciproci a LUT: COSTRUITA e SCARTATA sui dati
Idea: ogni `1/x` → `sqrt` nativa dove serve + **reciproco a LUT 1-D** (`acc_recip_lut`) + moltiplica; i divisori
sono limitati lontano da zero. Infrastruttura (tutta committata, corretta, riusabile):
- `acc_recip_lut.m` — reciproco 1/x via LUT 1-D + interp (modello `snn_decode_lut`). Provato: costruzione
  corretta (v0/b mostrano la firma 1/N² dell'interpolazione lineare).
- `acc_types.recipN` (0 = `divide()` SP3, >0 = reciproco-LUT) + `acc_div` che sceglie la strategia. **SP3
  invariato** (`run_plant_parity` 0.00e+00, `acciidm_test` dmax=0). Review-catch: il divisore **costante** `DT`
  resta `divide()` (guardia `nargin>=6`).
- `acc_sweep_kernel` + `build_acc_sweep_mex` — kernel MEXato (1 MEX per `recipN`): lo sweep passa da **~6 h a
  12 s**, bit-identico all'interpretato (max|diff|=0).

### Il verdetto (sweep sul dataset intero, 60 traj)
| N | E_L p99 | E_L max | passa (budget p99<0.272, max<1.484) |
|---|---|---|---|
| 16 | 1.51 | 3.77 | no |
| 32 | 0.79 | 4.09 | no |
| 64 | 0.59 | 4.09 | no |
| 128 | 0.61 | 4.14 | no |
| 256 | 0.64 | 4.14 | no |

**Nessuna N rispetta il budget.** E — più importante — **l'errore NON converge con N**: il p99 tocca il fondo a
~0.59 (N=64) e poi *peggiora*, il max resta **piatto a ~4 m/s²**. Un errore di sola risoluzione LUT scenderebbe
~16× da N=32 a N=256; qui è piatto → errore **strutturale, N-indipendente**.

### Causa: saturazione ESCLUSA, root-cause non stabilita
Sospetto iniziale = saturazione di range (firma tipica del max piatto). **Verificato e smentito** (range reali sul
dataset):

| divisore | LUT [lo,hi] | reale [min,max] | satura |
|---|---|---|---|
| 2·sab | [1.74, 2.64] | [1.740, **2.646**] | sì, **0.006** (0.2%, baco reale ma innocuo) |
| v0 | [8, 45] | [24.4, 32.0] | no |
| b | [0.5, 3] | [1.19, 2.05] | no |
| s_safe | [2, 150] | [2, 150] | no |

La micro-saturazione di `2·sab` (allargare la LUT a `[1.74, 2.65]`) **non spiega** 4 m/s². Root-cause non
stabilita: o un baco fixed-point nel reciproco-per-moltiplica, o l'**amplificazione intrinseca** — l'errore di
`1/s_safe` vicino a `s_safe=2` (dove `1/x` è più curvo) moltiplicato per `s_star` (fino a 465) → `z` → `z²` →
`a_z`. Non è stata inseguita oltre: la decisione non ne dipende (vedi sotto).

## Decisione: → M (time-mux dell'IIDM)
Presa sui dati (era il piano: «se nessuna N passa → è il dato che motiva M»). Argomento che va **oltre**
bug-vs-fondamentale: un **reciproco approssimato che alimenta un'amplificazione `z²` è fragile per costruzione**.
**M — divisione sequenziale ESATTA — è bit-identica** all'IIDM fixed di SP3 (`dmax=0`, zero errore
d'approssimazione) e **scavalca l'intera classe di problema** (niente LUT, niente amplificazione, niente range).
È anche la variante preferita dall'utente.

**Cosa L insegna a M:** le 5 divisioni vanno **sequenziate**, non approssimate. Il time-mux dell'IIDM (FSM
multi-ciclo, ~341 clock/control-step disponibili) spezza la catena combinatoria mantenendo la matematica esatta.
M avrà il suo **brainstorming → spec → piano** (redesign FSM, merita contesto pulito).

## File (variante L, committati — riusabili se L verrà ripresa)
`acc_recip_lut.m` · `acc_sweep_kernel.m` · `build_acc_sweep_mex.m` · `run_acc_recip_sweep.m` · `acc_types.recipN`
+ `acc_div` in `acc_iidm_open.m`. Commit `457aa6c4`…`e2cb8062`.
