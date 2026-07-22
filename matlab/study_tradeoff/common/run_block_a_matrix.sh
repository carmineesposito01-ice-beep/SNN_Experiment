#!/usr/bin/env bash
# Blocco A — matrice di accoppiamento SNN <-> decode.
#   run_block_a_matrix.sh [nome ...]      (senza argomenti: tutti gli esperimenti mancanti)
#
# Un blocco composto vale quanto il pezzo piu' lento. Gli esperimenti sono la diagonale bilanciata
# (SLOW/BALANCED/FAST) piu' due controlli che mostrano lo spreco nei due versi.
#
#   nome        decode  SNN  commit      attesa  ruolo
#   a_slow      fused   R2   bb50f9f0    ~30     candidato area minima
#   a_balanced  p3      R5   8b4843dc    ~57     candidato compromesso
#   a_fast      p5      R9   (corrente)  ~98     candidato margine massimo
#   a_ctrl_dec  p5      R2   bb50f9f0    ~30     ctrl: decode sovradimensionato
#   (a_ctrl_snn = fused+R9 e' gia' misurato: don_a1, 30,367)
#
# ⚠️ NIENTE WORKTREE: ai commit dei round SNN le funzioni decode_a1..decode_c NON esistevano (sono nate
#    dopo, nello studio IIDM), quindi li' il decode a fasi e' impossibile da costruire. L'unico file che
#    cambia fra i round e' snn_b2_fsm.m, con firma IDENTICA ai tre commit -> si scambia quello.
# ⚠️ L'albero corrente E' GIA' R9: per gli esperimenti con R9 non si scambia nulla.
# ⚠️ snn_b2_fsm.m si RIPRISTINA SEMPRE, anche se un passo fallisce: lasciarlo scambiato falserebbe in
#    silenzio tutti gli esperimenti successivi.
# ⚠️ Vivado spezza gli argomenti sugli SPAZI: mai passargli un path del repo (`1.Reti Neurali`).
set -uo pipefail

REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
COMMON="$REPO/matlab/study_tradeoff/common"
MATLAB="/c/Program Files/MATLAB/R2026a/bin/matlab.exe"
VIV="C:/AMDDesignTools/2026.1/Vivado/bin/vivado.bat"
OUT=/d/zbd_tradeoff/donatello
PTS="$REPO/matlab/study_tradeoff/donatello/points.tsv"

#            nome        variante  commitSNN(vuoto = corrente/R9)
#      nome        decode  snapshot-SNN                     firma-attesa
EXPS=( "a_slow      fused  snn_variants/snn_b2_fsm_R2.m  R2"
       "a_balanced  p3     snn_variants/snn_b2_fsm_R5.m  R5"
       "a_fast      p5     snn_variants/snn_b2_fsm_R9.m  R9"
       "a_ctrl_dec  p5     snn_variants/snn_b2_fsm_R2.m  R2"
       "a_fast6     p6     snn_variants/snn_b2_fsm_R9.m  R9" )


