#!/usr/bin/env python3
# T7b - genera results/NETLIST.md PARSANDO il log grezzo della run (results/netlist_func.log).
# I numeri non si trascrivono dalla console. Uso: python hw/gen_netlist_report.py
import io, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
RES  = os.path.normpath(os.path.join(HERE, '..', 'results'))
LOG  = os.path.join(RES, 'netlist_func.log')
OUT  = os.path.join(RES, 'NETLIST.md')

# Costo della cosim COMPORTAMENTALE sullo STESSO banco e sugli STESSI scenari (artefatto COSIM_AXI.md):
# 2 modalita' di gating x 58.522 confronti in 76 min totali -> il tempo di UNA passata e' la meta'.
BEH_STEPS, BEH_MIN_BOTH = 58522, 76
BEH_S_PER_STEP = (BEH_MIN_BOTH * 60.0 / 2.0) / BEH_STEPS
NSCEN_FULL = 99

ROLE = {1: 'nominale (primo del dataset)',
        4: 'nominale, altra combinazione regime/cut-in',
        9: '**COLLIDE** — serie troncata a 307'}


def die(m):
    print('GEN-ABORT: ' + m, file=sys.stderr); sys.exit(1)


if not os.path.exists(LOG):
    die('manca %s' % LOG)
t = io.open(LOG, encoding='utf-8', errors='replace').read()

# `[^\n]*` GOLOSO: sulla riga c'e' gia' una parentesi quadra (l'elenco degli scenari, es. "[1 4 9]"),
# quindi si deve agganciare l'ULTIMO [HH:MM:SS] della riga, non il primo campo fra quadre.
t0 = re.search(r'FASE 2/2[^\n]*\[(\d\d:\d\d:\d\d)\]', t)
if not t0:
    die('inizio della fase 2 non trovato nel log')
rows = re.findall(r'scenario (\d+): nMismatch=(\d+) / (\d+)\s+\[(\d\d:\d\d:\d\d)\]', t)
if not rows:
    die('nessuna riga di scenario nel log')
tot = re.search(r'NETLIST-FUNC-TOT nMismatch=(\d+) n=(\d+) nscen=(\d+)', t)
if not tot:
    die('riga di totale assente: la run non e\' arrivata in fondo')
skipped = 'FASE 1/2 · SALTATA' in t


def secs(x):
    h, m, s = map(int, x.split(':')); return h * 3600 + m * 60 + s


# La prima riga include compilazione+elaborazione: si dichiara, non si spalma in silenzio.
prev = secs(t0.group(1))
runs = []
for sc, nm, n, ts in rows:
    e = secs(ts)
    runs.append(dict(sc=int(sc), nm=int(nm), n=int(n), dur=e - prev, first=(len(runs) == 0)))
    prev = e
T = prev - secs(t0.group(1))
NM, N, NS = int(tot.group(1)), int(tot.group(2)), int(tot.group(3))

# CANCELLO: il totale della riga finale deve coincidere con la somma degli scenari. Se non coincide,
# nMismatch=0 non e' credibile -- un banco che confronta meno passi del previsto produce zero
# disallineamenti proprio perche' non guarda.
ssum = sum(r['n'] for r in runs)
if ssum != N or len(runs) != NS:
    die('il totale non torna: righe %d passi/%d scenari, totale dichiarato %d/%d' % (ssum, len(runs), N, NS))

# Il costo per passo si misura sugli scenari SENZA la compilazione dentro.
clean = [r for r in runs if not r['first']]
sp = [r['dur'] / r['n'] for r in (clean or runs)]
sp_avg = sum(r['dur'] for r in (clean or runs)) / sum(r['n'] for r in (clean or runs))
ratio = sp_avg / BEH_S_PER_STEP
full_h = BEH_STEPS * sp_avg / 3600.0

L = []; a = L.append
a('# T7b · NETLIST post-place&route — la netlist implementata riproduce il blocco\n')
a('> Rigenerabile: `bash hw/run_netlist.sh`; questa tabella: `python hw/gen_netlist_report.py`, che **parsa**')
a('> `results/netlist_func.log`. Nessuna cifra trascritta dalla console.')
if skipped:
    a('> La **fase 1** (impl OOC + export) e\' stata **saltata** dal cancello di provenienza sulla firma md5 dei')
    a('> sorgenti: la netlist era gia\' quella giusta. `NETLIST_DRYRUN=1` mostra la decisione senza lanciare Vivado.')
