#!/usr/bin/env bash
# Driver della campagna di trade-off. RIPARTIBILE: un rilancio salta i punti gia' nel CSV.
#
#   run_campaign.sh <points.tsv> <outdir> [tag ...]
#     senza tag: tutti i punti della tabella;  con tag: solo quelli.
#
# FLUSSO PER PUNTO (protocollo §2.1 della spec, tutto misurato il 2026-07-20):
#   1. synth_point.tcl VINCOLATO a period = delay_OOC del punto.
#      Vincolare la sintesi conviene: su R17 ha dato 80.315 MHz contro 77.604 della sintesi libera,
#      con MENO area (7902 vs 7991 LUT, 3988 vs 4069 FF). Costa 312 s invece di 109 s.
#   2. impl_point.tcl allo stesso period.
#   3. Se WNS > 0 il tool si e' FERMATO al vincolo e il numero e' un LIMITE INFERIORE:
#      si rifa' l'implementazione al ritardo appena raggiunto (period - WNS). Al massimo 2 raffinamenti.
#      NON si stringe "a caso": sovra-vincolare PEGGIORA (su R17, 11 ns invece di 12.831 ha dato
#      -3.6% di Fmax e +2.5% di LUT).
#
# Ogni campo non estratto vale NA, mai vuoto: una tabella con celle vuote non si distingue da una
# tabella con misure mancanti.
set -uo pipefail          # NIENTE -e: un punto che fallisce non deve fermare la campagna

HERE="$(cd "$(dirname "$0")" && pwd)"
VIV="C:/AMDDesignTools/2026.1/Vivado/bin/vivado.bat"
PTS="${1:?uso: run_campaign.sh <points.tsv> <outdir> [tag ...]}"
OUT="${2:?uso: run_campaign.sh <points.tsv> <outdir> [tag ...]}"
shift 2 || true
SEL="$*"

TOP="${TOPMOD:-DUT}"      # top del design: DUT (punti IIDM) | Donatello_LUT64 (Blocco A)
mkdir -p "$OUT"
CSV="$OUT/campaign.csv"
[ -f "$CSV" ] || printf "tag,period_ns,wns,whs,tns,ths,delay_ns,fmax_mhz,valid,lut,lutram,ff,dsp,bram,n_impl,t_synth_s,t_impl_s,date\n" > "$CSV"

field() {   # field <log> <prefisso> <regex-sed> ; NA se assente
  local v; v=$(grep -m1 "$2" "$1" 2>/dev/null | sed -E "$3")
  [ -n "$v" ] && echo "$v" || echo "NA"
}

w() {   # path POSIX -> path che VIVADO sa leggere
  # ⚠️ MISURATO: Vivado NON legge /d/...  ->  `file isdirectory /d/zbd_tradeoff/...` = false e
  # `glob /d/.../*.vhd` = 0 file, quindi synth_point.tcl moriva con "nessun .vhd sotto <dir>".
  # Con D:/... lo stesso glob trova i 4 file. points.tsv (di ENTRAMBI i blocchi) memorizza path POSIX,
  # quindi la conversione va fatta qui, al punto d'uso.
  # Non era mai emerso perche' l'unico test della campagna aveva il DCP PRE-CARICATO: il ramo della
  # sintesi non veniva eseguito e il path non veniva mai usato.
  cygpath -m "$1" 2>/dev/null || echo "$1"
}

verdict() {   # verdict <wns-del-migliore> <n-tentativi>
  # VALIDA           il migliore ha WNS <= 0: il tool ha spinto al massimo.
  # CONFERMATA       il migliore ha WNS > 0 MA un tentativo piu' stretto e' stato fatto e NON ha
  #                  migliorato -> non e' piu' un limite inferiore, e' una misura sondata.
  # LIMITE-INFERIORE il migliore ha WNS > 0 e non e' stato sondato nulla di piu' stretto.
  if awk -v w="$1" 'BEGIN{exit !(w+0 <= 0)}'; then echo "VALIDA"
  elif [ "${2:-1}" -gt 1 ];                   then echo "CONFERMATA"
  else                                             echo "LIMITE-INFERIORE"; fi
}

impl_once() {   # impl_once <dir> <dcp> <period> <suffisso> -> stampa "wns delay"
  local d="$1" dcp="$2" per="$3" sfx="$4"
  "$VIV" -mode batch -source "$HERE/impl_point.tcl" \
     -tclargs "$(w "$dcp")" "$per" "$(w "$d")" > "$d/impl$sfx.log" 2>&1 || return 1
  local w r
  w=$(field "$d/impl$sfx.log" "^IMPL: WNS=" 's/.*WNS=([-0-9.]+).*/\1/')
  r=$(field "$d/impl$sfx.log" "^IMPL: ritardo=" 's/.*ritardo=([0-9.]+).*/\1/')
  echo "$w $r"
}

