# Presentation_NN — Nuova presentazione (deck NN-first) — design

> **Data:** 2026-07-11 · **Branch:** `Presentation_NN` (da `main`) · **Worktree:** `.worktrees/Presentation_NN`
> (sparse: `presentation/ report/ docs/ core/ scripts/`) · **Stato:** design **approvato** (storyboard OK 2026-07-11).
>
> Nuova presentazione del progetto CF-SNN, **separata** da `presentation/cf_fsnn_thesis/`, stesso stile,
> pensata per un **discorso ad alto livello** e comprensibile. Base: presentazione esistente + codice +
> i 3 report in `report/`. **Ignora** i risultati del branch `Simulink_Importer` (Fase B/C).

---

## 1. Obiettivo & vincoli

**Obiettivo (utente):** un discorso che mostri quanto fatto nel progetto, **quanto più comprensibile
possibile**, restando **ad alto livello** per la maggior parte della discussione — carico affidato in gran
parte alle **animazioni** (alcune nuove).

**Vincoli:**
- Stesso **stile** della presentazione esistente (tema `cf_dark`, Quarto + reveal.js, KaTeX).
- **Riusare** le slide esistenti dove possibile (copiare + adattare, non ricreare da zero).
- **Slide di transizione** (divider) presenti, come nell'esistente.
- La prima bozza (**v1**) è completa e navigabile; seguirà una **rifinitura mirata per-slide**.
- **Fonti:** presentazione esistente, codice del progetto, i 3 report (`report/FPGA_REPORT.md`,
  `HOW_IT_WORKS_v3.md`, `VALIDATION_REPORT_v3.md`) + relative cartelle figure. **Non** i risultati Fase B/C.

## 2. Decisioni locked (dal brainstorming 2026-07-11)

| Tema | Decisione |
|---|---|
| **Slide 12 (hidden)** | Descrivere la **ricorrenza low-rank `U·V` (rango-8) + raggio spettrale ρ** (meccanismo reale dei champion). **NON** winner-take-all (esiste nel codice ma è variante non-deployata). |
| **4 animazioni nuove** | In **v1 restano i placeholder** (animazioni esistenti / figura concept); le nuove si costruiscono nel giro di **rifinitura**. |
| **Slide 5 (viste SysML)** | **Omessa** in v1 (nessuna figura sorgente nel repo). Riattivabile se l'utente fornisce gli export. |
| **Logo Kineton** | **Placeholder** sul titolo in v1; l'utente fornisce il file ufficiale (PNG/SVG) in rifinitura. |
| **Energia (s29)** | Framing **dei report: ≈5–8×, da AC<MAC, stime Horowitz.** NON il reframe "compattezza / e_MAC≈e_AC" della Fase B. |
| **Numeri s17/s19** | Presi da `report/` e dai champion **reali**, mai inventati. |

## 3. Approccio di build

**Nuovo progetto Quarto affiancato** `presentation/cf_fsnn_nn/`, che **riusa** il tema condiviso
`presentation/_shared/theme/cf_dark.scss` e **copia/adatta** i blocchi slide da `cf_fsnn_thesis`,
riordinandoli sullo schema a 32 slide in nuovi file-atto. Deliverable **autonomo** (asset propri).

*Alternative scartate:* (a) duplicare l'intero `cf_fsnn_thesis` e sfoltire — trascina roba inutile;
(b) un unico deck a profili — l'utente vuole una presentazione **separata**.

