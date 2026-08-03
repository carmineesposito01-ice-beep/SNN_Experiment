#!/usr/bin/env bash
# T7b — NETLIST: le due fasi in sequenza (impl OOC + export funcsim, poi simulazione sul sottoinsieme).
# La seconda fase parte SOLO se la prima e' andata a buon fine: un export mancato non deve diventare
# "zero disallineamenti" su una netlist che non esiste.
#
# Uso: bash run_netlist.sh [FCLK] [CLKHALF] ["<lista scenari>"]
#   default: 40 MHz (frequenza deployabile misurata dallo sweep), semi-periodo 12.5 ns, scenari "1 4 9".
#
# SOTTOINSIEME DICHIARATO "1 4 9" -- e' lo stesso smoke di T7a, quindi il riferimento e' gia' validato:
#   1 = nominale · 4 = nominale · 9 = COLLIDE (N=307 invece di 600, percorso piu' corto e caso limite).
# Totale atteso: 600 + 600 + 307 = 1507 confronti. Dichiarato PRIMA della run: se il totale non torna,
# il risultato non e' credibile nemmeno se nMismatch=0.
#
# ⚠️ In funcsim le primitive sono a ritardo ZERO: il periodo di clock NON prova nulla sul timing. La firma
#    del timing e' dell'STA (sweep FCLK). Qui il periodo e' allineato al punto deployabile solo per coerenza.
set -u
VIV="C:/AMDDesignTools/2026.1/Vivado/bin"
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/../results"
SRC="C:/t7bimpl/src"        # sorgenti gia' preparati dallo sweep (10 .v del DUT + wrapper + compile_order)
ROOT="C:/t7bnl"             # work-dir CORTA senza spazi
WORK="C:/t7bw"              # dove stanno i .mem generati da gen_axi_golden.m
FCLK="${1:-40}"; CLKHALF="${2:-12.5}"; SCEN="${3:-1 4 9}"

# CANCELLO PRELIMINARE (prima di ~50 minuti di calcolo, non dopo)
nv=$(ls "$SRC"/*.v 2>/dev/null | wc -l)
[ "$nv" -ge 11 ] || { echo "NETLIST-ABORT: solo $nv .v in $SRC (attesi >=11)"; exit 1; }
[ -s "$SRC/compile_order.txt" ] || { echo "NETLIST-ABORT: compile_order.txt mancante"; exit 1; }
for i in $SCEN; do
  for k in stim gold len; do
    [ -s "$WORK/axi_${k}_$i.mem" ] || { echo "NETLIST-ABORT: manca $WORK/axi_${k}_$i.mem"; exit 1; }
  done
done

# ---- CANCELLO DI PROVENIENZA: la fase 1 si rifa' solo se serve ----
# netlist_par.tcl CANCELLA la work-dir, quindi un rilancio rifarebbe ~10 minuti di implementazione anche
# quando la netlist esistente e' gia' quella giusta. Il criterio NON e' "il file esiste" -- sarebbe il modo
# di simulare in silenzio una netlist stantia: e' la FIRMA dei sorgenti che l'hanno prodotta.
# Forma a INTEGRITA' DEL FILE, non rigenera-e-confronta: makehdl non e' deterministico sui nomi temporanei
# interni, quindi un confronto per rigenerazione fallirebbe sempre (accertato in T7b).
SIG="$(cat "$SRC"/*.v "$SRC/compile_order.txt" | md5sum | cut -d' ' -f1)-fclk${FCLK}"
STAMP="$ROOT/netlist/src.sig"
if [ -s "$ROOT/netlist/snniidm_axi_lite_func.v" ] && [ -f "$STAMP" ] && [ "$(cat "$STAMP")" = "$SIG" ]; then
  echo "=== FASE 1/2 · SALTATA: netlist gia' presente e con la firma dei sorgenti attuali  [$(date +%H:%M:%S)] ==="
  echo "  firma: $SIG"
  SKIP1=1
else
  # Il motivo va detto ESATTO: "firma diversa" quando manca solo la netlist manderebbe a cercare
  # una modifica ai sorgenti che non c'e' stata.
  if   [ ! -s "$ROOT/netlist/snniidm_axi_lite_func.v" ]; then echo "  motivo: netlist assente o vuota"
  elif [ ! -f "$STAMP" ];                                then echo "  motivo: firma dei sorgenti mai registrata"
  else echo "  motivo: firma diversa -- attesa $SIG, trovata $(cat "$STAMP")"; fi
  echo "=== FASE 1/2 · impl OOC @${FCLK} MHz + export funcsim  [$(date +%H:%M:%S)] ==="
  SKIP1=0
fi
[ "${NETLIST_DRYRUN:-0}" = "1" ] && { echo "DRYRUN: fase1_saltata=$SKIP1"; exit 0; }

if [ "$SKIP1" = "0" ]; then
  "$VIV/vivado.bat" -mode batch -notrace -nojournal -nolog \
    -source "$HERE/netlist_par.tcl" -tclargs "$SRC" "$ROOT" "$FCLK" "$OUT" 6 2>&1 \
    | grep -E "^(NETLIST|ERROR:)" | head -20
  [ -s "$ROOT/netlist/snniidm_axi_lite_func.v" ] \
    || { echo "NETLIST-ABORT: export funcsim NON prodotto -- niente fase 2"; exit 1; }
  printf '%s' "$SIG" > "$STAMP"      # la firma si scrive DOPO l'export riuscito, mai prima
fi
echo "  netlist: $(wc -l < "$ROOT/netlist/snniidm_axi_lite_func.v") righe"

echo "=== FASE 2/2 · funcsim sul sottoinsieme [$SCEN]  [$(date +%H:%M:%S)] ==="
bash "$HERE/run_netlist_func.sh" "$WORK" "$ROOT/netlist" "$HERE" 600 0 "$CLKHALF" "$SCEN"
echo "=== FINE  [$(date +%H:%M:%S)] ==="
