# RESUME_PROCEDURE — Come allineare i documenti e riprendere il progetto in modo deterministico

> **Scopo.** Procedura riproducibile per due cose che l'utente chiede periodicamente:
> **(A)** «allinea tutti i documenti allo stato attuale per poter riprendere in una chat senza contesto»;
> **(B)** «dammi il prompt di ripresa».
> Seguendo questo documento passo-passo NON serve ri-spiegare come farlo, e non si dimentica nulla.
>
> **Branch:** `main` (lo studio `EventProp_Study` è stato consolidato in `main` il 2026-07-06; si lavora su `main`) · **Repo:** `D:\Project_MBSE\1.Reti Neurali\Rete_SNN_Test\CF_FSNN`

---

## 0. Principio

La ripresa a freddo poggia su **due canali**: (1) la **memoria** dell'assistente (`~/.claude/.../memory/MEMORY.md`
+ memorie, caricata automaticamente a inizio sessione) e (2) i **documenti nel repo**. I documenti del repo
**devono bastare da soli** (la memoria è un supplemento, non una dipendenza). Il punto d'ingresso unico è
**`document/EVENTPROP_STATUS.md` §0**, che contiene la **MAPPA DEI DOCUMENTI**: tutto il resto si raggiunge da lì.

---

## 1. Il set di documenti da tenere allineati (il "resume trail")

| Documento | Ruolo | Generato da script? |
|---|---|---|
| `document/EVENTPROP_STATUS.md` | **MASTER di ripresa** (§0 = stato in una riga + mappa doc + prossima azione + punti 1-N) | no (a mano) |
| `document/HOW_IT_WORKS_v3.md/.pdf` | Trio v3 — **teoria** (come funziona la rete) | **sì → `scripts/build_how_it_works_v3.py`** |
| `document/VALIDATION_REPORT_v3.md/.pdf` | Trio v3 — **risultati** (evaluate 6-tier, verdetto) | **sì → `scripts/build_validation_report_v3.py`** |
| `document/FPGA_REPORT.md/.pdf` | Trio v3 — **profilo hardware** (Fase A, 45 fig/10 sez.) | **sì → `scripts/build_fpga_report.py`** |
| `document/POST_FPGA_ROADMAP.md` | Fasi future ① simulatore · ② HDL · ③ FIL (decise) | no |
| `document/SIMULATOR_DESIGN.md` | Design MVP v1 del simulatore ① (approvato) | no |
| `document/FPGA_EVALUATE_DESIGN.md` / `FPGA_EVALUATION_FRAMEWORK.md` | Design/framework della valutazione FPGA | no |
| `MEMORY.md` (+ memorie) | Contesto supplementare + puntatore al master | no (memoria assistente) |

> **Regola d'oro:** i documenti del **trio v3 sono GENERATI**. Per correggerli si editano i **BUILDER in `scripts/`**,
> MAI i `.md`/`.pdf` (verrebbero sovrascritti al re-run e il `.pdf` non si aggiornerebbe). Poi si ri-eseguono i builder.

---

## 2. Procedura deterministica di ALLINEAMENTO (task A)

1. **`git pull origin main`** e verifica lo stato (`git status`, `git log --oneline -8`).
2. **Aggiorna il master `EVENTPROP_STATUS.md` §0**:
   - la **data** nell'header;
   - lo **"stato in una riga"** (cosa è fatto, cosa no) — rimuovi ogni «PROSSIMA AZIONE» ormai completata e metti quella nuova;
   - la **MAPPA DEI DOCUMENTI** (aggiungi eventuali nuovi documenti);
   - i **punti 1-N** (marca come ✅ ciò che è chiuso; aggiorna la prossima azione).
3. **Aggiorna gli altri documenti-stato** che hanno "prossime azioni" o stati datati: `POST_FPGA_ROADMAP.md` (intro +
   §5 domande aperte), `FPGA_EVALUATE_DESIGN.md` §6, `SIMULATOR_DESIGN.md` §0. Per il **trio v3**, se sono cambiati
   NUMERI/fatti: edita i **builder** e **ri-esegui** (`python scripts/build_how_it_works_v3.py`, `..._validation_report_v3.py`,
   `..._fpga_report.py`).
4. **Aggiorna la memoria** (`MEMORY.md` header + eventuale nuova memoria per decisioni durature).
5. **Verifica di consistenza cross-documento** (no duplicazioni, no contraddizioni, numeri coerenti). Per revisioni
   grosse usa un audit multi-agente (workflow a coppie HOW↔VAL, HOW↔FPGA, VAL↔FPGA + esaustività), come fatto il
   2026-07-03. Correggi le duplicazioni convertendole in **rimandi** (ogni informazione vive in UN solo documento).
6. **TEST DI RIPRESA A FREDDO** (obbligatorio, vedi §3).
7. **Commit + push** (rispettando i vincoli di §4). Messaggi chiari, senza `Co-Authored-By`.

---

## 3. Test di ripresa a freddo (come si verifica che i documenti bastino)