**File nuovi:**
```
presentation/cf_fsnn_nn/
  _quarto.yml               # copia di cf_fsnn_thesis/_quarto.yml (output-dir _output, katex, fit-equations)
  slides_nn.qmd             # master: YAML (titolo+tema) + include dei 7 atti
  cf_slim.scss              # copia (stile slide)
  fit-equations.js          # copia (auto-scale equazioni larghe)
  _acts_nn/
    act0_progetto.qmd       # s1–4  (titolo, obiettivo, perché NN, perché FPGA)
    act1_snn.qmd            # divider + s6–8  (principio NN, tre generazioni, confronto+scelta)
    act2_rete.qmd           # divider + s9–15 (PINN, architettura ×5, decode, ottimizzazioni)
    act3_training.qmd       # divider + s16–19 (BPTT, BPTT-risultati, EventProp, EP-risultati)
    act4_risultati.qmd      # divider + s20–25 (campioni, leve, NRMSE, safety, robustezza, traffico)
    act5_fpga.qmd           # divider + s26–30 (quant, ρ, timing, energia, SEU)
    act6_verdetto.qmd       # divider + s31–32 (radar+Donatello, fine)
  assets/                   # sottoinsieme copiato: img/ + manim/ + results/ necessari
  figures/                  # sottoinsieme copiato da cf_fsnn_thesis/figures + report/figures_* necessari
```

**Render:** `quarto render` da `presentation/cf_fsnn_nn/` → `_output/slides_nn.html`.

**Gotcha da rispettare (dai doc/deck esistente):** KaTeX (non MathJax) · niente heading `###` dentro le
`.card` · niente `title:""` negli include · **bundlare** le figure esterne (copiate in `assets/`/`figures/`,
mai riferite fuori dal progetto).

## 4. Arco narrativo (7 blocchi + divider)

`Atto 0 — Il progetto` (apertura, titolo) → `Atto 1 — Le reti neurali (SNN)` → `Atto 2 — La nostra rete
(CF-SNN)` → `Atto 3 — Addestramento` → `Atto 4 — Risultati` → `Atto 5 — Idoneità FPGA` →
`Chiusura — Verdetto`. Un `{.divider}` per atto (≈6), come i divider attuali.

## 5. Storyboard slide-per-slide

Legenda: ♻️ riuso esistente · ➕ riuso+estende/merge · ✳️ nuova · ✂️ split architettura ·
🎬 animazione nuova (in v1 = placeholder esistente).

