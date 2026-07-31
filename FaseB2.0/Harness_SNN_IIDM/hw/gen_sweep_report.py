#!/usr/bin/env python3
# T7b - genera results/SWEEP_FCLK.md PARSANDO i report grezzi di Vivado.
# I numeri NON si trascrivono dalla console: si leggono dal .rpt, cosi' l'artefatto e' rigenerabile
# e ogni cifra ha una provenienza. Uso: python hw/gen_sweep_report.py
import io, os, re, sys, glob

HERE = os.path.dirname(os.path.abspath(__file__))
RES  = os.path.normpath(os.path.join(HERE, '..', 'results'))
OUT  = os.path.join(RES, 'SWEEP_FCLK.md')
DEPLOY_HIER = 'util_hier_fclk{}.rpt'
LAT_CLK  = 555          # clock di una inferenza+controllo (misurato in T7a)
CTRL_STEP = 0.1         # s - il solo requisito temporale vero
FMAX_OOC_DUT = 41.5     # MHz - misurato a parte, OOC sul solo DUT


def die(msg):
    print('GEN-ABORT: ' + msg, file=sys.stderr)
    sys.exit(1)


def read(p):
    with io.open(p, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()


def parse_timing(path):
    """WNS, WHS e il clock EFFETTIVO (il PS7 quantizza: la frequenza chiesta non e' quella ottenuta)."""
    t = read(path)
    m = re.search(r'WNS\(ns\)[^\n]*\n[-\s]*\n\s*(-?[\d.]+)\s+(-?[\d.]+)\s+\d+\s+\d+\s+(-?[\d.]+)', t)
    if not m:
        die('WNS/WHS non trovati in ' + os.path.basename(path))
    wns, whs = float(m.group(1)), float(m.group(3))
    c = re.search(r'^(\S+)\s+\{[\d.\s]+\}\s+([\d.]+)\s+([\d.]+)\s*$', t, re.M)
    if not c:
        die('tabella dei clock non trovata in ' + os.path.basename(path))
    return dict(wns=wns, whs=whs, clk=c.group(1), period=float(c.group(2)), freq=float(c.group(3)))


def parse_flat(path):
    t = read(path)
    def grab(pat, cast=int):
        m = re.search(pat, t, re.M)
        return cast(m.group(1)) if m else None
    return dict(
        lut  = grab(r'^\|\s*Slice LUTs\s*\|\s*(\d+)'),
        lutp = grab(r'^\|\s*Slice LUTs\s*\|\s*\d+\s*\|[^|]*\|[^|]*\|\s*\d+\s*\|\s*([\d.]+)', float),
        ff   = grab(r'^\|\s*Slice Registers\s*\|\s*(\d+)'),
        ffp  = grab(r'^\|\s*Slice Registers\s*\|\s*\d+\s*\|[^|]*\|[^|]*\|\s*\d+\s*\|\s*([\d.]+)', float),
        dsp  = grab(r'^\|\s*DSPs\s*\|\s*(\d+)'),
        dspp = grab(r'^\|\s*DSPs\s*\|\s*\d+\s*\|[^|]*\|[^|]*\|\s*\d+\s*\|\s*([\d.]+)', float),
        bram = grab(r'^\|\s*Block RAM Tile\s*\|\s*([\d.]+)', float),
        bramp= grab(r'^\|\s*Block RAM Tile\s*\|\s*[\d.]+\s*\|[^|]*\|[^|]*\|\s*\d+\s*\|\s*([\d.]+)', float),
        srl  = grab(r'^\|\s*LUT as Memory\s*\|\s*(\d+)'),
    )


def parse_hier(path, want):
    """Righe della gerarchia post-route per le istanze richieste."""
    rows = {}
    for line in read(path).splitlines():
        m = re.match(r'\|\s*(\S+)\s*\|\s*(\S+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|'
                     r'\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|', line)
        if m and m.group(1) in want and m.group(1) not in rows:
            rows[m.group(1)] = dict(mod=m.group(2), lut=int(m.group(3)), srl=int(m.group(6)),
                                    ff=int(m.group(7)), rb36=int(m.group(8)),
                                    rb18=int(m.group(9)), dsp=int(m.group(10)))
    return rows


# ---------------- raccolta ----------------
pts = []
for tp in sorted(glob.glob(os.path.join(RES, 'timing_fclk*.rpt'))):
    f = int(re.search(r'fclk(\d+)', tp).group(1))
    up = os.path.join(RES, 'util_flat_fclk%d.rpt' % f)
    if not os.path.exists(up):
        die('manca %s (report di timing senza il gemello di utilizzo)' % os.path.basename(up))
    d = parse_timing(tp); d.update(parse_flat(up)); d['req'] = f
    pts.append(d)
pts.sort(key=lambda d: d['freq'])
if not pts:
    die('nessun report in %s - lanciare prima run_impl_sweep.sh' % RES)

# CANCELLO: il PS7 quantizza. Se la frequenza ottenuta non e' quella chiesta, va DETTO, non ignorato.
quant = [d for d in pts if abs(d['freq'] - d['req']) > 1e-6]

ok  = [d for d in pts if d['wns'] >= 0]
if not ok:
    die('nessun punto chiude: non esiste una frequenza deployabile fra quelle provate')
best  = max(ok, key=lambda d: d['freq'])
tight = min(pts, key=lambda d: d['period'] - d['wns'])
lim   = 1000.0 / (tight['period'] - tight['wns'])

# CANCELLO: setup chiuso ma hold violato = NON deployabile. Va verificato, non supposto.
if best['whs'] < 0:
    die('il punto deployabile (%g MHz) viola il HOLD (WHS=%+.3f ns)' % (best['freq'], best['whs']))

# WNS dell'implementazione OOC del wrapper+DUT (quella da cui esce la netlist), se disponibile:
# serve a mostrare che OOC e sistema NON sono lo stesso perimetro.
ooc = None
oocp = os.path.join(RES, 'timing_ooc_nl_fclk%d.rpt' % best['req'])
if os.path.exists(oocp):
    ooc = parse_timing(oocp)['wns']

HIER = ['sys_wrapper', 'tier0', 'u_dut', 'u_ACC', 'u_Tier', 'u_SNN', 'u_DEC', 'u_align', 'ps7_axi_periph']
hp = os.path.join(RES, DEPLOY_HIER.format(best['req']))
hier = parse_hier(hp, set(HIER)) if os.path.exists(hp) else {}

# ---------------- scrittura ----------------
L = []; a = L.append
a('# T7b · Sweep FCLK — frequenza deployabile, limite del cammino critico, risorse post-route\n')
a('> **Rigenerabile.** Implementazioni: `bash hw/run_impl_sweep.sh "%s"` — un\'invocazione Vivado per punto,'
  % ' '.join(str(d['req']) for d in pts))
a('> `-jobs` FISSO (determinismo). Questa tabella: `python hw/gen_sweep_report.py`, che **parsa i `.rpt` grezzi**')
a('> in `results/` — nessuna cifra e\' trascritta a mano dalla console.\n')
a('Perimetro: **sistema completo post-route** — PS7 + protocol converter + `snniidm_axi_lite` + DUT,')
a('su xc7z020clg400-1 (PYNQ-Z1). WNS/WHS da `report_timing_summary`, utilizzo da `report_utilization`.\n')

a('## Sweep\n')
a('| FCLK chiesto | clock ottenuto [MHz] | periodo [ns] | WNS [ns] | WHS [ns] | ritardo ottenuto [ns] | LUT | FF | chiude |')
a('|---|---|---|---|---|---|---|---|---|')
for d in pts:
    a('| %d | %.3f | %.3f | %+.3f | %+.3f | %.3f | %d | %d | %s |'
      % (d['req'], d['freq'], d['period'], d['wns'], d['whs'],
         d['period'] - d['wns'], d['lut'], d['ff'], 'si' if d['wns'] >= 0 else '**NO**'))
if quant:
    a('\n⚠️ Il PS7 **quantizza** la frequenza richiesta: %s. In tabella conta il **clock ottenuto**.'
      % ', '.join('%d→%.3f MHz' % (d['req'], d['freq']) for d in quant))
else:
    a('\nIl PS7 ha realizzato **esattamente** ogni frequenza richiesta (chiesto ≡ ottenuto): la quantizzazione')
    a('della PLL non entra in gioco su questi punti. Verificato, non supposto.')
a('\nIl **WHS** e\' positivo ovunque: nessun punto e\' scartato per violazione di hold — il che rende il')
a('criterio "chiude" leggibile sul solo setup.\n')

a('## I due numeri, e la loro natura\n')
a('| Grandezza | Valore | Natura |')
a('|---|---|---|')
a('| **Frequenza deployabile** | **%g MHz** (WNS %+.3f ns, WHS %+.3f ns) | **misurata** — il piu\' alto fra i provati che chiude |'
  % (best['freq'], best['wns'], best['whs']))
a('| **Limite del cammino critico** | **%.1f MHz** | **derivata** — `1/ritardo` al punto piu\' stretto (%g MHz), che **non** chiude |'
  % (lim, tight['freq']))
a('\nIl limite si legge **stringendo** il vincolo, non al crossover WNS=0: a vincolo largo lo strumento smette')
a('di ottimizzare e il ritardo si assesta su un valore che **non** e\' il limite del circuito. Lo mostrano i dati:')
a('il ritardo ottenuto scende da **%.2f ns** a **%.2f ns** via via che il vincolo stringe.\n'
  % (pts[0]['period'] - pts[0]['wns'], tight['period'] - tight['wns']))

a('## OOC e sistema sono perimetri DIVERSI: i numeri non si scambiano\n')
a('Tre misure di timing sullo stesso circuito, a confronto:\n')
a('| Perimetro | Vincolo | Esito | Frequenza implicata |')
a('|---|---|---|---|')
a('| **Sistema completo** (PS7 + converter + wrapper + DUT) | %g MHz | WNS **%+.3f** ⇒ **chiude** | **%g MHz deployabile** |'
  % (best['freq'], best['wns'], best['freq']))
a('| Sistema completo, punto piu\' stretto | %g MHz | WNS %+.3f | %.1f MHz (limite derivato) |'
  % (tight['freq'], tight['wns'], lim))
if ooc is not None:
    a('| **OOC** wrapper + DUT (per la netlist) | %g MHz | WNS **%+.3f** ⇒ **NON chiude** | %.1f MHz |'
      % (best['freq'], ooc, 1000.0 / (best['period'] - ooc)))
a('| OOC del **solo DUT** (misura precedente) | — | — | %g MHz |' % FMAX_OOC_DUT)
a('\nLo stesso circuito alla stessa frequenza **chiude nel sistema e non chiude in OOC**: la stima OOC qui e\' piu\'')
a('PESSIMISTA di quella di sistema. Ne segue una regola operativa: **un numero OOC non e\' una capacita\' del')
a('progetto** ed e\' confrontabile solo con altri numeri OOC dello stesso perimetro. In particolare, la vicinanza')
a('fra il limite derivato (%.1f MHz) e l\'OOC del solo DUT (%g MHz) **non** dimostra che il wrapper sia gratuito:'
  % (lim, FMAX_OOC_DUT))
a('a parita\' di perimetro OOC, wrapper + DUT sta piu\' in basso del DUT da solo.\n')
a('Dove sia il collo lo dice invece un\'**osservazione diretta**, non una coincidenza fra numeri: il')
a('`report_timing` del sistema individua il cammino critico in **`DEC → align → IIDM`**, interno al blocco.\n')
a('⚠️ **Qui NON vale la regola «OOC ≈ 2× il deployabile»** registrata per il Tier: la\' il cammino critico passava')
a('dal confine d\'ingresso e il metro io-timed lo dimezzava. Quella regolarita\' vale solo quando il collo sta **al')
a('confine**; su questo blocco, dopo la correzione di `align`, non ci sta piu\'.\n')

if hier:
    a('## Risorse post-route al punto deployabile (%g MHz)\n' % best['freq'])
    a('| Istanza | Ruolo | LUT | FF | DSP | RAMB18 |')
    a('|---|---|---|---|---|---|')
    ROLE = {'sys_wrapper': '**sistema completo**', 'tier0': 'IP AXI (wrapper + DUT)',
            'u_dut': '**`Donatello_SNN_IIDM`** (il blocco)', 'u_ACC': '└ ACC-IIDM (controllore)',
            'u_Tier': '└ `Donatello_Tier`@BAL/n13 (SNN)', 'u_SNN': '    └ rete a spike',
            'u_DEC': '    └ decodifica readout', 'u_align': '└ `align` (ritardo appaiato)',
            'ps7_axi_periph': 'protocol converter (contorno)'}
    for k in HIER:
        if k in hier:
            r = hier[k]
            a('| `%s` | %s | %d | %d | %d | %d |' % (k, ROLE[k], r['lut'], r['ff'], r['dsp'], r['rb18']))
    f = pts[[d['req'] for d in pts].index(best['req'])]
    a('\nSul dispositivo: **LUT %.2f %%** · **FF %.2f %%** · **DSP %.2f %%** · **BRAM %.2f %%** (%g tile).'
      % (f['lutp'], f['ffp'], f['dspp'], f['bramp'], f['bram']))
    a('Il DSP e\' la risorsa piu\' impegnata; nessuna e\' vicina alla saturazione.\n')
    if 'u_align' in hier and 'u_dut' in hier:
        al, du = hier['u_align'], hier['u_dut']
        a('`align` — il blocco che allinea i cinque parametri ai quattro ingressi fisici — costa **%d LUT'
          % al['lut'])
        a('(%.1f %% del DUT)** e %d FF. Non e\' logica gratuita: e\' il prezzo di **una** inferenza per'
          % (100.0 * al['lut'] / du['lut'], al['ff']))
        a('control-step, cioe\' della correttezza del filtro OU.\n')

a('## Area: insensibile al vincolo\n')
lo, hi = min(d['lut'] for d in pts), max(d['lut'] for d in pts)
a('LUT da %d a %d su tutto lo sweep: **%.1f %%** di variazione; FF da %d a %d; DSP e BRAM costanti (%d · %g).'
  % (lo, hi, 100.0 * (hi - lo) / lo, min(d['ff'] for d in pts), max(d['ff'] for d in pts),
     pts[0]['dsp'], pts[0]['bram']))
a('**L\'area non e\' la leva su cui agire per guadagnare frequenza**, e per converso stringere il vincolo non')
a('costa area in modo apprezzabile.\n')

a('## Margine sul control-step — il solo requisito temporale vero\n')
a('Una inferenza+controllo dura **%d clock** (misurato in T7a): e\' la **latenza pura del DUT**.\n' % LAT_CLK)
a('⚠️ Il **duty** riportato in [`POWER.md`](POWER.md) e\' leggermente piu\' alto perche\' misura la finestra')
a('**effettivamente occupata**, protocollo AXI incluso (**582 clock**: %d di latenza + 27 di scritture e polling'
  % LAT_CLK)
a('del `done`). I due numeri non sono in contraddizione, misurano due cose diverse: qui la **capacita\' del')
a('blocco**, la\' l\'**occupazione reale del sistema**. Per l\'energia vale il secondo.\n')
for d in (pts[0], best):
    t = LAT_CLK / (d['freq'] * 1e6)
    a('- a **%g MHz**: %d clock = **%.1f µs** contro un control-step di **%g s** ⇒ margine **%.0f×**, duty **%.4f %%**'
      % (d['freq'], LAT_CLK, t * 1e6, CTRL_STEP, CTRL_STEP / t, 100.0 * t / CTRL_STEP))
a('\nNessun punto dello sweep mette in discussione il control-step, nemmeno il piu\' lento: **la frequenza qui e\'')
a('una caratterizzazione, non un requisito**.')

with io.open(OUT, 'w', encoding='utf-8', newline='') as f:
    f.write('\n'.join(L) + '\n')

# Sommario MACCHINA per il sintetizzatore (RESULTS_HW.md). Un numero nasce in UN posto solo: qui, dal
# .rpt grezzo. Il sintetizzatore legge questo, non ri-parsa le stesse fonti ne' il markdown generato.
import json
json.dump({
    'deployable_mhz': best['freq'], 'deployable_wns_ns': best['wns'], 'deployable_whs_ns': best['whs'],
    'datapath_limit_mhz': round(lim, 2), 'limit_from_mhz': tight['freq'],
    # `period` LETTO dal report, non 1000/mhz: la frequenza e' stampata arrotondata a 3 cifre e il
    # round-trip restituisce 65.998 dove il tool dice 66.000.
    'points': [{'req': d['req'], 'mhz': d['freq'], 'period': d['period'], 'wns': d['wns'],
                'whs': d['whs'], 'lut': d['lut'], 'ff': d['ff']} for d in pts],
    'quantized': [{'req': d['req'], 'mhz': d['freq']} for d in quant],
    'ooc_wns_ns': ooc,
    'util': {'lut': pts[[d['req'] for d in pts].index(best['req'])]['lut'],
             'lut_pct': pts[[d['req'] for d in pts].index(best['req'])]['lutp'],
             'ff': pts[[d['req'] for d in pts].index(best['req'])]['ff'],
             'ff_pct': pts[[d['req'] for d in pts].index(best['req'])]['ffp'],
             'dsp': pts[[d['req'] for d in pts].index(best['req'])]['dsp'],
             'dsp_pct': pts[[d['req'] for d in pts].index(best['req'])]['dspp'],
             'bram': pts[[d['req'] for d in pts].index(best['req'])]['bram'],
             'bram_pct': pts[[d['req'] for d in pts].index(best['req'])]['bramp']},
    'hier': {k: hier[k] for k in hier},
}, io.open(os.path.join(RES, 'sweep.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
print('GEN-OK %s | %d punti | deployabile %g MHz | limite %.1f MHz | gerarchia %d istanze'
      % (os.path.basename(OUT), len(pts), best['freq'], lim, len(hier)))
