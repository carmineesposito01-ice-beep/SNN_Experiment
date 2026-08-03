# Studio di quantizzazione per-campo (mixed-precision) — design

**Data:** 2026-07-24
**Track:** HDL / Simulink_Importer
**Stato:** design approvato a voce (2026-07-24), in attesa di review della spec scritta

---

## 1. Contesto e motivazione

Lo studio di quantizzazione a `nfrac` **unico** (chiuso, report `report/QUANTIZATION_STUDY_REPORT.pdf`) ha
stabilito che la sicurezza car-following di Donatello è invariante fino a 2 bit frazionari, che il ginocchio di
fedeltà cade attorno a 4-5 bit, e che il costo hardware scende in modo modesto e non monotono (confine DSP↔LUT,
potenza piatta). In quello studio **tutti** i tipi del core condividono lo stesso `nfrac`.

I sei tipi del core, però, non sono ugualmente sensibili. `snn_types.m` li definisce con interi diversi per campo —
V=Q5.n (potenziale di membrana), fatigue=Q3.n (soglia adattiva), acc=Q5.n e accw=Q8.(n+4) (accumulatori), raw=Q7.n
(readout), w=Q2.n (pesi a potenza di due) — e alcuni sono plausibilmente molto più tolleranti di altri alla perdita
di bit frazionari. La **precisione mista per-campo** — bit frazionari indipendenti per ciascun tipo — è lo spazio
di ottimizzazione che l'`nfrac` unico non esplora: assegnare pochi bit ai campi tolleranti e più bit ai sensibili
può ridurre l'area a pari comportamento.

Questo era il future work registrato in `docs/superpowers/specs/2026-07-24-quantization-study-design.md` §8.

## 2. Obiettivo e criteri di successo

Obiettivo: trovare l'**allocazione dei 6 nfrac per-campo** che **massimizza il risparmio d'area** mantenendo il
comportamento car-following **indistinguibile** dal full-precision — con la stessa ricchezza di metriche e lo
stesso rigore dello studio nfrac unico, rendendo poi la configurazione modificabile nel blocco e i risultati
inseriti nel report.

Successo = tutti veri:
1. Una **mappa di sensibilità per-campo** (6 curve) da misura sull'intero dataset esaustivo, non su un campione,
   che riporta l'**intero cruscotto di metriche** dello studio unico (non solo la metrica-cancello): SSM di
   sicurezza (collisioni extra, min_gap, brake_margin, max_DRAC, min_TTC), NRMSE per-parametro, e — sui casi
   inevitabili — la severità (impact_dv).
2. Una o più **configurazioni per-campo candidate** che passano il cancello comportamentale in verifica congiunta,
   con il cruscotto completo riportato per ciascuna.
3. Le **curve hardware** (risorse LUT/FF/DSP, potenza, Fmax) da sintesi reale, con lo **stesso protocollo io-timed**
   dello studio unico, su un **numero ridotto di punti** (i finalisti + i riferimenti; §5.C) per non pagare le ~12
   ore di uno sweep per-campo completo — e il **risparmio** della config area-ottimale rispetto al miglior nfrac
   uniforme a pari cancello e al full-precision.
4. La **Modalità Avanzata** nel blocco `Donatello_Tier`: una config che espone e rende modificabili i 6 nfrac
   per-campo (§5.D).
5. I risultati **aggiunti al report** dello studio di quantizzazione (§5.E).
6. Tutto **isolato** in `matlab/Quantizzation_Study/`; gli script funzionanti originali non modificati (il blocco e
   il report sono estensioni additive, non riscritture).

## 3. Il cancello (comportamentale)

Una configurazione per-campo `n = (n_V, n_fat, n_acc, n_accw, n_raw, n_w)` è **accettata** se, sull'intero dataset
esaustivo (99 traiettorie), valgono entrambe:
- **(a) sicurezza**: 0 collisioni **extra** rispetto alla baseline oracolo (le stesse 3 inevitabili dell'oracolo
  restano ammesse);