Lancia un **subagente SENZA contesto** (Agent tool, `general-purpose`) con un prompt che gli chiede di ricostruire
lo stato **leggendo SOLO i documenti** (partendo da `EVENTPROP_STATUS.md §0` e seguendo la mappa), e di **elencare
ogni gap / ambiguità / contraddizione / rimando rotto**. Deve rispondere: (a) stato, (b) prossima azione, (c) vincoli,
(d) i 4 champion + candidato deploy, (e) ruoli del trio, (f) bug n_ticks e numeri corretti, **(g) elenco critico dei gap**.

- Se (g) è vuoto e (a)-(f) sono corretti → i documenti **bastano**: procedi.
- Se emergono gap (numeri incoerenti, rimandi a file inesistenti, punti poco chiari) → **aggiorna/aggiungi documenti**
  e **ri-lancia il test** finché è pulito.

Il subagente NON ha la memoria dell'assistente: così il test verifica la **sufficienza dei soli documenti del repo**
(più robusto).

---

## 4. Modi di procedere (le "regole" del progetto — vanno nel prompt di ripresa)

- **NIENTE workaround / soluzioni-tampone.** Se un numero o un comportamento non torna, si indaga la **causa** (come
  col bug n_ticks: doppia divisione trovata, non aggirata).
- **Job pesanti** (training / evaluate / render HB_AZURE): su **Azure** (lanciati dall'utente) **oppure in locale** sui
  **4 champion versionati in `champions/`**. Mai **inventare numeri**: se non ci sono, dirlo.
- **Push SOLO quando Azure è fermo** (i notebook fanno auto-push → conflitti non-fast-forward). Se Azure gira, tenere
  i commit in locale.
- **Checkpoint `.pt`**: solo i 4 champion sono versionati (`champions/<tag>/best_model.pt`); tutto il resto è gitignorato.
- **Documenti generati da script**: correggere i **builder** in `scripts/`, mai i `.md`/`.pdf`.
- **Metrica primaria** = comportamento fisico (`val_data`), non la NRMSE nuda.
- **Design prima del codice**: per nuove funzionalità usare la skill di brainstorming, poi writing-plans; non saltare
  all'implementazione.
- **Commit** chiari e conventional, **senza `Co-Authored-By`** (attribution disabilitata). Branch `main`.

---

## 5. Il PROMPT DI RIPRESA (da incollare in una nuova chat post-clear)

> Copia-incolla questo. È volutamente **una guida a LEGGERE i documenti**, non un dump di informazioni.

```
Riprendi il progetto CF_FSNN. Non ho contesto in questa chat (post-clear): NON chiedermi lo stato,
ricostruiscilo dai documenti.

Repo: D:\Project_MBSE\1.Reti Neurali\Rete_SNN_Test\CF_FSNN — branch main.

1. git pull origin main
2. Leggi PRIMA document/EVENTPROP_STATUS.md §0 (COME RIPRENDERE): stato in una riga + MAPPA DEI
   DOCUMENTI + prossima azione. Segui la mappa: trio v3 (HOW_IT_WORKS_v3 = teoria, VALIDATION_REPORT_v3
   = risultati, FPGA_REPORT = hardware) e, per le fasi future, POST_FPGA_ROADMAP + SIMULATOR_DESIGN.
   Leggi anche i punti 1-N di §0.
3. La tua memoria (MEMORY.md + memorie) è già caricata: usala come contesto supplementare.

Poi, PRIMA di lavorare, dimmi in breve: (a) stato attuale, (b) prossima azione, (c) i vincoli/modi di
procedere che rispetterai — e ASPETTA la mia conferma.

Modi di procedere (rispettali sempre):
- Niente workaround: se un numero/comportamento non torna, indaga la CAUSA, non aggirarla.
- Job pesanti: su Azure (li lancio io) o in locale sui champion in champions/. Mai inventare numeri.
- Push solo quando Azure è fermo. Documenti del trio v3: edita i BUILDER in scripts/, non i .md/.pdf.
- Metrica primaria = comportamento fisico (val_data), non la NRMSE nuda.
- Design prima del codice (brainstorming → writing-plans). Commit senza Co-Authored-By.
```

---

## 6. Checklist finale (spuntare tutto)

- [ ] `git pull` fatto; stato noto.
- [ ] `EVENTPROP_STATUS.md` §0: data + stato-in-una-riga + mappa doc + prossima azione aggiornati.
- [ ] Altri doc-stato aggiornati (roadmap, FPGA_EVALUATE_DESIGN §6, SIMULATOR_DESIGN §0).
- [ ] Trio v3: se cambiati numeri, **builder editati e ri-eseguiti** (md+pdf rigenerati).
- [ ] `MEMORY.md` aggiornato.
- [ ] Consistenza cross-documento verificata (no duplicazioni/contraddizioni).
- [ ] **Test di ripresa a freddo** eseguito e PULITO.
- [ ] Prompt di ripresa (§5) fornito all'utente.
- [ ] Commit + push (Azure fermo), senza `Co-Authored-By`.
