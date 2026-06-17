# FUTURE_WORK.md — Esperimenti differiti + opzioni next-phase

> File con (a) **opzioni post-closure 2026-06-16** disponibili dopo merge
> studio Prodigy su main, (b) **opzioni storiche STEP 2E** (sotto), (c) **idee differite** per dopo. Ogni voce è un'opzione, non un impegno. Aggiornare data quando si esegue/scarta.

---

## 🟢 POST-CLOSURE 2026-06-16 — opzioni dopo R33

Lo studio Prodigy è chiuso. I floor val_data sono passati da 0.28 (pre-R24F) a **0.159** (R33_C1 record). 4 champion attivi in `Arch_Tested/`. Le opzioni concrete per il prossimo capitolo:

| ID | Mossa | Costo dev | Costo Azure | Risultato atteso | Note |
|----|---|---|---|---|---|
| **F6** | **Multi-seed validation 4 champion** | 1 giorno | ~6h | conferma robustezza ± 1σ | **CONSIGLIATO prima di F5** — single-seed è il vero rischio rimasto |
| **F5** | **Deploy FPGA PYNQ-Z1** (R33_C2 CLEAN) | 2-3 settimane | minimo | progetto v1 completato | Setup minimum-risk: 864 params + gn pulito + 50/50 ep |
| **F4** | **Architettura modificata** post-RESET | ~1 settimana | 5-10h sweep | val_data 0.13-0.15 (?) | Rifare A8 attn (3936p), StackedSkip su baseline pulito |
| **F7** | **R30 4-tuple sui champion R33** | 2-3 giorni | ~3h | rank ≥4 garantito | Aggiunge supervisione ausiliaria a C1/C2; può sbloccare ulteriore Tp |
| **F2** | EventProp (storico) | 2-4 settimane | ~5h | bassa probabilità di vincere | Già scartato in F2 originale, mantenuto come reference |

**Raccomandazione**: **F6 → F5** è il path low-risk. **F7 → F4** è il path high-reward (più tempo, più downside, più potenziale).

### [F6] Multi-seed validation — il vero rischio rimasto