- **(b) indistinguibilità**: `max|Δgap|` rispetto al **riferimento full-precision** (tutti i campi a 13) è ≤
  **soglia = 0.5 m**.

La (b) è una **metrica nuova**: per ogni traiettoria si confronta la serie del gap prodotta dalla config `n` con
quella del riferimento full-precision, e si prende il massimo scarto assoluto su tutte le traiettorie. La soglia
0.5 m è piccola rispetto alle dinamiche degli scenari (gap 0.25–44 m) e molto più stretta del ~2.5 m che il nfrac
unico produceva al livello conservativo. È il parametro chiave dello studio e va dichiarato come tale.

Il cancello è **cheap**: richiede solo giri di anello chiuso (`qz_cl_sim` + forward a precisione mista), nessuna
sintesi. La sintesi entra in gioco solo sulle configurazioni finali (Fase C).

## 4. L'abilitatore (unico)

Oggi `snn_types(dt, nfrac)` applica un unico `nfrac` a tutti i campi. L'abilitatore, in una **copia isolata** in
`Quantizzation_Study/` (`qz_snn_types_mp.m` o equivalente), accetta i **6 nfrac per-campo** e deriva ciascun tipo
con la formula attuale di `snn_types`, sostituendo il per-campo al posto dell'unico (accw mantiene la sua
relazione `+4`: `Q8.(n_accw+4)`, per gli scorrimenti po2 esatti). Il core `snn_types.m` originale **non è toccato**.

Il forward a precisione mista riusa i mattoni dello studio unico: `qz_cl_sim` per l'anello (con lo step-forward che
usa i tipi per-campo, MEX per velocità — un MEX per configurazione), e `qz_gen_block_vhdl` per il VHDL delle
configurazioni finali, sostituendo la generazione dei tipi per-campo.

**Nota di semantica.** Al riferimento full-precision i 6 nfrac valgono tutti 13 (accw → Q8.17), e la config
per-campo deve coincidere **bit per bit** col forward storico: la parametrizzazione a 13-ovunque è un'operazione
neutra (cancello §7).

## 5. Metodo (tre fasi)

### 5.A — Sensibilità per-campo
Per ciascun campo `f` dei sei: si fissano gli altri cinque a 13 e si abbassa `n_f` da 13 fino a **1** (con lo **0**
= solo interi incluso come estensione per i campi che a 1 sono ancora ampiamente dentro il cancello). Per ogni
livello si misura, sull'intero dataset, l'**intero cruscotto** dello studio unico: la metrica-cancello
`max|Δgap|` vs full-precision e le collisioni extra (che **decidono** il floor, §3), e — per la stessa ricchezza
di prima — `min_gap`, `brake_margin`, `max_DRAC`, `min_TTC` e l'NRMSE per-parametro (che **caratterizzano**). Ne
risultano **6 curve** e, per ciascun campo, il **floor**: il minimo `n_f` che passa ancora il cancello.

Costo: solo anello chiuso. Le configurazioni sono ~6 campi × ~12 livelli = ~72, ciascuna con un MEX del forward a
precisione mista (build una volta, in background); nessuna sintesi. Se il `fi` interpretato è troppo lento, MEXare
(mai ridurre il dataset).

### 5.B — Combinazioni informate
Dai floor per-campo si compongono **poche** configurazioni candidate — non tutte le combinazioni (esaustivo =
proibitivo e inutile). Come minimo:
- l'**aggressiva**: tutti i campi al proprio floor simultaneamente;
- eventuali **back-off**: se l'aggressiva rompe il cancello in verifica congiunta (le interazioni fra campi non
  sono catturate dalla sensibilità isolata), si risale di 1 bit sul campo o sui campi che più contribuiscono allo
  scarto, finché il cancello regge.

Ogni candidata è verificata **in congiunta** sull'intero dataset con lo stesso cancello (§3).

