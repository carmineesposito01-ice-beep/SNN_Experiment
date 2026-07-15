# SP2 — `Donatello_ACC_IIDM`: campione + plant ACC-IIDM open-loop — Design

**Data:** 2026-07-14 · **Branch:** `Simulink_Importer` · **Stato:** approvato dall'utente

## 1. Scopo
Aggiungere alla libreria un blocco **plug&play** che porti la catena completa **stato → azione di controllo**:
il campione Donatello stima i 5 parametri IDM, il modello **ACC-IIDM** li usa per calcolare l'accelerazione.
Serve a **testare la SNN a valle** (dentro un modello di car-following), non a mettere il plant su FPGA.

## 2. Contesto — cosa è cambiato dall'abbozzo di SP1 §5
L'abbozzo originale prevedeva «Donatello con LUT-256 + ACC-IIDM». Tre cose sono cambiate:
1. **Il campione ora è LUT-64** (`DECODE_LUT_SWEEP.md` §5bis): stessa accuratezza, −288 LUT sul top.
2. **L'interfaccia del blocco SNN è cambiata**: da `xn`+`start`/`done` a **I/O fisico** `s,v,dv,v_l → v0,T,s0,a,b`,
   senza handshake, edge-triggered sul cambio d'ingresso (`HDL_PHASE.md` §3.1.4).
3. Il forward è stato **corretto** (`HDL_PHASE.md` §2.1): ora bit-exact al riferimento su 0/240.000 control-step.
   SP2 parte quindi da fondamenta verificate, non da una claim.

## 3. Decisioni prese (con l'utente)
| decisione | scelta | motivo |
|---|---|---|
| Decode del campione | **LUT-64** | è il campione (§5bis) |
| ACC-IIDM | **double, sola simulazione** | l'IDM ha `sqrt(a·b)` e divisioni: renderlo fixed è **uno studio di quantizzazione a sé**, e nessuno l'ha chiesto. Il plant è **banco di prova**, non deployato |
| Struttura | **blocco UNICO** `s,v,dv,v_l → accel` | massimo plug&play. **Conseguenza accettata: il blocco NON è sintetizzabile** (mescola SNN fixed e IIDM double) — l'artefatto HDL-ready resta `Donatello_Champion` |
| Uscite | **solo `accel`** | interfaccia minima; per ispezionare i parametri si affianca un `Donatello_Champion` |
| Tipo degli ingressi | **fixed** (≥20 bit frazionari), Data Type Conversion **fuori** dal blocco | se domani il blocco diventa HDL-ready, l'interfaccia **non cambia** → niente rework. Coerente con gli altri blocchi |
| Loop velocità | **APERTO** | la velocità la altera il sistema che testa: il blocco **non** integra `v` né `s`, li riceve |

## 4. Design

```
 s,v,dv,v_l (fixed, >=20 frac)
      |
      +--> [ SNN Donatello LUT-64 ]  (fixed, cycle-accurate, edge-triggered)
      |          ~341 campioni/inferenza  -->  5 param (v0,T,s0,a,b)
      |                                              |
      +----------------------------------------------+--> [ ACC-IIDM open-loop ]  (double)
                                                          gated sul REFRESH dei param
                                                          NON integra v ne' s
                                                              |
                                                              +--> accel (double, tenuto)
```

- **Nome/collocazione**: `Donatello_ACC_IIDM` in `snn_champions_lib.slx`. Niente prefisso `Champion`/`LUT`: segnala che
  è **altro**. La Description dichiara esplicitamente **sola simulazione, NON sintetizzabile**.
- **Semantica**: **1 cambio d'ingresso = 1 control-step = DT 0.1 s** (lo stesso DT di traiettorie, training e
  `cf_plant_lib/ACC_IIDM`). Ogni ingresso va tenuto **≥ ~341 campioni** (fisica del time-mux).
- **Stato interno ammesso**: solo il filtro OU che stima `a_l` — è parte del **controllore ACC**, non del loop del
  veicolo. Tutto il resto è memoryless.
- **Sorgente dell'IIDM**: port dell'`ACC_IIDM` esistente (`build_plant_lib.m`), **rimuovendo l'integrazione**
  (`v = v + accel*DT`, `s = s + (vl - v_old)*DT`) e prendendo `s`, `v`, `dv` dagli ingressi.

## 5. ⚠️ Il punto critico: il gating dell'IIDM
`DT` sopravvive all'apertura del loop **solo** dentro il filtro OU: `alf = ALPHA*alf + (1-ALPHA)*(Δv_l/DT)`.

> **Se l'IIDM girasse a ogni clock**, per **340 campioni su 341** vedrebbe `Δv_l = 0` (l'ingresso è tenuto costante
> durante l'inferenza) → stimerebbe **`a_l ≈ 0`**, e il blend CAH sarebbe sistematicamente sbagliato. **In silenzio.**

Per questo l'IIDM **deve** girare **una volta per control-step**, cioè quando i parametri si rinfrescano (il `valid`
interno della SNN). Così `Δv_l` è la differenza vera fra due control-step e **`DT = 0.1` torna corretto**.
*È lo stesso genere di trappola del §2.1: un errore che non fa rumore. Va verificato, non assunto.*

## 6. Verifiche (sul DATASET, mai su un caso singolo)
| verifica | criterio |
|---|---|
| **Catena completa vs riferimento**: `s,v,dv,v_l → accel` del blocco vs `MEX + snn_decode_lut(.,64) + acc_iidm_accel` (port double) su N traiettorie di `test_dataset.mat` | **dmax = 0** |
| **Gating del filtro OU**: `a_l` stimato dentro il blocco vs `a_l` di riferimento calcolato a control-step | **dmax = 0** (becca l'IIDM che girasse a ogni clock: `a_l → 0`) |
| **Loop aperto**: il blocco non deve avere stato di velocità | `s`,`v` cambiati dall'esterno → `accel` cambia di conseguenza; nessuna deriva da stato interno |
| **Sync coi sorgenti** | `run_block_sync_check` esteso al nuovo blocco |

## 7. Fuori scope (esplicito)
- **ACC-IIDM su FPGA** (fixed/HDL-ready): è un **SP a sé** — `sqrt(a·b)` e le divisioni sono lo stesso genere di
  problema che per la sigmoide ha richiesto una LUT. Se servirà, avrà i suoi numeri e i suoi cancelli.
- Chiudere il loop dentro il blocco.
- Altri champion (SP2 è **solo Donatello**) e altri plant (Gipps/OVM…).

## 8. File
- `matlab/build_hdl_variants.m` → aggiunge `Donatello_ACC_IIDM` *(oppure builder separato: da decidere nel piano)*
- `matlab/acc_iidm_open.m` (nuovo) → IIDM open-loop, sorgente inlinato nella chart
- `matlab/run_block_acciidm_test.m` (nuovo) → verifiche §6 sul dataset
- `matlab/snn_champions_lib.slx` (rigenerato) · `document/DECODE_LUT_SWEEP.md` o doc dedicato (da decidere)