| # | Slide | Azione | Asset (esistenti salvo nota) |
|---|---|---|---|
| **A0** | *Il progetto (apertura = slide titolo)* | | |
| 1 | Titolo + logo Kineton | ♻️ titolo + **logo placeholder** | — |
| 2 | Obiettivo: DSP con AI-accel, V2X → parametri CF su FPGA | ✳️ + illustrazione | base `v2x.png` / **schema placeholder** |
| 3 | Perché una rete neurale? (velocità inferenza · comportamenti non-deterministici/probabilistici · mapping inverso appreso) | ✳️ cards | — |
| 4 | Perché FPGA? (determinismo temporale · basso consumo · fast-prototyping vs ASIC) | ✳️ cards | — |
| ~~5~~ | ~~Viste SysML black/white-box~~ | **omessa (v1)** | — |
| **A1** | *Le reti neurali (SNN)* — divider | | |
| 6 | Introduzione alle NN: principio di funzionamento | ✳️ (riusa concetti neurone) | `assets/img/membrane.png` |
| 7 | Le tre generazioni | ♻️ | `assets/manim/three_generations.gif` |
| 8 | Confronto generazioni + scelta (hardware/applicazione) | ➕ merge (ANN-vs-SNN + vantaggi/svantaggi) | tabella |
| **A2** | *La nostra rete (CF-SNN)* — divider | | |
| 9 | Algoritmo PINN: cos'è / perché + animazione esaustiva | ➕ (problema-inverso + PINN-processo) · 🎬 | `pinn_loop.gif` → **nuova** |
| 10 | Architettura (1): schema generale + strati | ♻️ | `architecture_flow.gif` |
| 11 | Architettura (2): layer **input** + equazioni | ✂️✳️ | `report/figures_howitworks_v3/eq_norm.png` |
| 12 | Architettura (3): **hidden** ALIF + ricorrenza low-rank + ρ | ♻️ (ALIF + low-rank) | `alif_fatigue_dark.gif`, `low_rank.gif` |
| 13 | Architettura (4): **output** LI + sigmoid | ✂️✳️ | `eq_li.png` |
| 14 | Architettura (5): **Decode** + visual prima/dopo | ✳️ | `eq_decode.png` + **visual placeholder** |
| 15 | Architettura (6): ottimizzazioni (Po2 + ricorrenza) | ♻️ (po2 + recap low-rank) | `ste_po2.gif` |
| **A3** | *Addestramento* — divider | | |
| 16 | BPTT: perché il backprop classico non basta + animazione passo-passo (parallelo al codice) | ➕ (why-backprop + BPTT) · 🎬 | `bptt_training.gif` → **nuova** |
| 17 | BPTT — risultati (min loss) + pro/contro | ✳️ | numeri da `report/` (reali) |
| 18 | EventProp (stesso livello) | ♻️ | `eventprop_adjoint.gif` |
| 19 | EventProp — risultati + pro/contro | ✳️ | numeri da `report/` (reali) |
| **A4** | *Risultati* — divider | | |
| 20 | I 4 campioni (2 BPTT, 2 EP) + perché scelti | ♻️ | `champions_roster_intro.png` |
| 21 | Leve di valutazione + riferimento (Master Splinter) | ♻️ (6 tier) | — |
| 22 | NRMSE (figura comparativa) | ♻️ | `accuracy_heatmap.png` / `nrmse_stratified.png` |
| 23 | Safety (figura) | ♻️ | `safety_delta.png` |
| 24 | Robustezza (strada avversa **+ dati frammentati**) | ♻️ | `plant.png` (+ V2X) |
| 25 | Traffico: string · stop&go · flusso-densità | ♻️ (3 fig) | `string.png`+`meso_spacetime.png`+`macro_fd.png` |
| **A5** | *Idoneità FPGA* — divider | | |
| 26 | FPGA-Friendly (1): quantizzabilità (range stati + fixed-point + resistenza) | ➕ | `quant.png` + `02_FixedPoint__state_ranges.png` + `eq_qmn.png` |
| 27 | FPGA-Friendly (2): stabilità ρ + animazione overflow-vs-stabile | ♻️ · 🎬 | `discriminant.png` + `spectral_echo.gif` → **nuova** |
| 28 | FPGA-Friendly (3): metriche temporali (sotto il limite) | ♻️ | timing WCET==BCET (cards) |
| 29 | FPGA-Friendly (4): energia (confronto + sparsity) | ♻️ | `energy_ann.png` + `synops_split`/`sparsity_per_tick` |
| 30 | FPGA-Friendly (5): bit-flip + errore vs #flip | ♻️ · 🎬 | `seu.png` + `07_SEU..concept` → **nuova** |
| **Fine** | *Verdetto* — divider | | |
| 31 | Verdetto: radar + Donatello + sunto | ➕ merge | `readiness_radar.png` + `champions_roster.png` |
| 32 | Fine / grazie / domande | ✳️ | — |

**Bilancio:** ~18 riuso/merge · ~10 nuove o split · 4 animazioni nuove (placeholder in v1) · s5 omessa.
Totale ≈ **31 slide + ~6 divider**.

## 6. Nuove slide — note di contenuto

- **s2 Obiettivo:** una frase-tesi (sistema DSP con AI-acceleration che genera i parametri di un modello di
  car-following da segnali V2X, su FPGA) + illustrazione «FPGA: V2X → [SNN] → 5 parametri». v1: adatta
  `v2x.png` o schema semplice a blocchi (placeholder).
- **s3 Perché una NN:** cards — velocità d'inferenza · comportamenti non-deterministici/probabilistici (oltre
  l'approccio deterministico classico) · capacità di apprendere il mapping inverso (traiettoria → parametri).
- **s4 Perché FPGA:** cards — determinismo temporale (WCET==BCET) · basso consumo · fast-prototyping vs ASIC.
- **s6 Principio NN:** neurone → pesi → attivazione → strati; ponte verso le tre generazioni (s7).
- **s11 Input:** i 4 segnali V2X normalizzati entrano come corrente continua `I = W·x` (no spike); eq. di
  normalizzazione (`eq_norm`).
