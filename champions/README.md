# champions/ — pesi frozen dei 4 champion (versionati)

> **Scopo:** i 4 champion sono **frozen** e **minuscoli** (~24–60 KB l'uno), quindi li
> **versioniamo in git** — a differenza degli altri checkpoint, esclusi da `.gitignore`
> (`checkpoints/`, `*.pt`). Così si può **girare in locale senza Azure**: sviluppo/test del
> **simulatore ①** (`document/SIMULATOR_DESIGN.md`, che deve `load` un checkpoint) e re-render
> delle **figure FPGA** sui champion veri invece degli stand-in.
>
> **Un-ignore:** `.gitignore` ha `!champions/**` (dopo `*.pt`). L'oracolo (Master Splinter)
> **non** è incluso (decisione: solo i 4 champion).

## Mappa alias → tag → metodo

| Alias | Tag checkpoint | Metodo | ρ(U·V) | Nota |
|---|---|---|---|---|
| **Raffaello** | `R33_C2_A1_T12_fix` | BPTT | 2.99 | baseline rank-8 |
| **Leonardo** | `LS3_PEAK_R0_launch_d03` | BPTT | 1.155 | |
| **Donatello** | `PE_t05_gp0002` | EventProp | 0.051 | rank-16, best accuracy (84.8%), candidato deploy FPGA |
| **Michelangelo** | `A_lr1e2_t06_r16` | EventProp | 0.388 | rank-16 |

## Layout

```
champions/
  README.md
  R33_C2_A1_T12_fix/best_model.pt
  LS3_PEAK_R0_launch_d03/best_model.pt
  PE_t05_gp0002/best_model.pt
  A_lr1e2_t06_r16/best_model.pt
```
Struttura `<tag>/best_model.pt` = identica a `checkpoints/<tag>/`, così il codice di load esistente
funziona cambiando solo la radice.

## Come popolarla (DA FARE su Azure — i .pt reali stanno lì)

Da eseguire **sulla VM Azure**, dalla root del repo, **dopo** che questo commit (con la negazione
`.gitignore`) è su origin e la VM ha fatto `git pull`:

```bash
cd <repo-root>   # .../SNN_Experiment
for tag in R33_C2_A1_T12_fix LS3_PEAK_R0_launch_d03 PE_t05_gp0002 A_lr1e2_t06_r16; do
  mkdir -p "champions/$tag"
  cp "checkpoints/$tag/best_model.pt" "champions/$tag/best_model.pt"
done
git add champions/
git status --short          # deve mostrare solo i 4 best_model.pt (~30KB l'uno)
git commit -m "champions: versiona i 4 champion frozen per girare in locale"
git push origin EventProp_Study
```
Poi in locale `git pull` → i 4 champion sono disponibili senza Azure.

> **Resolver (da aggiungere quando serve, non ora):** un piccolo helper
> `resolve_checkpoint(tag)` che cerca `champions/<tag>/best_model.pt` e poi `checkpoints/<tag>/`,
> così sia i run locali sia quelli Azure trovano i pesi senza toccare i path nel codice.
> Lo si costruisce col primo consumatore (simulatore ① o run FPGA locale).
