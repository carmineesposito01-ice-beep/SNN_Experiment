# Fase ②-HDL — Metodologia, Stato e Procedura di Ripresa

> **Worktree separato:** `D:\Project_MBSE\1.Reti Neurali\Rete_SNN_Test\CF_FSNN\.worktrees\Simulink_Importer`
> **Branch:** `Simulink_Importer` · **Base:** HEAD `9010d3d` (closed_loop_demo)
> `core/` PyTorch **congelato read-only** (letti solo i pesi). MATLAB **R2026a** gira headless
> (`C:\Program Files\MATLAB\R2026a\bin`). **Vivado / simulatore HDL: NON installati in locale**
> (Vivado in installazione ~3h → sintesi vera e cosim rinviate).

---

## §0 RIPRESA RAPIDA (leggi prima questo)

**Stato in una riga:** RTL VHDL **bit-accurato** (garanzia HDL Coder vs il fixed MATLAB — **NON ancora
cosim'd**) generato per Donatello, single-source da `snn_core`. **po2→shift FATTO** → moltiplicatori
**27.840 → 32 in STIMA** (premessa 0-DSP; **NON ancora sintetizzato**), comportamento preservato (parità
double 2e-6, errore fixed **≤0.028 = max sui 5 parametri**, v0 il peggiore). Resta il **lato LUT**
(adder/mux, alti in STIMA) e il **verdetto di sintesi VERO** (serve Vivado — che include il simulatore,
quindi UNA installazione sblocca sia la sintesi ④ sia la cosim ③).

**Prossima azione (quando Vivado è pronto):** sintetizzare l'RTL Donatello
(`matlab/codegen/snn_hdl_Donatello/hdlsrc/snn_hdl_Donatello.vhd` — rigenerabile) su **Zynq-7020
`xc7z020clg400-1`** per numeri DSP/LUT/FF/timing REALI. La resource-report di HDL Coder è solo una
STIMA (pessimista sui DSP). Se sta / è vicino → area OK. Se LUT troppo alti → streaming ÷32 (§8 punto 2).

**Comandi di verifica (dalla dir `matlab/`, MATLAB su PATH):**
```
matlab -batch "cd('D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab'); run_parity_tests"                 % double vs golden PyTorch (~2e-6 — DEVE passare)
matlab -batch "cd('D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab'); run_fixed_sweep"                  % errore fixed vs frac bits (convergenza a f=13)
matlab -batch "cd('D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab'); gen_hdl_tops; run_hdl_verify"     % wrapper HDL vs golden (≤0.028)
matlab -batch "cd('D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab'); make_hdl('Donatello')"            % rigenera RTL + report risorse
```

**Regola d'oro (cancello 1:1):** ogni modifica a `snn_core.m`/`snn_types.m` → rilancia
`run_parity_tests` (double DEVE restare ~2e-6) PRIMA di procedere. È così che è stato trovato il bug
leak-division e verificato ogni passo.

**Decisioni che SUPERANO `SIMULINK_IMPORT_DESIGN.md` (2026-07-06)** — quel doc precede questa fase:
- **Qm.n uniforme `f=13`** (non il floor `f=5` del design §1/§8). Uniforme e generoso su tutti i champion →
  **dissolve il prerequisito** «ri-profilare i range per-stato dell'eventprop prima del fixed-point» (design §7):
  il fixed-point su Donatello/Michelangelo (eventprop) è GIÀ fatto a f=13, errore ≤0.028. `snn_types('fixed',nfrac)`
  resta parametrico → il floor f=5 vale se un domani si vuole comprimere, ma NON è l'operating point attuale.
- **Generazione RTL via `make_hdl.m` → `codegen -config hdl`** sui wrapper `snn_hdl_<name>.m`, **NON** `makehdl`
  sul `.slx` (design §5.2/§7): il flow Simulink-HDL non aiuta con un MATLAB Function block (§9). Il blocco
  `snn_champions_lib.slx` resta l'**artefatto comportamentale** (double), non il sorgente HDL.

---

## §1 Obiettivo
Portare i 4 champion SNN (Donatello, Michelangelo, Raffaello, Leonardo) su FPGA **PYNQ-Z1 (Zynq-7020)**
come RTL **generato dallo STESSO codice** che ha la parità bit-accurata col PyTorch — non una
riscrittura a mano. Delivery finale = HDL sintetizzabile e 0-DSP (pesi potenza-di-2 → shift).

## §2 La catena 1:1 (4 anelli, ognuno con la sua garanzia)
```
PyTorch(fp32) ─①─ MATLAB double ─②─ MATLAB fixed(fi Q?.13) ─③─ VHDL/RTL ─④─ silicio
   parità 2e-6       quantizz. ≤0.028      HDL Coder BIT-ESATTO      sintesi (Vivado)
```
- **①** FATTO: `run_parity_tests` ~2e-6 (roundoff float).
- **②** quantizzazione INEVITABILE ma piccola (≤0.028 su v0 a f=13) — **non** è un fallimento di conversione.
- **③** HDL Coder garantisce RTL bit-esatto vs il fixed MATLAB; stream/share/shift **preservano i bit**.
- **④** NON fatto (serve Vivado, non locale). Il TB auto (`raw_expected.dat`) proverà ③ in cosim.

## §3 I tre livelli (dove si agisce — regola)
1. **VHDL a mano → MAI.** Rompe la garanzia 1:1, non riproducibile, e ora **non verificabile** (niente simulatore).
2. **Config HDL Coder → SÌ (leva primaria).** Bit-preserving.
3. **Sorgente MATLAB → SÌ, chirurgico.** Solo modifiche behavior-preserving, gated dalla parità.

> Il blocco plug&play `snn_champions_lib.slx` è l'artefatto **COMPORTAMENTALE** (double, decode inline):
> resta com'è, **NON** è il sorgente HDL. Il sorgente HDL è `snn_core` (type-parametrizzato).

## §4 Architettura del core (`matlab/snn_core.m`)
- **Type-parametrizzato** via `snn_types('double'|'fixed', nfrac)`: stesso codice per parità (double) e HDL (fi).
- 1 chiamata = 1 control-step = `nt=10` tick interni; stato `persistent` (V, fatigue, s_prev, V_LI, x_buf);
  `snn_core([],[],T,'reset')` azzera. `snn_entry(dt,x_phys,W)` = normalize → core → decode (double).
- **Per tick:** ring-buffer input → `t_lr = Vr·s_prev` (conditional-add, spike∈{0,1} → nessuna mult) →
  **loop per-neurone** { corrente sinaptica via `po2shift`, ricorrenza `U·t_lr` via `po2shift`, membrana
  leak-shift, spike `>=`, fatigue, soft-reset, readout `Wout` conditional-add } → LI leak-shift.
- **Helper chiave:**
  - `leaky(x,n)` — leak bit-shift (fi: `x - bitsra(x,n)`; double: `x - x/2^n`). **Sostituisce** la divisione
    fi `./ld` (causa del bug plateau, §9).
  - `po2shift(sgn,k,w,x,Tw)` — moltiplicazione per peso po2 come **SHIFT** (fi: `sgn·bitshift(cast(x,Tw),k)`
    nel tipo **LARGO** `T.accw`; double: `w·x`). Esponenti/segni `Kfc/Sfc/KU/SU` calcolati nell'header da
    COSTANTI (foldati da HDL Coder; **niente `log2` nel datapath**).
- **Comparatore spike `>=`** (`snn_core.m` §3c): baseline PyTorch usa `>=` (match esatto), eventprop usa
  `>` (deviazione misura-nulla in float; da rivalutare in fixed se i pareggi contano — §9).
- **Tipi fixed** (`snn_types.m`, default `nfrac=13`): V=Q5.13, fatigue=Q3.13, acc=Q5.13, **accw=Q8.17**
  (+4 frac per shift po2 esatti), raw=Q7.13, w=Q2.13 (po2 esatti).

## §5 Trajectory ottimizzazione area (Donatello, STIMA HDL Coder)
| step | mult | add | mux | clock |
|---|---|---|---|---|
| naive `makehdl` | 27.840 | 67.100 | 29.170 | 1× |
| +`LoopOptimization='StreamLoops'` (tick ÷10) | 2.752 | 7.084 | 3.472 | 10× |
| +refactor loop per-neurone | 1.344 | 3.476 | 3.472 | 10× |
| +conditional-adds (Vr, Wout gated) | 672 | 3.476 | 10.768 | 10× |
| **+po2→shift (ATTUALE)** | **32** | **5.524** | **11.536** | **10×** |

Config in `make_hdl.m`: `LoopOptimization='StreamLoops'`, `ConstantMultiplierOptimization='CSD'`,
`ResourceSharing=32`, `ShareAdders=true`, TargetLanguage VHDL, TB auto-generato.

## §6 Stato attuale (fatto / pendente)
- ✅ **po2→shift**: 32 moltiplicatori (i 32 residui = scalari gated `si·eth`/`si·tjump`, ≪ 220 DSP).
- ✅ RTL bit-accurato generato per **Donatello** (+ testbench auto vs golden), 0 errori codegen.
- ✅ Comportamento: parità double 2e-6; errore fixed ≤0.028 (v0) su tutti e 4 (Leonardo NON regredito).
- ⏳ **Lato LUT**: adder 5.524 + mux 11.536 (barrel-shift + wide-acc + conditional-add) — alti in STIMA.
- ⏳ **Streaming ÷32** dei neuroni: BLOCCATO da RAM-mapping (accessi non-scalari) — §8 punto 2 / §9.
- ⏳ **Vivado/sintesi**: non locale (in installazione). Nessun simulatore → **niente cosim** ancora.
- ⏳ **Decode (sigmoid)**: ESCLUSO dall'RTL → **LUT in fabric** (deciso), non ancora implementato.
- ⏳ **Altri 3 champion**: wrapper generati; RTL prodotto solo per Donatello.

## §7 File (worktree)
- **Sorgente HDL:** `matlab/snn_core.m` (mod), `matlab/snn_types.m` (mod, +`accw`),
  `snn_normalize.m`, `snn_decode.m`, `snn_entry.m`.
- **Wrapper baked + `coder.const`:** `matlab/snn_hdl_<name>.m` (generati da `gen_hdl_tops.m`).
- **Driver HDL:** `matlab/make_hdl.m` (config + `codegen -config hdl` + TB + summary risorse).
- **Verifiche:** `run_parity_tests.m` (double), `run_fixed_parity.m` / `run_fixed_sweep.m` (fixed Qm.n),
  `run_hdl_verify.m` (wrapper HDL).
- **Diagnostica:** `diag_ranges.m` (range segnali interni), `diag_quant.m` (quantizzazione stato vs bug).
- **Export pesi:** `scripts/export_champions.py` → `matlab/champions_export.mat` (po2 reale, delays, golden).
- **Generato, NON versionato** (`matlab/.gitignore`): `matlab/codegen/` (RTL in `snn_hdl_<name>/hdlsrc/`). HDL Coder
  emette più file: top `snn_hdl_<name>.vhd`, stadio/i pipeline `snn_hdl_<name>p<N>.vhd` (dal delay-balancing del
  clock-rate), test-config `*_tc.vhd`, package `*_pkg.vhd`, testbench `*_tb.vhd` + vettori `xn.dat`/`raw_expected.dat`.

## §8 Prossimi passi
1. **[Vivado pronto] Sintesi vera** RTL Donatello su Zynq-7020 (`xc7z020clg400-1`): crea progetto, aggiungi
   `hdlsrc/snn_hdl_Donatello.vhd` + `*_pkg.vhd`, run synthesis → DSP/LUT/FF/timing reali. Decide se serve altro.
2. **Se LUT troppo alti → streaming ÷32 (refactor RAM-friendly):** `x_buf` come **circular-buffer con
   puntatore** (niente `x_buf(:,2:end)=...`); accessi **SCALARI** a V/fatigue/s_prev; abbassa `RAMThreshold`;
   poi `coder.hdl.loopspec('stream')` sul loop neuroni. Sblocca RAM-mapping → clock ~320×, adder→~170, mux→~360.
3. **Decode → LUT** (`coder.approximate` su σ) come stadio separato + parità decode-approx vs esatto.
4. **Altri 3 champion:** `make_hdl('Michelangelo'|'Raffaello'|'Leonardo')`.
5. **Cosim** (quando c'è un simulatore): il TB auto verifica RTL vs golden bit-esatto (anello ③).
6. **Registrazione custom-board PYNQ-Z1** + eventuale ri-profilazione Qm.n.

## §9 Gotcha / lezioni (FONDAMENTALI — non ri-sbatterci)
- **`log2`/`double` MAI nel datapath**: HDL Coder li sintetizza (via `isnan`/`isinf` → errore). OK **solo su
  COSTANTI nell'header** (foldati, come `sh`). `po2shift` usa `Kfc/Sfc` precalcolati, non `log2` nel loop.
- **Bug leak-division (RISOLTO):** `V./ld` in fi = divisione con auto-output-type → errore
  *precision-independent* (plateau ~3.5, non migliora coi bit). Fix = `leaky` bit-shift. → i leak in HW sono
  SHIFT, non divisioni. (Diagnosi: `diag_quant.m` convergeva a 0, `fi` no → non era quantizzazione.)
- **po2 NON riconosciuti da CSD**: attraverso `struct + cast`, HDL Coder non folda i po2 in shift → 1.312
  moltiplicatori. Fix = `po2shift` esplicito (esponenti baked). **Il tool non sfrutta i vantaggi FPGA da solo
  → vanno ESPRESSI esplicitamente** (come il leak-shift). La rete non si "sbrandella": si adatta l'espressione.
- **Precisione shift**: `bitshift` nello STESSO tipo TRONCA (Leonardo → 0.95). Fix = tipo LARGO `accw`
  (+4 frac) → shift esatto, precisione preservata.
- **Streaming bloccato da RAM-mapping**: il loop neuroni non si streamma perché V/fatigue/x_buf non mappano in
  RAM (warning: "non-scalar sub-matrix access" = ring-buffer/slice; "accessed in loop region"; soglia default
  256 > 32 elementi). Serve accessi scalari + `RAMThreshold` basso.
- **Simulink-HDL flow NON aiuta con MATLAB Function block**: dentro il block gira lo stesso motore
  MATLAB-to-HDL. Beneficio solo ricostruendo a blocchi (perde single-source) → **scartato**.
- **Resource report = STIMA, non sintesi**: ignora DSP-inference (mult piccoli → LUT), LUT-packing, retiming.
  **Verdetto vero solo da Vivado.**
- **Accumulatore a larghezza fissa (codegen)**: una variabile non può cambiare tipo tra iterazioni del loop →
  usare `x(:) = ...` per forzare il tipo dichiarato (I_input, wacc, t_lr).
- **loopspec factor**: `coder.hdl.loopspec('stream', N)` con N = trip-count NON serializza (interpretato come
  parallelismo). Semantica non chiarita in R2026a → per lo streaming affidarsi prima al RAM-mapping (§8 punto 2).