- **s13 Output:** 5 neuroni LI (integratori a perdita, no soglia); readout = tensione; uscita sigmoid (`eq_li`).
- **s14 Decode:** mappatura tensione → range fisico dei 5 parametri; eq. (`eq_decode`) + traduzione visiva
  prima/dopo (visual placeholder in v1).
- **s17/s19 Risultati BPTT/EventProp:** «min loss raggiunta» + pro/contro per metodo. Numeri dai champion
  reali (BPTT: Leonardo/Raffaello; EventProp: Donatello/Michelangelo) e da `report/VALIDATION_REPORT_v3.md`.
  *(Se servono le loss di training esatte, si estende lo sparse-checkout a `results/` — da confermare in
  fase di build; nessun numero inventato.)*
- **s32 Chiusura:** «Fine», ringraziamento, attesa domande.

## 7. Animazioni nuove (rifinitura — placeholder in v1)

| Slide | Placeholder v1 | Animazione nuova (cosa deve mostrare) |
|---|---|---|
| 9 (PINN) | `pinn_loop.gif` | Flusso **numerico completo**: traiettoria (valori) → SNN → 5 parametri (valori) → equazioni ACC-IIDM (coi numeri che entrano) → â → confronto con `a_obs` → loss → gradiente → update. Chiarezza numerica in ogni passo. |
| 16 (BPTT) | `bptt_training.gif` | Unroll temporale con **frecce a ritroso** tick-per-tick attraverso `(U·V)ᵀ`, somma sui tick, surrogato allo spike; parallelo visivo a ciò che accade nel codice. |
| 27 (ρ) | `spectral_echo.gif` | Due accumulatori affiancati: uno con **ρ>1** che cresce e va in **overflow**, uno con **ρ<1** che resta limitato. |
| 30 (SEU) | `07_SEU..concept` | Cos'è un **bit-flip** (un bit che si inverte in un registro) e il suo effetto sull'uscita; abbinata al grafico errore vs #flip. |

Le altre animazioni (three_generations, lif, alif, low_rank, acc_iidm, ste_po2, eventprop_adjoint,
architecture_flow) sono **riusate as-is**.

## 8. Onestà (vincoli di contenuto)
- Energia inquadrata **come nei report** (≈5–8×, AC<MAC, Horowitz); niente reframe Fase B.
- Hidden layer = **low-rank + ρ**, non WTA.
- Placeholder in v1 dichiarati (logo, illustrazione s2, 4 animazioni, visual decode s14).
- Numeri s17/s19 dai report/champion reali, non inventati.
- Idoneità FPGA = **obiettivo di design / stime**, non silicio validato (già l'onestà del deck esistente).

## 9. Criteri di successo (v1)
1. `presentation/cf_fsnn_nn/` renderizza con `quarto render` senza errori → `_output/slides_nn.html`.
2. Tutte le **31 slide + divider** presenti nell'ordine dello storyboard; s5 omessa.
3. **Stesso stile** dell'esistente (tema, card, equazioni, footerbar) — riuso verificabile a vista.
4. I **placeholder** (logo, s2, 4 animazioni, visual decode) sono chiaramente marcati e sostituibili.
5. Deck **autonomo**: nessun riferimento a figure fuori da `cf_fsnn_nn/` (asset bundlati).

## 10. Vincoli permanenti (dal progetto)
- **Niente workaround**: se un contenuto/numero non torna, si indaga la causa (nei report/codice), non si
  aggiusta il numero.
- Cura della documentazione: spec → piano → build; aggiornare `SESSION_RESUME`/memoria a milestone.
- Commit conventional, **senza `Co-Authored-By`**. Push su `Presentation_NN`.
- Non si tocca il deck `cf_fsnn_thesis` esistente (la nuova è separata).

## 11. Aperte / rinviate (a rifinitura)
- **Slide 5** (viste SysML): inclusa solo se l'utente fornisce gli export General/Interconnection View.
- **Logo Kineton**: file ufficiale da fornire.
- **4 animazioni nuove**: da costruire (Manim, `scripts/manim/`).
- **Illustrazione s2** e **visual decode s14**: da rifinire.
- Eventuale export **PPTX** (`build_pptx.py`) — opzionale, a valle della v1.
