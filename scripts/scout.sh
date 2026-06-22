#!/usr/bin/env bash
# scout.sh — esegue un run ESPLORATORIO ("spurio") di train.py e ne PUSHA i risultati
# in una cartella a parte (results/_scratch/<tag>) cosi' sono recuperabili via git pull
# senza inquinare lo studio principale (results/EventProp_Study/...).
#
# Uso (da root repo, es. su Azure):
#   bash scripts/scout.sh --training_method eventprop_alif_full --tag SCOUT_X ...altri flag train.py...
#
# Richiede --tag. I risultati finiscono in results/_scratch/<tag>/ e vengono committati+pushati.
set -u
ARGS=("$@")
TAG=""
for ((i=0; i<${#ARGS[@]}; i++)); do
    if [ "${ARGS[$i]}" = "--tag" ]; then TAG="${ARGS[$((i+1))]}"; fi
done
if [ -z "$TAG" ]; then echo "ERRORE: --tag <nome> e' obbligatorio"; exit 1; fi

export PYTHONIOENCODING=utf-8 PYTHONUTF8=1
echo "[scout] run: $TAG"
python train.py "${ARGS[@]}"
RC=$?

DST="results/_scratch/$TAG"
mkdir -p "$DST/plots"
cp -f "checkpoints/$TAG"/*.csv "checkpoints/$TAG"/*.json "$DST/" 2>/dev/null || true
cp -f "checkpoints/$TAG"/plots/*.png "$DST/plots/" 2>/dev/null || true

BR=$(git branch --show-current)
git add "$DST"
git commit -q -m "scout: $TAG (train rc=$RC)" || { echo "[scout] niente da committare"; exit $RC; }
git pull -q --no-rebase --no-edit origin "$BR" || true
if git push -q origin "$BR"; then echo "[scout] pushed $DST"; else echo "[scout] push FALLITO (riprova: git push)"; fi
exit $RC