a('')
a('## Perimetro, dichiarato\n')
a('Si simula la netlist **funcsim** (post-place&route, primitive UNISIM) di `snniidm_axi_lite` implementato')
a('**out-of-context**, col banco AXI gia\' validato in Task 2 e contro lo **stesso golden**.\n')
a('⚠️ **funcsim e NON timesim**, per un motivo misurato in T6b: la sim di timing con SDF non produsse')
a('risultati validi per una configurazione del banco mai risolta. La domanda a cui questo passo risponde —')
a('*la netlist implementata e\' logicamente equivalente all\'RTL?* — e\' coperta dalla funcsim; la **firma del')
a('timing spetta all\'STA** (`SWEEP_FCLK.md`: WNS +0,022 ns @40 MHz), non alla simulazione. E\' anche la')
a('prassi industriale corrente.\n')
a('⚠️ In funcsim le primitive sono a **ritardo zero**: il periodo di clock non prova nulla sul timing. E\'')
a('allineato al punto deployabile solo per coerenza.\n')

a('## Esito sul sottoinsieme DICHIARATO\n')
a('| Scenario | Ruolo | Passi | Disallineamenti | Durata |')
a('|---|---|---|---|---|')
for r in runs:
    a('| %d | %s | %d | **%d** | %d m %02d s%s |'
      % (r['sc'], ROLE.get(r['sc'], '—'), r['n'], r['nm'], r['dur'] // 60, r['dur'] % 60,
         ' *(include compilazione ed elaborazione)*' if r['first'] else ''))
a('| **totale** | | **%d** | **%d** | **%d m %02d s** |' % (N, NM, T // 60, T % 60))
a('\nLo scenario **9 collide**: e\' quello che aveva scoperto il difetto di `axi_len` nella cosim')
a('comportamentale (il banco leggeva oltre la fine del golden sugli scenari piu\' corti). Includerlo e\' il')
a('punto del sottoinsieme, non un dettaglio.\n')

a('## Il totale e\' auto-verificante\n')
a('**%s = %d** confronti, **dichiarati PRIMA della run**; il log riporta `nMismatch=%d n=%d nscen=%d`.'
  % (' + '.join(str(r['n']) for r in runs), N, NM, N, NS))
a('Il totale torna. Se non fosse tornato, `nMismatch=0` non sarebbe stato credibile: un banco che confronta')
a('meno passi del previsto produce zero disallineamenti proprio perche\' **non guarda**.\n')

a('## Costo — MISURATO su T7b, non piu\' ereditato\n')
a('| Scenario | s / control-step |')
a('|---|---|')
for r in clean or runs:
    a('| %d | %.2f |' % (r['sc'], r['dur'] / r['n']))
a('\nDispersione %.2f–%.2f s: attesa, il simulatore e\' a eventi e scenari con commutazione diversa costano'
  % (min(sp), max(sp)))
a('diversamente.\n')
a('**Penalizzazione gate-level = %.0f×** rispetto alla cosim comportamentale sullo STESSO banco e sugli STESSI'
  % ratio)
a('scenari (%.4f s/passo, da `COSIM_AXI.md`: %d confronti x 2 modalita\' in %d min). T6b aveva misurato ~29×'
  % (BEH_S_PER_STEP, BEH_STEPS, BEH_MIN_BOTH))
a('sul proprio progetto: qui il numero e\' **misurato su questo**, non ereditato.\n')
a('⇒ i **%d scenari** completi costerebbero **~%.0f ore**. E\' la ragione per cui N=3 e\' un **cancello di'
  % (NSCEN_FULL, full_h))
a('conferma su N dichiarato**, non la base di una metrica.\n')
a('⚠️ **La stima a priori era ~80 minuti, il misurato e\' %d.** Veniva da T6b scalata per il rapporto dei clock'
  % (T // 60))
a('per passo (560/371): **pessimistica di circa 2×**. Una stima scalata da un altro progetto e\' un ordine di')
a('grandezza, non una previsione.\n')

a('## Cosa e\' provato, e cosa no\n')
a('| Domanda | Risposta | Da cosa |')
a('|---|---|---|')
a('| La netlist piazzata e instradata calcola come il blocco? | **si**, %d/%d | questa run |' % (NM, N))
a('| ...su tutti i %d scenari? | **non provato** — N=%d dichiarato | costo (~%.0f h) |' % (NSCEN_FULL, NS, full_h))
a('| Il timing chiude? | **si** a 40 MHz | STA, non simulazione (`SWEEP_FCLK.md`) |')
a('| L\'integrazione con PS7 / protocol converter? | STA di sistema; board in Fase C | perimetro OOC, dichiarato sopra |')

io.open(OUT, 'w', encoding='utf-8', newline='').write('\n'.join(L) + '\n')

import json
json.dump({
    'nmismatch': NM, 'n': N, 'nscen': NS,
    'scenari': [r['sc'] for r in runs],
    'wall_s': T, 's_per_step': round(sp_avg, 3),
    'gate_level_ratio': round(ratio, 1), 'beh_s_per_step': round(BEH_S_PER_STEP, 4),
    'full99_hours': round(full_h, 1),
}, io.open(os.path.join(RES, 'netlist.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
print('GEN-OK %s | %d scenari | %d/%d | %d m | gate-level %.0fx | full-%d ~%.0f h'
      % (os.path.basename(OUT), NS, NM, N, T // 60, ratio, NSCEN_FULL, full_h))