### 5.C — Area (sintesi su punti ridotti)
Uno sweep Vivado per-campo completo (~6 campi × ~12 livelli = ~72 sintesi io-timed) costerebbe **~12 ore**; qui si
sintetizza un **insieme ridotto** di configurazioni, con lo **stesso protocollo io-timed** e le **stesse metriche**
dello studio unico (risorse LUT/FF/DSP/BRAM, potenza, Fmax):
- il **full-precision** (tutti-13) come riferimento;
- il **miglior nfrac uniforme** che passa il cancello §3 — il termine di paragone "a pari comportamento";
- i **finalisti** per-campo (l'aggressiva accettata e le eventuali varianti di back-off di §5.B);
- **opzionale**, se il tempo lo consente: i **6 config "un-campo-al-floor"** (ogni campo al suo floor, gli altri a
  13), per attribuire a ciascun campo il suo contributo hardware — l'analogo per-campo della curva
  risorse-vs-nfrac dello studio unico.

Si riportano risorse e potenza di ciascuno e il **risparmio** della config area-ottimale rispetto ai due
riferimenti (miglior uniforme e full-precision). VHDL a precisione mista da `qz_gen_block_vhdl` (generazione dei
tipi per-campo); sintesi con `qz_sweep_nfrac.sh`-style e il tooling `study_tradeoff/common/*.tcl`. Determinismo di
sintesi (thread/seme fissi) come nello studio unico.

### 5.D — Modalità Avanzata nel blocco
Dopo la scelta della config area-ottimale, il blocco `Donatello_Tier` guadagna una **Modalità Avanzata** che
espone e rende modificabili **tutti i 6 nfrac per-campo**, non il solo bit unico.

⚠️ **Vincolo Simulink noto** (dallo studio unico): un nfrac come **mask-parameter vivo** (word-length parametrico)
NON aggancia attraverso il Variant Subsystem, e la via a **varianti discrete** (usata per il menu NFRAC 13/8/5/2)
è impraticabile qui — 6 campi liberi darebbero un'esplosione combinatoria di varianti. La Modalità Avanzata usa
quindi una **mask auto-modificante**: una checkbox "Avanzata" che, quando attiva, mostra 6 campi (uno per tipo) e,
all'applicazione, un callback rigenera la chart della variante attiva coi **tipi per-campo cotti concreti**
(stessa logica di sostituzione di `qz_gen_block_vhdl`, ma per-campo). Tipi concreti → nessun problema di
risoluzione. Il menu NFRAC semplice (13/8/5/2) resta come Modalità Base (imposta i 6 nfrac uguali).

Cancelli: a tutti-13 la Modalità Avanzata coincide **bit per bit** col forward storico (no-op); una config
per-campo nota (es. i floor) produce il comportamento atteso e genera VHDL valido; il menu Base resta invariato.

### 5.E — Estensione del report
I risultati (curve di sensibilità per-campo, config area-ottimale, risparmio hardware) sono **aggiunti al report**
esistente `report/QUANTIZATION_STUDY_REPORT.{md,pdf}` come **nuova sezione**, dallo stesso generatore
(`scripts/build_quantization_report.py`, sorgente unica): nuovi TSV per-campo → nuove figure e tabelle → nuova
sezione, con lo stesso register e gli stessi cancelli di qualità (numeri ancorati, determinismo, audit).

## 6. Output

- Le **6 curve di sensibilità** per-campo, ciascuna col cruscotto completo (`max|Δgap|`, collisioni extra,
  `min_gap`, `brake_margin`, `max_DRAC`, `min_TTC`, NRMSE per-parametro) + i 6 floor.
- La **configurazione per-campo area-ottimale** (i 6 nfrac) e le eventuali varianti, col cruscotto completo, la
  **severità** sugli inevitabili e il verdetto del cancello.
- Le **risorse/potenza/Fmax** dell'insieme ridotto (§5.C) e il **risparmio** vs miglior uniforme e full-precision.
- La **Modalità Avanzata** nel blocco `Donatello_Tier` (§5.D).
- Il **report esteso** (§5.E): nuova sezione mixed-precision in `report/QUANTIZATION_STUDY_REPORT.{md,pdf}`, più il
  doc sorgente `matlab/Quantizzation_Study/QZ_CARFOLLOWING_STUDY.md` aggiornato.

## 7. Cancelli (vincolanti)

- **Cancello di isolamento**: `git diff` sugli originali (`snn_types.m`, `snn_core.m`, `qz_cl_sim.m`, …) resta vuoto.
- **Cancello bit-exact @ full-precision**: la config per-campo a tutti-13 (accw→Q8.17) coincide bit per bit col
  forward storico (dmax=0 sul dataset) — prova che la parametrizzazione per-campo è un no-op al riferimento.
- **Rilevatore comportamentale provato nei due sensi**: il cancello §3 deve **accettare** una config buona nota
  (es. tutti a 8, dallo studio unico) e **rifiutare** una config cattiva nota (es. un campo a 0 che sfonda la
  soglia). Un cancello mai visto fallire non è un cancello.
- **Modalità Avanzata bit-exact @ full-precision**: la variante rigenerata a tutti-13 coincide bit per bit col
  blocco storico (come il menu NFRAC a n13, dmax=0); il menu Base (13/8/5/2) resta invariato; una config per-campo
  nota genera VHDL valido (time-mux, DualPortRAM).
- **Report**: numeri ancorati ai nuovi TSV, `.md` byte-stabile su due build, audit avversariale (come per lo
  studio unico).
- **Dataset, mai campione**: ogni misura sull'intero dataset esaustivo; riportare quanti su quanti.

## 8. Rischi e note

- **Interazioni fra campi**: la sensibilità isolata (5.A) assume gli altri campi a 13; l'aggressiva li abbassa
  tutti insieme. Le interazioni (es. due campi tolleranti che insieme sfondano) sono catturate **solo** dalla
  verifica congiunta (5.B) — che è quindi obbligatoria, non opzionale.
- **Semantica di accw**: accw porta `+4` frazionari sul suo nfrac (scorrimenti po2 esatti); il suo floor va letto
  su quella base, non sul valore assoluto di frazionari.
- **Esattezza po2 dei pesi**: `snn_types` annota che i pesi `w` sono po2 esatti per n≥5; sotto, l'arrotondamento
  cambia i pesi reali. La curva di sensibilità di `w` **cattura** questo effetto (è comportamento, non un errore) —
  ma è la spiegazione attesa se `w` risulta il campo più sensibile.
- **Costo dei MEX**: ~72 configurazioni × un MEX ciascuna. Build in background; il forward a precisione mista prende
  i 6 nfrac come `coder.Constant` (una compilazione per tupla distinta).
- **Onestà sul risparmio**: come nello studio unico, la potenza è static-dominata su Zynq-7020 e l'Fmax è margine;
  il risparmio per-campo si leggerà soprattutto su LUT/FF/DSP, e va confrontato onestamente col nfrac unico (non
  col full-precision soltanto).
- **Fragilità della mask auto-modificante (§5.D)**: un callback che rigenera una chart a ogni "applica" è più
  fragile di una variante statica (edge-case su salvataggi/undo/copie del blocco). Va isolato e provato nei due
  sensi; se risultasse troppo fragile, il **ripiego robusto** è un **argomento del builder** —
  `build_tier_configurable` esteso con l'override per-campo, che rigenera il blocco alla config scelta — meno
  "menu vivo" ma senza callback.

## 9. Riferimenti

| Riferimento | Tema |
|---|---|
| `matlab/snn_types.m` | i 6 tipi del core (da parametrizzare per-campo) |
| `matlab/Quantizzation_Study/qz_cl_sim.m` · `qz_safety_metrics.m` | anello fedele + SSM (da riusare) |
| `matlab/Quantizzation_Study/qz_gen_block_vhdl.m` · `qz_sweep_nfrac.sh` | VHDL a nfrac + sweep sintesi (da riusare) |
| `matlab/Quantizzation_Study/test_dataset_exhaustive.mat` | dataset esaustivo (99 traj, cut-in) |
| `report/QUANTIZATION_STUDY_REPORT.md` · `QZ_CARFOLLOWING_STUDY.md` | studio nfrac unico (baseline di confronto) |
| fpga-expert ch09/ch13 (mixed-precision, per-tensor vs per-field) | metodo e pitfall |
