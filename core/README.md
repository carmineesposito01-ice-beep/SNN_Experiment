# core/ — Il modello

Il cuore di CF_FSNN: la rete spiking, i neuroni, le primitive hardware-aware, l'addestramento a
gradiente esatto e l'ottimizzatore dedicato. Teoria completa in `report/HOW_IT_WORKS_v3`.

| File | Contenuto |
|---|---|
| `network.py` | `CF_FSNN_Net` (Input→ALIF→LI→decode), lo strato `HiddenLayer_ALIF` (ricorrenza low-rank U·V + ritardi assonali) e `OutputLayer_LI`; il decode σ nei 5 parametri con i bound fisici; il modello fisico `acc_iidm_accel()` (usato nel residuo PINN) e `idm_accel()` di riferimento; `ou_residual()`. |
| `neurons.py` | `ALIFCell` (leak a bit-shift 7/8, soglia adattiva `θ_eff = θ_base + fatica`, spike Heaviside, reset sottrattivo) e `LICell` (integratore leaky d'uscita). |
| `hardware.py` | `SurrogateSpike_Hardware` (derivata surrogata fast-sigmoid `1/(1+γ|V−θ|)²`, γ=1.0, STE) e `PowerOf2Quantize` (Q(w) = sign·2^clip(round(log2|w|),−4,1), banda morta, STE). |
| `eventprop.py` | Addestramento **EventProp**: gradiente esatto via equazione aggiunta (adjoint) sugli istanti di spike. |
| `prodigy_event.py` | `ProdigyEvent`: variante parameter-free di Prodigy adattata a EventProp (stima di `d` su gradiente EMA + throttle + ProbeUp). |
| `__init__.py` | Export del package. |

> Oltre alla baseline, `network.py` contiene le **varianti architetturali** confrontate negli
> studi — `CF_FSNN_Net_Stacked`, `_StackedSkip`, `_MultiRate`, `_WTA`, `_Attn` — e le versioni per
> l'addestramento a gradiente esatto (`CF_FSNN_Net_EventProp_Full`), tutte selezionabili con la
> factory `build_model(variant=…)`. Gli snapshot self-contained sono in
> [`../Arch_Tested/`](../Arch_Tested/).

## Note di co-design

- Le quantità sono **hardware-friendly per costruzione**: leak = shift, moltiplicazione = shift
  (po2), reset = sottrazione (nessun divisore). Il gradiente verso la soglia **non** è propagato
  (scelta hardware): `θ_base`/`θ_jump` imparano solo tramite il soft-reset.
- La quantizzazione è **forward-only** durante il training (STE): i pesi in virgola mobile
  restano quelli aggiornati.

Consumato da: `train.py`, `eval_report.py`, i notebook di studio, `utils/` e `scripts/`.
