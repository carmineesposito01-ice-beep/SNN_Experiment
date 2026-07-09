# data/ — Generatore di dati sintetici

| File | Contenuto |
|---|---|
| `generator.py` | Genera traiettorie di car-following **sintetiche** con lo stesso modello ACC-IIDM che la rete deve identificare (nessun dato reale). Include: `_acc_iidm_accel` (verità di simulazione), `simulate_trajectory` (integrazione balistica, Δt=0.1 s), `_idm2d_T_step` (T(t) a salti di Markov), `_ou_step` (rumore Ornstein-Uhlenbeck su gap/velocità/accelerazione), la stima IIR dell'accelerazione del leader, e `normalize` (ingressi fisici → [0,1]). |
| `__init__.py` | Export del package. |

## Cosa produce

Per ogni passo: `[s, v, Δv, v_leader, v̇, T_vero, mask]`. Dopo normalizzazione, input `(N,4)` e
target fisico `(N,2) = [accelerazione, T_vero]`. Ingredienti realistici: mix di scenari
(highway/urban/truck/mixed + free-flow/launch), cut-in (~20%), perdita pacchetti V2X (~2%),
T(t) stocastico (IDM-2d). I parametri esatti (durate, split, proporzioni) sono in `config.py`;
la spiegazione discorsiva è in `report/HOW_IT_WORKS_v3` §14.

> I dataset materializzati vanno in `dataset/` (gitignored): sono **rigenerati a runtime**.
