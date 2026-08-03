#!/usr/bin/env bash
# FACCIATA 1 della Fase C: a stadi, uno per volta.
#
# Non contiene logica: chiama phase_c.cli, che e' lo stesso codice che chiama il notebook.
# Se questo file iniziasse a decidere qualcosa per conto suo, il cancello di parita'
# (stadio `parity`) diventerebbe rosso -- ed e' esattamente cio' che deve fare.
set -u
cd "$(dirname "$0")"

STAGE="${1:-help}"
shift || true

case "$STAGE" in
  c0|c1|c2|c3)
    python -m phase_c.cli "$STAGE" --frontend script "$@" ;;

  p1)
    python -m phase_c.platoon --frontend script "$@" ;;

  test)
    python -m pytest -q "$@" ;;

  parity)
    # Esegue LO STESSO stadio dalle due facciate e confronta gli artefatti.
    # Su p1 usa un sottoinsieme di scenari: il cancello prova che le facciate coincidono,
    # non rimisura P1 -- e un cancello che costasse mezz'ora non verrebbe eseguito.
    S="${1:-p1}"; shift || true
    LIM=""; [ "$S" = "p1" ] && LIM="--scenari ${PARITY_SCEN:-6}"
    mkdir -p results/_parity/script results/_parity/notebook
    python -m phase_c.cli "$S" --frontend script   --out-dir results/_parity/script   $LIM "$@" || exit 1
    python -m phase_c.cli "$S" --frontend notebook --out-dir results/_parity/notebook $LIM "$@" || exit 1
    python c_frontend_parity.py "results/_parity/script/$S.json" "results/_parity/notebook/$S.json" ;;

  notebook)
    # Cancello di riproducibilita' del notebook.
    # NON usa `jupyter nbconvert` direttamente: su questa postazione esce con 0 senza aver
    # eseguito nulla (zeromq rotto), quindi sarebbe un cancello verde per costruzione.
    # check_notebook.py guarda l'ARTEFATTO, e in piu' esegue le celle in un processo pulito.
    python check_notebook.py "$@" ;;

  summary)
    python - <<'PY'
import glob, json, os
files = sorted(glob.glob('results/*.json'))
if not files:
    print('nessun artefatto in results/. Stadi disponibili: ./run_phase_c.sh help')
for f in files:
    o = json.load(open(f, encoding='utf-8'))
    p = o['prov']
    print('%-28s sorgente=%-12s frontend=%-9s %s'
          % (os.path.basename(f), p.get('sorgente', '?'), p.get('frontend', '?'),
             p.get('timestamp', '')))
PY
    ;;

  # `list` e' il nome che usa gia' `python -m phase_c.cli list`: le due facciate devono
  # accettare lo stesso comando, altrimenti la documentazione e' giusta per una e sbagliata
  # per l'altra -- ed e' successo (STATO.md documentava `list`, che qui usciva con 2).
  help|list|*)
    cat <<'EOF'
uso: ./run_phase_c.sh <stadio>

  p1        plotone in simulazione            SENZA scheda
  test      la suite completa                 SENZA scheda
  parity    confronto fra le due facciate     SENZA scheda (su p1)
  notebook  esegue il notebook headless       SENZA scheda
  summary   elenca gli artefatti e la loro provenienza

  c0        vita del bus                      RICHIEDE la scheda
  c1        bit-esatto sui 99 scenari         RICHIEDE la scheda
  c2        anello chiuso                     RICHIEDE la scheda
  c3        potenza differenziale             RICHIEDE la scheda

Gli stadi su silicio sono gia' scritti e collaudati contro il mock; la procedura
di esecuzione e' in RUNBOOK.md.
EOF
    case "$STAGE" in help|list) exit 0 ;; *) exit 2 ;; esac ;;
esac
