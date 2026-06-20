# S3 — Consolidazione (A) + direzione futura sulla struttura di `a` (B)

> 2026-06-19. Chiusura della linea "osservabilita'" (S1b/S3). Stato consolidato +
> ciò che resterebbe da fare per spingere `a` oltre il suo tetto.

---

## A — Stato consolidato (punto d'arrivo solido)

Partiti da identificabilita' disastrosa (v0 NRMSE 0.50 saturato, `a` 0.36 collassato),
l'approccio **osservabilita' progressiva** (dato che eccita i parametri, NON aux) ha portato a:

| run | v0 | T | s0 | a | b | media NRMSE |
|---|---|---|---|---|---|---|
| S1 (vecchia data) | 0.50 | 0.13 | 0.17 | 0.36 | 0.24 | 0.28 |
| **S3 launch + decay 0.3** | 0.22 | 0.25 | **0.13** | 0.26 | 0.31 | **0.235** |

**Tutti e 5 i parametri in 0.13-0.31, media 0.235** (migliore identificabilita' congiunta
del progetto). Setup consolidato:
- **Dati**: mix con `freeflow` (eccita v0 in crociera) + `launch` (eccita `a`/`b` in
  accelerazione/frenata forte ripetuta). Scenari additivi nel generatore.
- **Restart**: `restart_decay=0.3` (Opzione 1+4) — restart progressivamente gentili
  (0.5,0.15,0.045,..), niente bump, miglior identificabilita' (vs decay 1.0 che esplorava
  l'accelerazione sacrificando i parametri).
- **Stabilita'**: guard v2 (frazione+inf) e AGC (`--grad_clip agc`) disponibili.
- **Diagnostica**: G19 (NRMSE per-canale) e G20 (follow x(t)) su ogni run.

**Tetto di `a`**: ~0.65 (vero 1.1), NRMSE 0.26. Lo abbiamo portato da 0.43 collassato a
0.65 con il launch, e li' si ferma — i restart non c'entravano (li abbiamo esclusi).

---

## B — Perche' `a` ha un tetto, e cosa servirebbe (FUTURO)

Analisi strutturale di `acc_iidm_accel` (`core/network.py`): `a` entra in 3 ruoli.

1. **Scala** (`v_free = a·(1−(v/v0)⁴)`, `a_z = a·(1−z²)`): gradiente grande solo in
   accelerazione libera forte.
2. **Cap saturante** — `min(·, a)` compare **3 volte** (`min(a_l,a)`, `min(a_cah,a)`,
   `min(a_acc,a)` finale). `∂min/∂a = 1` SOLO quando `a` e' il vincolo che morde
   (veicolo accel-limitato), `= 0` altrimenti. In guida normale `a` e' **invisibile**.
3. **Accoppiamento** — `a` e `b` entrano in `s_star` **solo come `√(a·b)`** -> direzione
   di sloppiness (scambiabili li').

**Conseguenza**: `a` e' osservabile solo in una finestra stretta (accel forte da bassa
velocita', dove l'IIDM satura a `a`). Il launch la sfrutta ma la finestra e' limitata
*per costruzione del modello*, non per scarsita' di dati. Quindi l'osservabilita' (dati)
ha un tetto.

**Cosa servirebbe per andare oltre 0.65** (cambi di MODELLO/loss, non di dati):
- Ridurre la dipendenza di `a` dai `min(·,a)` (riformulare i cap come transizioni smooth
  -> gradiente non-nullo anche prima della saturazione). Rischio: cambia la fisica ACC.
- Disaccoppiare `a` e `b` in `s_star` (oggi solo `√(a·b)`). Difficile senza cambiare l'IIDM.
- Un termine fisico che renda la loss sensibile ad `a` — MA: `a` = accel massima e' gia'
  la sua definizione nell'equazione (usata da `L_phys`); un termine dedicato sarebbe
  **aux travestito** (usa l'informazione che vogliamo evitare). Scartato in S3.

**Verdetto**: B e' un cambio di modello (piu' profondo, piu' rischioso), da valutare solo
se la validazione closed-loop mostra che l'errore residuo su `a` (~40%) causa comportamenti
insicuri. Altrimenti `a`≈0.65 e' un tetto pratico accettabile.

---

## Prossimo passo: validazione closed-loop

Vedi `utils/closed_loop_eval.py` + `Loss_Study_Eval_ClosedLoop.ipynb`: l'ego guidato dai
param SNN in scenari avversari (cut-in, frenate forti, ...) vs oracolo. Se e' sicuro
(zero collisioni) e ~oracolo, B non serve; se gli errori su `a` causano insicurezza, B
diventa prioritario.
