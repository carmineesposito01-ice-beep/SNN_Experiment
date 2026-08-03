#!/usr/bin/env bash
# tier_signature_gate.sh — verifica che il VHDL di ogni tier porti la firma attesa (SNN round + decode + splitpipe).
# Firme (da snn_variants/README.txt e struct_gate di run_block_a_matrix.sh):
#   SNN:   R2 -> pCa=0,pCm=0,pCx=0 | R5 -> pCa>0,pCm=0,pCx=0 | R9 -> pCa>0,pCm>0,pCx>0
#   decode: fused -> dodec>0,dph=0 | p3 -> dph>0,q1k>0,s3a=0 | p5 -> dph>0,s3a>0,q1k=0
#   splitpipe: op_reg / op_prev presenti nel VHDL (registro operandi; i NOMI di funzione MATLAB
#              come local_normalize_ops NON sopravvivono alla generazione HDL, i persistent si')
# Sourceable: se caricato con `source`, definisce gate() senza eseguire main (per il test di sensibilita').
set -uo pipefail
gate() { # gate <dir> <round R2|R5|R9> <decode fused|p3|p5>
  local G="$1" rnd="$2" dec="$3" all fail=0
  all=$(find "$G" -name '*.vhd' -exec cat {} + 2>/dev/null)
  cnt() { printf '%s' "$all" | grep -c "$1" || true; }
  local ca cm cx dodec dph q1k s3a ops mul
  ca=$(cnt pCa); cm=$(cnt pCm); cx=$(cnt pCx)
  dodec=$(cnt dodec); dph=$(cnt dph); q1k=$(cnt q1k); s3a=$(cnt s3a)
  opreg=$(cnt op_reg); opprev=$(cnt op_prev)
  case "$rnd" in
    R2) [ "$ca" -eq 0 ] && [ "$cm" -eq 0 ] && [ "$cx" -eq 0 ] || { echo "FAIL $G SNN!=R2 (pCa=$ca pCm=$cm pCx=$cx)"; fail=1; } ;;
    R5) [ "$ca" -gt 0 ] && [ "$cm" -eq 0 ] && [ "$cx" -eq 0 ] || { echo "FAIL $G SNN!=R5 (pCa=$ca pCm=$cm pCx=$cx)"; fail=1; } ;;
    R9) [ "$ca" -gt 0 ] && [ "$cm" -gt 0 ] && [ "$cx" -gt 0 ] || { echo "FAIL $G SNN!=R9 (pCa=$ca pCm=$cm pCx=$cx)"; fail=1; } ;;
  esac
  case "$dec" in
    fused) [ "$dodec" -gt 0 ] && [ "$dph" -eq 0 ] || { echo "FAIL $G decode!=fused (dodec=$dodec dph=$dph)"; fail=1; } ;;
    p3)    [ "$dph" -gt 0 ] && [ "$q1k" -gt 0 ] && [ "$s3a" -eq 0 ] || { echo "FAIL $G decode!=p3 (dph=$dph q1k=$q1k s3a=$s3a)"; fail=1; } ;;
    p5)    [ "$dph" -gt 0 ] && [ "$s3a" -gt 0 ] && [ "$q1k" -eq 0 ] || { echo "FAIL $G decode!=p5 (dph=$dph s3a=$s3a q1k=$q1k)"; fail=1; } ;;
  esac
  [ "$opreg" -gt 0 ] && [ "$opprev" -gt 0 ] || { echo "FAIL $G splitpipe assente (op_reg=$opreg op_prev=$opprev)"; fail=1; }
  [ "$fail" = 0 ] && echo "OK  $(basename "$G"): SNN=$rnd decode=$dec splitpipe (pCa=$ca pCm=$cm pCx=$cx | dodec=$dodec dph=$dph q1k=$q1k s3a=$s3a | op_reg=$opreg op_prev=$opprev)"
  return "$fail"
}
main() {
  local ROOT="${1:-D:/zbd_tiers/vhdl}" rc=0
  gate "$ROOT/Donatello_SLOW"     R2 fused || rc=1
  gate "$ROOT/Donatello_BALANCED" R5 p3    || rc=1
  gate "$ROOT/Donatello_FAST"     R9 p5    || rc=1
  [ "$rc" = 0 ] && echo "=== G3 OK: firma HDL corretta sui 3 tier ===" || { echo "=== G3 FALLITO ==="; return 1; }
}
[ "${BASH_SOURCE[0]}" = "${0}" ] && main "$@"