run_one() {
  local tag="$1" src="$2" per="$3"
  if grep -q "^${tag}," "$CSV"; then echo "SKIP $tag (gia' nel CSV)"; return 0; fi
  [ -d "$src" ] || { echo "FALLITO $tag: srcdir assente ($src)"; return 1; }
  local d="$OUT/$tag"; mkdir -p "$d"

  local t0=$SECONDS
  if [ ! -f "$d/post_synth.dcp" ]; then
    # $TOP: `DUT` per i punti IIDM, `Donatello_LUT64` per il Blocco A (rtl_gen_dut nomina il top come
    # il blocco di libreria). Si passa con TOPMOD=... nell'ambiente; assumere DUT faceva fallire la
    # sintesi con "ERROR: [Synth 8-439] module 'DUT' not found".
    "$VIV" -mode batch -source "$HERE/synth_point.tcl" \
       -tclargs "$(w "$src")" "$(w "$d")" "$tag" "$per" "$TOP" > "$d/synth.log" 2>&1 \
       || { echo "FALLITA SINTESI $tag (vedi $d/synth.log)"; return 1; }
  fi
  local ts=$((SECONDS-t0)); t0=$SECONDS

  # implementazione + eventuale raffinamento se il tool si e' fermato al vincolo
  local cur="$per" n=0 out wns delay sfx=""
  while : ; do
    out=$(impl_once "$d" "$d/post_synth.dcp" "$cur" "$sfx") \
      || { echo "FALLITA IMPL $tag (vedi $d/impl$sfx.log)"; return 1; }
    wns=$(echo "$out" | cut -d' ' -f1); delay=$(echo "$out" | cut -d' ' -f2)
    n=$((n+1))
    # WNS <= 0 -> massimo sforzo, misura valida. Altrimenti si riparte dal ritardo raggiunto.
    awk -v w="$wns" 'BEGIN{exit !(w+0 > 0)}' || break
    [ "$n" -ge 3 ] && { echo "  $tag: 3 tentativi, resta LIMITE-INFERIORE"; break; }
    cur="$delay"; sfx="_r$n"
    echo "  $tag: WNS=$wns > 0 -> rifaccio a $cur ns (tentativo $((n+1)))"
  done
  local ti=$((SECONDS-t0))

  # Si riporta il MIGLIORE dei tentativi, non l'ultimo. Ogni tentativo e' un'implementazione vera a un
  # vincolo dichiarato, e place&route NON e' monotono: su R17 il raffinamento a 12.451 e' atterrato a
  # 12.544, cioe' PEGGIO del tentativo che l'aveva prodotto. Prendere l'ultimo scarterebbe una misura
  # valida solo perche' e' arrivata prima.
  local L="" best=""
  for f in "$d"/impl.log "$d"/impl_r*.log; do
    [ -f "$f" ] || continue
    local dly; dly=$(field "$f" '^IMPL: ritardo=' 's/.*ritardo=([0-9.]+).*/\1/')
    [ "$dly" = "NA" ] && continue
    if [ -z "$best" ] || awk -v a="$dly" -v b="$best" 'BEGIN{exit !(a+0 < b+0)}'; then
      best="$dly"; L="$f"
    fi
  done
  [ -n "$L" ] || { echo "FALLITO $tag: nessun tentativo con un ritardo leggibile"; return 1; }
  cur=$(field "$L" '^IMPL: dcp=' 's/.*vincolo=([0-9.]+).*/\1/')
  wns=$(field "$L" '^IMPL: WNS=' 's/.*WNS=([-0-9.]+).*/\1/')
  delay="$best"
  printf "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n" \
    "$tag" "$cur" "$wns" \
    "$(field "$L" '^IMPL: WNS=' 's/.*WHS=([-0-9.]+).*/\1/')" \
    "$(field "$L" '^IMPL-TNS' 's/.*= *//')" \
    "$(field "$L" '^IMPL-THS' 's/.*= *//')" \
    "$delay" \
    "$(field "$L" '^IMPL: ritardo=' 's/.*Fmax=([0-9.]+).*/\1/')" \
    "$(verdict "$wns" "$n")" \
    "$(field "$L" '^IMPL-RES Slice LUTs' 's/.*= *//')" \
    "$(field "$L" '^IMPL-RES LUT as Memory' 's/.*= *//')" \
    "$(field "$L" '^IMPL-RES Slice Registers' 's/.*= *//')" \
    "$(field "$L" '^IMPL-RES DSPs' 's/.*= *//')" \
    "$(field "$L" '^IMPL-RES Block RAM Tile' 's/.*= *//')" \
    "$n" "$ts" "$ti" "$(date +%F_%T)" >> "$CSV"
  echo "OK $tag  delay=$delay ns  (sintesi ${ts}s, impl ${ti}s in $n tentativi)"
}

tail -n +2 "$PTS" | while IFS=$'\t' read -r tag src per fooc nota; do
  [ -z "${tag:-}" ] && continue
  if [ -n "$SEL" ] && ! echo " $SEL " | grep -q " $tag "; then continue; fi
  run_one "$tag" "$src" "$per"
done
echo "=== $(($(wc -l < "$CSV")-1)) punti nel CSV: $CSV ==="
