# CF-SNN Presentation — Session Resume & STATE (ENTRY POINT)

> **Role of this file:** the single **resume entry point + STATE** for the CF-SNN
> presentation deck (`Presentation_NN` track). It is a **guide to the docs that hold
> the detail** — read those, don't reconstruct from memory. It is **not** the general
> build procedure (that's the `create-presentation` skill).

## Location
- **Worktree:** `D:\Project_MBSE\1.Reti Neurali\Rete_SNN_Test\CF_FSNN\.worktrees\Presentation_NN` — **branch `Presentation_NN`**.
- **Deck:** `presentation/cf_fsnn_nn/` — entrypoint `slides_nn.qmd` → includes `_acts_nn/act0_progetto.qmd … act6_verdetto.qmd`. Theme `[../_shared/theme/cf_dark.scss, cf_slim.scss]`, math = KaTeX.
- **Other branches/tracks exist** in this repo (EventProp, Simulator, Loss_Study on `main` etc.) — **NOT this one**; ignore them here.
- **Working tree is DIRTY (uncommitted):** the user's content-edit pass on all 7 acts + `slides_nn.qmd` + `presentation/cf_fsnn_nn/assets/img/kineton_logo_placeholder.svg`, plus this session's 2 structural fence fixes. Nothing committed — commit only when the user asks. (Build artifacts, safe to ignore: `slides_nn.html` is **gitignored**; `_acts_nn/act0_progetto.html` + `_acts_nn/act0_progetto_files/` are **untracked** leftovers from a stray single-act render — deletable.)
- **This STATE doc is committed on `Presentation_NN`** so it survives `git clean`/`checkout`; the deck source edits around it stay uncommitted until you ask. (Its paused-track sibling lives in the non-git skill dir.)
- Rendered deck to view: `presentation/cf_fsnn_nn/slides_nn.html` (this render lands at the deck root, not `_output/`). Rebuild: from the deck dir, `"/c/Program Files/Quarto/bin/quarto" render slides_nn.qmd`.

## Current state (what just happened)
The user did a large **content-edit pass across all 7 acts**. It **broke navigation** — the deck froze and wouldn't advance past slide 2. **Root cause (fixed this session):** two **unclosed `:::` fenced divs** — `act0_progetto.qmd` "Perché una rete neurale?" had `::: {.threecol}` left open (a card-merge dropped its closing `:::`), and `act1_snn.qmd` "Reti Neurali — Come funziona?" had `::: {.twocol}` left open. An unclosed container swallows all following slides → reveal can't build sections → freeze. **Fix = added the one missing `:::` in each slide; zero written words changed.** Verified with a fragment-aware headless walk: **navigation now reaches the last slide ("Fine")**, KaTeX/JS/broken-images all clean.

## PENDING ACTIONS
1. **DECISION PENDING (immediate).** The slide **"T5 — FPGA-Friendly [Quantizzazione]"** (`_acts_nn/act5_fpga.qmd`, first `##`) is **visibly overloaded and overflows at the bottom** — 3 cards + a figure + 2 equations + a "Tre osservazioni" block on one slide (the overload is real by inspection; the exact px from DOM measurement is only indicative, ~100px+). The user was **asked** whether to fix it **without changing any text**, by **splitting it into two slides** (cards on one, figure+equations+observations on the other). **Awaiting the user's yes/no.** Constraint: **do NOT alter the user's written slide content without their OK** — only structural/layout moves.
2. **Known, minor, leave unless asked:** "Algoritmo PINN" overflows +12px (negligible); the uniform **`.eq`-box HCUT +31px** across ~17 slides is a **pre-existing cosmetic trait of the slim theme** (not from the edits) — touching it means a deck-wide theme change.
3. **Ongoing deck polish.** The interactive animations are **already built** (verified in the `.qmd` source): `pinnLoopToggle`, `archToggle`, `liToggle` (layer d'ingresso), `loToggle` (layer d'uscita), `decToggle` (decode) in act2; `bpttToggle`/`evpToggle` in act3; `rhoToggle`/`bfToggle` in act5. Anything marked `[▶ animato nel deck]` is a **finished** animation, not a placeholder. **The only genuine to-build items are:** (a) act1's `![](assets/img/membrane.png)` + `[▶ figura: principio NN — da creare]{.pill}` — a "principio NN" concept figure/widget still to create; (b) the **Kineton logo** (`assets/img/kineton_logo_placeholder.svg`) — swap in the real one when the user supplies it.

## Verify / gotcha
- The deck is a **nested-stack** design: each `# Parte N {.divider}` becomes a **vertical stack** holding its `##` slides. This is intentional and fine.
- **`verify_deck.py` caveat:** it tracks only the `h.v` index, so on the first slide carrying `.fragment` cards it reports a **false "navigation freeze N/40"** (a `Reveal.next()` there advances a *fragment*, not the slide). If nav actually works, ignore that flag; to re-verify properly, walk tracking the full `{h,v,f}` state. (This is a real bug in the skill's tool — logged in the paused side-track below.)

## Source docs — READ these (don't reconstruct from memory)
> **Authority order (important).** The **`.qmd` files under `_acts_nn/` are the current ground truth** for slide content and titles. The spec and plan below are **design-time** and have been **superseded in places** by the shipped deck + the 2026-07-12 correction batch (titles changed, cards rewritten, the closing "Restiamo a disposizione…" removed) — use them for **intent/structure, not current wording**, and **never reintroduce reverted text** from them. Of the two memory notes, **`cf-fsnn-presentation-slide-corrections.md` is the later/authoritative** one; `cf-fsnn-presentation-nn.md` has an older "restano …" to-do list that is now stale (its ρ/SEU/layer items are in fact done). When in doubt, **read the `.qmd`.**
>
> **Slide-numbering caution.** Three schemes don't line up: spec/plan use storyboard `s1–s32` (s5 omitted); `cf-fsnn-presentation-slide-corrections.md` uses absolute rendered numbers (~26–40); the deck now has ~40 sections. **Refer to slides by TITLE, not number**, to avoid mis-targeting.

- **Spec:** `docs/superpowers/specs/2026-07-11-presentation-nn-design.md` *(design-time; see authority note)*
- **Plan:** `docs/superpowers/plans/2026-07-11-presentation-nn-v1.md` *(design-time; see authority note)*
- **Build/design/animation knowledge:** the `create-presentation` skill (`C:\Users\user poco smart\.claude\skills\create-presentation\SKILL.md` + `references/`).
- **Deck history & decisions (memory):** `C:\Users\user poco smart\.claude\projects\D--Project-MBSE-0-Documenti-Platooning-Focus-Traffic-Flow-2025\memory\cf-fsnn-presentation-slide-corrections.md` (later/authoritative) and `…\memory\cf-fsnn-presentation-nn.md` (older, partly stale).

## PAUSED SIDE-TRACK (different project — don't lose it)
The bulk of this session was **`/ultra-optimize` on the `create-presentation` skill** (5 rounds, trend 17→16→14→10→8; 45 fixes applied; round-5's 8 findings + a `verify_deck.py` bug **not yet applied**). Its full STATE + captured findings live in:
`C:\Users\user poco smart\.claude\skills\create-presentation\OPTIMIZATION_STATE.md`.
The **deck is the live track** unless the user says otherwise.

## Ways of working (project constraints — honor these)
- **Investigate root cause; never patch symptoms or guess** (this session: found the real fence bug via systematic debugging; distinguished the `verify_deck.py` false-freeze from a real one with a fragment-aware walk).
- **Surface contradictions; don't silently change** a number/claim/design — reconcile with the source or ask.
- **Structural fixes must not alter the user's written slide content** without explicit OK.
- **Verify by rendering the real deck and walking it**, not by hoping.
- **Small, checkpointed changes; verify between them. Commit only when asked.**

## Tone
Reply in **Italian** (English technical terms are fine). Decisive, honest, **evidence-first, no hedging**; distinguish **pre-existing** issues from **newly-introduced** ones; **recommend, then act or offer** — don't over-ask.

---

## RESUME PROMPT (copy-paste into the new chat)

```
Stai riprendendo un lavoro SENZA contesto precedente — ricostruisci lo stato dai
documenti del repo, NON chiedermi di rispiegare, e NON basarti sulla memoria: LEGGI
i documenti indicati.

Lavoro principale — presentazione CF-SNN (deck reveal.js/Quarto):
- Worktree: D:\Project_MBSE\1.Reti Neurali\Rete_SNN_Test\CF_FSNN\.worktrees\Presentation_NN
  (branch Presentation_NN). Deck in presentation/cf_fsnn_nn/.
- PUNTO D'INGRESSO — leggi per primo:
  docs/superpowers/PRESENTATION_STATE.md  (in quel worktree)
  È la fonte unica di verità su dove siamo, le azioni pendenti, i modi di lavoro e il
  tono. Leggi i documenti a cui rimanda (spec, plan, skill create-presentation, le due
  note di memoria) invece di ricostruire a mente.
- Esiste ANCHE un side-track in pausa (ultra-optimize della skill create-presentation):
  PRESENTATION_STATE.md rimanda al suo STATE doc. Prendine nota, ma il deck è il lavoro
  vivo salvo mia indicazione contraria.

Modi di lavoro (in breve): investiga la causa radice, mai toppe o tentativi alla cieca;
fai emergere le contraddizioni invece di cambiare in silenzio; le correzioni STRUTTURALI
non devono mai alterare il contenuto scritto delle slide senza mio ok; verifica
renderizzando e navigando il deck reale, non sperando; commit solo quando lo chiedo;
modifiche piccole e verificate a checkpoint.

Tono: rispondi in italiano (termini tecnici in inglese ok); deciso e onesto, prima
l'evidenza, niente giri di parole; distingui i problemi preesistenti da quelli appena
introdotti; consiglia e poi agisci/proponi — non chiedere troppo.

Per prima cosa: leggi PRESENTATION_STATE.md e i documenti a cui rimanda, poi RIFERISCI
— (a) stato attuale, (b) branch/posizione, (c) ogni azione pendente e come la eseguiresti,
(d) modi di lavoro, (e) tono — e ATTENDI il mio via libera prima di fare qualsiasi cosa.
```