struct_gate() {   # struct_gate <dir-con-i-vhd> <variante> <tag>
  # ⚠️ CANCELLO STRUTTURALE sull'ARTEFATTO CHE SI STA PER MISURARE (non su quello appena costruito):
  # gira SEMPRE, anche quando la generazione e' stata saltata perche' il VHDL c'era gia'. Verificare
  # solo cio' che si e' appena prodotto lascia passare gli artefatti riciclati.
  # ⚠️ Si cerca in TUTTI i .vhd: la logica della chart sta in `SNN.vhd`, mentre `Donatello_LUT64.vhd`
  # e' solo il WRAPPER e non contiene NESSUN persistent. La prima versione grepava il wrapper ->
  # passava sempre 'fused' e bocciava sempre p3/p5.
  local G="$1" var="$2" tag="$3" snn="${4:-}"
  local a b c e
  a=$(cat "$G"/*.vhd 2>/dev/null | grep -c "dodec" || true)   # solo 'fused' (post-[A1])
  b=$(cat "$G"/*.vhd 2>/dev/null | grep -c "dph"   || true)   # contatore di fase: solo p3/p5
  c=$(cat "$G"/*.vhd 2>/dev/null | grep -c "q1k"   || true)   # registri di p3
  e=$(cat "$G"/*.vhd 2>/dev/null | grep -c "s3a"   || true)   # registri di p5
  # discriminante p5 vs p6: la fase 6 (dph->6) esiste SOLO in p6.
  # ⚠️ Si conta una TRANSIZIONE DI FASE (dph_temp := to_unsigned(16#06#...), cioe' la FSM che RAGGIUNGE
  # la fase 6), NON il nome della variabile `pr`: nell'architettura split, decode_c1/c2 sono inlinate
  # come funzioni locali anche in p5 (dove NON sono chiamate) -> `pr` compare nella loro dichiarazione
  # e il conteggio del nome dava 8 su un p5 CORRETTO (falso positivo, bocciava sp_fast). La transizione
  # di fase e' invece emessa solo se la fase esiste davvero nella macchina.
  local pr; pr=$(cat "$G"/*.vhd 2>/dev/null | grep -cE "16#06#" || true)
  case "$var" in
    fused) [ "$a" -gt 0 ] && [ "$b" -eq 0 ] || { echo "FALLITO $tag: chiesto fused (dodec=$a dph=$b)"; return 1; } ;;
    p3)    [ "$b" -gt 0 ] && [ "$c" -gt 0 ] && [ "$e" -eq 0 ] || { echo "FALLITO $tag: chiesto p3 (dph=$b q1k=$c s3a=$e)"; return 1; } ;;
    p5)    [ "$b" -gt 0 ] && [ "$e" -gt 0 ] && [ "$c" -eq 0 ] && [ "$pr" -eq 0 ] || { echo "FALLITO $tag: chiesto p5 (dph=$b s3a=$e q1k=$c pr=$pr)"; return 1; } ;;
    p6)    [ "$b" -gt 0 ] && [ "$e" -gt 0 ] && [ "$c" -eq 0 ] && [ "$pr" -gt 0 ] || { echo "FALLITO $tag: chiesto p6 (dph=$b s3a=$e q1k=$c pr=$pr)"; return 1; } ;;
  esac

  # ⚠️ FIRMA DELLA SNN — la meta' che mancava. Verificare solo il decode ha lasciato passare artefatti
  # con la SNN SBAGLIATA (cache slprj): `a_balanced` chiedeva R5 e aveva R9. Gli stadi nascono a round
  # noti -> i nomi discriminano: pCa da R4, pCm da R6, pC2i da R8, pCx da R9.
  #   R2: pCa=0 pCm=0 pCx=0   |   R5: pCa>0 pCm=0 pCx=0   |   R9: pCa>0 pCm>0 pCx>0
  if [ -n "$snn" ]; then
    local ca cm cx
    ca=$(cat "$G"/*.vhd 2>/dev/null | grep -c "pCa"  || true)
    cm=$(cat "$G"/*.vhd 2>/dev/null | grep -c "pCm"  || true)
    cx=$(cat "$G"/*.vhd 2>/dev/null | grep -c "pCx"  || true)
    case "$snn" in
      R2) [ "$ca" -eq 0 ] && [ "$cm" -eq 0 ] && [ "$cx" -eq 0 ] || { echo "FALLITO $tag: chiesta SNN R2 (pCa=$ca pCm=$cm pCx=$cx)"; return 1; } ;;
      R5) [ "$ca" -gt 0 ] && [ "$cm" -eq 0 ] && [ "$cx" -eq 0 ] || { echo "FALLITO $tag: chiesta SNN R5 (pCa=$ca pCm=$cm pCx=$cx)"; return 1; } ;;
      R9) [ "$ca" -gt 0 ] && [ "$cm" -gt 0 ] && [ "$cx" -gt 0 ] || { echo "FALLITO $tag: chiesta SNN R9 (pCa=$ca pCm=$cm pCx=$cx)"; return 1; } ;;
    esac
    echo "STRUCT $tag: decode=$var + SNN=$snn CONFERMATI (dodec=$a dph=$b q1k=$c s3a=$e | pCa=$ca pCm=$cm pCx=$cx)"
    return 0
  fi
  echo "STRUCT $tag: variante $var CONFERMATA (dodec=$a dph=$b q1k=$c s3a=$e)"
}

mkdir -p "$OUT"
[ -f "$PTS" ] || printf "tag\tsrcdir\tperiod_ns\tfmax_ooc\tnota\n" > "$PTS"

one() {
  local tag="$1" var="$2" com="$3" snn="$4"
  local d="$OUT/$tag"
  if [ -f "$d/src/Donatello_LUT64.vhd" ]; then echo "SKIP-GEN $tag"; else
    mkdir -p "$d/src"
    # snapshot CONGELATO invece dello scambio in-place del file condiviso: niente swap, niente
    # ripristino, niente trap. Lo scambio temporaneo aveva prodotto artefatti con meta' configurazione
    # sbagliata, e chiunque generasse qualcosa nel frattempo leggeva la SNN dell'esperimento in corso.
    [ -f "$REPO/matlab/$com" ] || { echo "FALLITO $tag: snapshot SNN assente ($com)"; return 1; }
    echo "  $tag: SNN da $com (il file condiviso non viene toccato)"
    # addpath invece di copiare il generatore in matlab/: una funzione vive in UN posto solo
    ( cd "$REPO/matlab" && "$MATLAB" -batch \
        "addpath('study_tradeoff/common'); gen_donatello_point('D:\\zbd_tradeoff\\donatello\\$tag\\gen', '$var', '$com')" ) \
        > "$d/gen.log" 2>&1
    local s; s=$(find "$d/gen" -name "Donatello_LUT64.vhd" 2>/dev/null | head -1)
    [ -n "$s" ] || { echo "FALLITO $tag: nessun VHDL (vedi $d/gen.log)"; return 1; }


    cp "$(dirname "$s")"/*.vhd "$d/src/" && rm -rf "$d/gen"
    echo "GEN $tag: $(ls "$d/src"/*.vhd | wc -l) file .vhd  [decode=$var]"
  fi

  # il cancello gira SEMPRE, anche se la generazione e' stata saltata: valida cio' che si MISURA
  struct_gate "$d/src" "$var" "$tag" "$snn" || return 1

  if grep -q "^${tag}$(printf '\t')" "$PTS"; then echo "SKIP-PER $tag"; else
    "$VIV" -mode batch -source "$COMMON/synth_point.tcl" \
       -tclargs "D:/zbd_tradeoff/donatello/$tag/src" "D:/zbd_tradeoff/donatello/$tag/free" \
                "${tag}_free" "" "Donatello_LUT64" > "$d/synth_free.log" 2>&1
    local wns; wns=$(grep -m1 "^SYNTH-RESULT" "$d/synth_free.log" | sed -E 's/.*WNS=([-0-9.]+).*/\1/')
    [ -n "$wns" ] || { echo "FALLITO $tag: sintesi libera (vedi $d/synth_free.log)"; return 1; }
    awk -v t="$tag" -v s="/d/zbd_tradeoff/donatello/$tag/src" -v w="$wns" -v v="$var" \
        'BEGIN{p=125.0-w; printf "%s\t%s\t%.3f\t%.3f\tDonatello LUT-64 decode=%s\n", t,s,p,1000.0/p,v}' >> "$PTS"
    rm -f "$d/free/post_synth.dcp"    # DCP della sintesi LIBERA: la campagna la rifa' VINCOLATA
    echo "PER $tag: WNS=$wns -> periodo $(awk -v w="$wns" 'BEGIN{printf "%.3f", 125.0-w}') ns"
  fi
}

SEL="$*"
for e in "${EXPS[@]}"; do
  set -- $e; tag="$1"; var="$2"; com="$3"; snn="$4"
  if [ -n "$SEL" ] && ! echo " $SEL " | grep -q " $tag "; then continue; fi
  echo "--- $tag (decode=$var, SNN=$snn @ $com) ---"
  one "$tag" "$var" "$com" "$snn"
done

# il file condiviso non viene MAI toccato: lo si verifica invece di prometterlo
echo "=== snn_b2_fsm intatto: $(git -C "$REPO" diff --quiet matlab/snn_b2_fsm.m && echo OK || echo '⚠️ MODIFICATO (non dovrebbe)') ==="
echo "=== points.tsv ==="; column -t -s$'\t' "$PTS" 2>/dev/null | cut -c1-120
