# FSNN V5.1 — Rete Originale (PUNTO DI PARTENZA)

> **ATTENZIONE: NON MODIFICARE QUESTO FILE.**
> Questa cartella contiene la rete neurale originale da cui CF_FSNN è stata derivata.
> Deve rimanere intatta come riferimento architetturale permanente.

---

## File

- `NN_FSNN_v5.py` — sorgente monolitico completo (single-file, nessuna dipendenza esterna)
- `FSNN_ Evoluzione delle Reti Neurali Spiking.pdf` — documentazione architetturale (7 pag.) — **VALIDATA** 2026-05-25

## Architettura

```
Input:  784 pixel MNIST (flat)
Hidden: HiddenLayer_ALIF  784 → 128  (rank=16, max_delay=3)
Output: OutputLayer_LI    128 → 10   (10 classi MNIST)
Task:   Classificazione immagini (CrossEntropyLoss)
```

**Componenti chiave (confermate, non inventate):**
| Classe | Descrizione |
|--------|-------------|
| `SurrogateSpike_Hardware` | Gradiente surrogato: `1/(1+γ|V−θ|)²` con γ=0.3 |
| `PowerOf2Quantize` | Quantizzazione pesi a `{2⁻⁴,...,2¹}` (DSP=0 su PYNQ-Z1) |
| `HiddenLayer_ALIF` | ALIF con soglia adattiva, fatica (bit-shift /8), soft reset, low-rank recurrence U(128×16)·V(16×128), delay assionico buffer |
| `OutputLayer_LI` | Leaky Integrator puro (no spike, no threshold) → potenziale diretto usato come logit |
| `Deep_SNN_V5_1` | Assembla Hidden+Output, 3 epoche, Adam lr=0.005 |

## Differenze rispetto a CF_FSNN

| Aspetto | Original (questo file) | CF_FSNN |
|---------|----------------------|---------|
| Dominio | Classificazione MNIST | Car-following V2X |
| Input | 784 pixel | 4 segnali [s, v, Δv, v_l] |
| Hidden size | 128 | 32 |
| Output size | 10 classi | 5 parametri IDM |
| rank | 16 | 8 |
| max_delay | 3 | 6 |
| Loss | CrossEntropy | PINN (data+phys+OU+bc) |
| Struttura | Monolitico | Modulare (neurons/network/train) |

## Perché conservare questo file

1. **Riferimento architetturale**: dimostra che ALIF+LI è la scelta originale,
   non un'aggiunta successiva. Qualsiasi variazione in CF_FSNN è intenzionale.
2. **Baseline hardware**: i valori di quantizzazione (2⁻⁴–2¹), leak (V/8),
   e soglia (1.5) sono calibrati su PYNQ-Z1 in questo file.
3. **Debug**: se CF_FSNN produce comportamenti anomali nell'architettura neurale,
   confrontare con questo file per isolare la causa.

## Note di Validazione del PDF (2026-05-25)

Il PDF è stato confrontato riga per riga con `NN_FSNN_v5.py`.

**Corretto**: ALIF, Po2, soglia adattiva, fatica, delay buffer, surrogate gradient, output LI, zero DSP, analisi di complessità.

**Discrepanza minore — decadimento LI output:**
- PDF afferma: `V = V − (V>>4)` → perde 1/16
- Codice attuale: `leak = self.potential / 8.0` → perde 1/8
- Il codice stesso documenta il cambiamento con il commento:
  `# Prima era: leak = self.potential / 16.0 — ORA: dimentica più in fretta`
- **Conclusione**: il PDF descrive la versione precendente; la modifica è intenzionale e non è un errore del PDF.

**Discrepanza trascurabile — range delay:**
- PDF: "da 0 a 3 tick". Codice: `randint(0, max_delay=3)` → {0,1,2}. Differenza di 1 tick.

**Imprecisione narrativa — "WTA / Inibizione laterale":**
- Il PDF descrive la recurrenza low-rank come Winner-Takes-All con segnali negativi.
- Nel codice i pesi rec_U/rec_V non sono strutturalmente vincolati ad essere negativi.
- La WTA può emergere dal training, ma non è architetturalmente garantita.
- È una semplificazione descrittiva accettabile, non un errore tecnico.

---
Generato: 2026-05-25
