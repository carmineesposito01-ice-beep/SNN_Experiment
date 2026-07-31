#!/usr/bin/env python3
# T7b - conta i TOGGLE dentro i SAIF e li salva in results/saif_stats.json.
#
# PERCHE' SERVE. `report_power` stampa 3 cifre decimali: a 0,026 W tutto cio' che sta sotto ~0,0005 W
# sparisce. Gli 8 carichi reali risultano cosi' bit-identici nel sommario, il che SEMBRA dispersione nulla.
# Guardando dentro l'artefatto, la dispersione c'e' (~3 % di commutazione) ma e' sotto la precisione di
# stampa. La stessa lettura rende MISURABILE il clock gating, che nel sommario dei watt e' invisibile
# perche' `report_power` deriva la potenza dei net di clock dal VINCOLO di frequenza, non dal SAIF.
#
# Uso: python hw/gen_saif_stats.py [cartella_saif]
import io, json, os, re, sys, glob

HERE = os.path.dirname(os.path.abspath(__file__))
RES  = os.path.normpath(os.path.join(HERE, '..', 'results'))
SDIR = sys.argv[1] if len(sys.argv) > 1 else 'C:/t7bw'
OUT  = os.path.join(RES, 'saif_stats.json')

RE_TC = re.compile(r'\(TC (\d+)\)')
RE_T1 = re.compile(r'\(T1 (\d+)\)')


def stats(p):
    tc = nets = 0; t1 = 0
    with io.open(p, encoding='utf-8', errors='replace') as f:
        for line in f:
            m = RE_TC.search(line)
            if m:
                tc += int(m.group(1)); nets += 1
            m1 = RE_T1.search(line)
            if m1:
                t1 += int(m1.group(1))
    return dict(nets=nets, tc=tc, t1=t1)


files = sorted(glob.glob(os.path.join(SDIR, 'saif_*.saif')))
if not files:
    print('GEN-ABORT: nessun SAIF in %s' % SDIR, file=sys.stderr); sys.exit(1)
d = {os.path.basename(f)[len('saif_'):-len('.saif')]: stats(f) for f in files}

# CANCELLO: se tutti i SAIF avessero lo STESSO conteggio, non starei misurando i carichi ma un default.
# Il controllo positivo e' l'idle: DEVE risultare ordini di grandezza sotto l'attivo.
act  = {k: v['tc'] for k, v in d.items() if k.startswith('act_')}
idl  = {k: v['tc'] for k, v in d.items() if k.startswith('idle_')}
if act and idl and min(act.values()) <= max(idl.values()) * 10:
    print('GEN-ABORT: i SAIF attivi non si distinguono dagli idle (attivo min %d, idle max %d): '
          'la registrazione non sta seguendo il carico' % (min(act.values()), max(idl.values())),
          file=sys.stderr)
    sys.exit(1)
if len(set(act.values())) == 1 and len(act) > 1:
    print('GEN-ABORT: gli %d SAIF attivi hanno TC IDENTICO (%d): stimoli diversi non possono dare '
          'commutazione identica al toggle -- sospetto che venga riletto sempre lo stesso file'
          % (len(act), next(iter(act.values()))), file=sys.stderr)
    sys.exit(1)

json.dump(d, io.open(OUT, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
sp = 100.0 * (max(act.values()) - min(act.values())) / max(act.values()) if act else 0
print('GEN-OK saif_stats.json | %d SAIF | attivi %d..%d (dispersione %.1f %%) | idle %s'
      % (len(d), min(act.values()), max(act.values()), sp,
         ' / '.join('%s=%d' % (k.replace('idle_', ''), v) for k, v in sorted(idl.items()))))