Single-seed è la principale criticità non risolta dello studio. Tutti i 4 champion sono basati su 1 seed (default 42). Rumore intra-seed può essere ≈ margini dichiarati (cfr. AUDIT_2026-06-02 §criticità #3).

**Setup proposto**:
- 4 champion × 5 seed (42, 123, 456, 789, 1024) = 20 run
- ~18 min/run × 20 = 6h compute Azure
- Output: stessa metrica per seed → media ± σ
- Test: il ranking PEAK/CLEAN/STABLE resta stabile? Se sì → deploy con confidenza. Se no → rivaluta.

**Notebook stub**: `Prodigy_MultiSeed_R34.ipynb` (da creare). Pattern: identico a R33 ma loop su `--seed {42,123,456,789,1024}`.

---

## 📋 STORICO — Sommario decisione utente STEP 2E (pre-R24F)

> ⚠️ Le tabelle e raccomandazioni sotto sono dello stato **pre-2026-06-03** (prima della scoperta R24F baseline). Conservato per archeologia. Per le decisioni post-closure 2026-06-16 vedi sopra.

## 📋 Sommario decisione utente STEP 2E (storico)

| ID | Mossa | Costo dev | Costo Azure | Potenziale miglioramento | Pro | Contro |
|----|-------|-----------|-------------|--------------------------|-----|--------|
| **F2** | **Switch a EventProp** | 2-4 settimane | ~5h | -0.06/-0.10 (probabile) | gradiente esatto, no surrogate error | paradigma diverso, refactor |
| **F3** | **Curriculum noise** | 1 giorno | ~2h | -0.03/-0.06 (atteso) | leverage scoperta F2, zero refactor | miglioramento limitato |
| **F4** | **Architettura modificata** (più layer / attention / multi-rate ALIF) | ~1 settimana | 5-10h sweep | -0.05/-0.10 (alta probabilità) | attacca direttamente residuo 78% | Po2 da preservare, BPTT più costoso |
| **F5** | **Accept floor + deploy PYNQ-Z1** | ~2 settimane | minimo | nessuno | chiude progetto v1 | lascia 0.06 di margine sul tavolo |
| ~~F1~~ | _Re-sweep Prodigy esteso_ | rimandato | — | basso | esplorazione approfondita | da fare DOPO aver alzato il floor |

**Mia raccomandazione personale (Claude)**: combo **F3 + F4** (curriculum noise come quick win + architettura modificata come main bet). F2 (EventProp) è valido ma più rischioso, da valutare se F4 non basta. F5 (deploy) è prematuro finché non hai dati che 0.28 è "accettabile" per il tuo target.

**Risposta tipica all'indicazione utente "valutiamo se abbiamo raggiunto il limite di BPTT"**:
La decomposizione P14 NON dimostra che BPTT sia il limite (il residuo 78% può venire da capacità/dataset/architettura ANCHE indipendentemente da BPTT). Per provare/falsificare l'ipotesi "BPTT è il limite", servirebbe esattamente **F2 (EventProp)** come esperimento controllato: stesso modello + stesso dataset + stesso scheduler ma gradient esatto invece di approssimazione surrogate. Questo isola la variabile "training method" e dice se BPTT era il bottleneck.

---

## 🎯 [F2] Switch a EventProp — paradigma training event-based exact gradient

**Quando**: ORA, candidato per STEP 2E. La decomposizione P14 mostra che **78% del floor è "residuo architettura"** e BPTT+surrogate è il paradigma di training corrente. Se il limite è negli errori di approssimazione del surrogate gradient, EventProp può sbloccare il residuo.

**Razionale**:
- **EventProp** (Wunderlich & Pehle 2021, "Event-based backpropagation can compute exact gradients for spiking neural networks") calcola gradienti **esatti** evento-per-evento usando metodo aggiunto (Hamiltonian backprop), invece di approssimare via surrogate gradient continuo.
- Costo memoria: O(spikes) invece di O(T × N) → drasticamente più efficiente di BPTT
- Gradiente esatto = no errore di approssimazione γ (che potrebbe essere parte del residuo P14)
- Reference skill: `SNN-expert` ch08 §Surrogate Gradient Learning, §Beyond Surrogate Gradient

**Riferimenti**:
- Paper: https://www.nature.com/articles/s42256-021-00428-6
- snnTorch ha implementazione recente in `snntorch.functional.eventprop` (da verificare versione)
- Alternative framework: **Norse** (PyTorch-based, EventProp native), **Spyx** (JAX, EventProp via diffrax)

**Cosa serve fare per testare**:
1. **Decision punto-chiave**: vogliamo riscrivere CF_FSNN_Net in snnTorch/Norse/Spyx OPPURE implementare EventProp manualmente sulla nostra ALIF cell custom?
   - Opzione A (riscrittura): più rapida (1-2 settimane) ma perdiamo `core/hardware.py` Po2 + surrogate hardware-friendly → richiede ri-implementare gli stessi vincoli sul nuovo framework
   - Opzione B (manuale su nostra cell): più costosa (3-4 settimane) ma preserva tutta l'architettura corrente
2. Validare equivalenza forward: il nuovo modello deve dare gli STESSI spike pattern sulla stessa input (sanity check)
3. Re-runnare il baseline (F2 setup: no OU + AdamW b=8 + 15 ep × 190) per confronto diretto val_best EventProp vs BPTT (0.2262)
4. Se EventProp scende sotto 0.20 → conferma surrogate era parte del residuo → migrate al nuovo paradigma
5. Se EventProp resta a 0.22 → confermerà che il residuo NON è errore di approssimazione gradiente → si rivela limite architetturale puro

**Costo stimato**: 2-3 settimane sviluppo (opzione A) o 3-4 settimane (opzione B) + ~5h Azure per validation.

**Risultato atteso**:
- Probabilità EventProp sblocca il floor: **media (~40%)**
  - Pro: gradient esatto, conferma teorica che surrogate è approssimazione lossy
  - Pro: O(spikes) memoria → potremmo permetterci modelli più grandi
  - Contro: paradigma "newer", meno robusto in produzione
  - Contro: per ALIF il calcolo aggiunto è non-trivial, implementazione delicate

**Rischi**:
- Tempo significativo speso senza garanzia di miglioramento
- Riscrittura potrebbe introdurre nuovi bug nascosti
- Po2 quantization deve essere ri-pensata (in EventProp i pesi entrano nel calcolo aggiunto)

---

## 🎯 [F3] Curriculum noise training

**Quando**: ORA, alternativa più rapida a F2. Sfrutta direttamente la scoperta che OU noise (-19.3%) è la sola componente facilmente riducibile.

**Razionale**: il modello F2 (no OU) impara val=0.226. Il modello REF (OU on) impara val=0.281. Idea: addestrare PRIMA su dataset deterministico (noise_scale=0) per imparare il "vero" mapping, POI gradualmente alzare noise_scale per adattarsi al rumore reale. Curriculum learning classico.

**Schema**:
```
Phase 1 (epoch 1-5):  noise_scale=0.0   →  rete impara mapping pulito (target ~0.22)
Phase 2 (epoch 6-10): noise_scale=0.5   →  adattamento graduale
Phase 3 (epoch 11-15): noise_scale=1.0  →  fine-tuning su rumore nominale
```

**Aspettativa**: probabilmente val finale sarà tra F2 (0.226) e REF (0.281), forse intorno a **0.24-0.25**. Non è breakthrough ma è miglioramento del ~10% gratis.

**Cosa serve**:
- Cella notebook che genera 3 cache (`cache_..._ou0.0`, `..._ou0.5`, `..._ou1.0`) — F2 e REF già esistono, manca solo OU=0.5
- Loop training che switch cache+dataloader a epoch boundary
- Tempo dev: ~1 giorno

**Costo Azure**: ~45 min × 3 = ~2h totali.

**Pro**:
- Zero cambio paradigma, riusa tutto il codice esistente
- Decisione immediata "in produzione vediamo questo val realistico"

**Contro**:
- Miglioramento atteso modesto (~10-15%)
- Non attacca il residuo architettura

---

## 🎯 [F4] Architettura modificata

**Quando**: ORA, attacca direttamente il residuo 78% del floor.

**Razionale**: il residuo architettura è il vero collo di bottiglia. Sweep STEP 2B ha mostrato che AUMENTARE h non aiuta (864 → 9605 params: Δval=1.3‰). Quindi non è "più capacità della stessa cosa", serve cosa DIVERSA. Cosa testare:

1. **Più layer** (depth invece di width): CF_FSNN_Net attualmente è 1 hidden layer ALIF + 1 LI output. Provare:
   - 2 hidden layers ALIF
   - ResNet-style skip connections tra layer
2. **Attention/spike-attention**: ricevere riferimenti `SNN-expert` ch21 "Spiking transformer". Versione lite SpikFormer su nostra task
3. **Mixed precision time**: ALIF base + LIF refinement layer (gerarchia temporale)
4. **Recurrent connection più profonde**: invece di rank=8 low-rank, recurrent full-rank con regolarizzazione
5. **Multi-rate ALIF**: neuron groups con τ_adapt diversi (slow/fast adaptation)

**Costo stimato**: ~1 settimana sviluppo + 5-10h Azure (sweep 3-5 varianti architetturali).

**Risultato atteso**: alta probabilità di portare il floor da 0.22 a 0.15-0.18 se la diagnosi "limite architetturale" è corretta. Range 0.10-0.15 se l'architettura cambiata + curriculum noise (F3) si combinano sinergicamente.

**Rischi**:
- Po2 quantization deve essere preservata su ogni nuovo layer aggiunto
- BPTT diventa più costoso con più layer (deep + recurrent)
- Spike pattern potrebbero degenerare (dead neurons / saturation come P13)

---

## 🎯 [F5] Accept floor 0.28 → procedere a deploy PYNQ-Z1

**Quando**: ORA, se l'utente decide che 0.28 è "accettabile" per il deploy target.

**Razionale**:
- 0.28 = MSE/RMSE compatibile con specifiche target? (da verificare con requisiti progetto)
- val_data 0.27 corrisponde a un errore di predizione del parametro T in unità reali — quantificare
- Approccio engineering: "release v1, raccogli feedback su HW reale, ottimizza in v2"

**Cosa serve fare per chiudere v1**:
1. Validation finale su dataset full-mix (highway + urban + truck + cut-in) per evitare overfit highway-only
2. Bench cross-scenario robustness (deve passare anche su scenari non visti in training)
3. Export weights in formato PYNQ-Z1: quantizzazione finale + bitstream
4. Latency benchmark su FPGA: tempo per inference, energy budget
5. Demo end-to-end V2X → CF_FSNN → ACC controller

**Tempo stimato**: ~2 settimane per pipeline deploy + benchmark.

**Pro**: chiude il progetto, libera l'utente per altre attività.

**Contro**: lascia 0.06 di margine teorico sul tavolo (residuo architettura non attaccato).

---

## 🔬 [F1] Re-sweep Prodigy con parametri estesi (post-floor)

_(spostato in fondo perché meno prioritario rispetto a F2-F5; il contenuto resta valido)_

**Quando**: dopo aver superato il floor strutturale val~0.28 (STEP 2D+, cioè dopo F2/F3/F4).

**Razionale**: Lo sweep STEP 2C-bis (2026-05-30) ha confermato che Prodigy con `lr=0.1, b=1` raggiunge essenzialmente lo stesso plateau di AdamW (0.2823 vs 0.2805). Conclusione: per QUESTO problema (con il floor a 0.28), Prodigy non offre vantaggi sufficienti.

Ma una volta abbattuto il floor, lo "spazio di apprendimento" si apre. In un regime dove val può davvero scendere sotto 0.20, Prodigy potrebbe esibire comportamenti diversi.

**Parametri non ancora esplorati**: `weight_decay`, `growth_rate`, `beta3`, `slice_p`, `d0`, `use_bias_correction`. Combo da testare: "lr alto + d_coef molto basso" (es. lr=2.0 + d_coef=0.1 → lr_eff=0.2).

**Strumenti già pronti**: `--prodigy_d_coef` esposto, logging `prodigy_d` attivo.

**Costo aggiungere CLI**: ~30 min dev + 5 nuovi flag.
