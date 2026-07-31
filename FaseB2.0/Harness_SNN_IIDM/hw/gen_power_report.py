#!/usr/bin/env python3
# T7b - genera results/POWER.md PARSANDO i power_*.rpt prodotti da report_power.
# Uso: python hw/gen_power_report.py
import io, os, re, sys, glob

HERE = os.path.dirname(os.path.abspath(__file__))
RES  = os.path.normpath(os.path.join(HERE, '..', 'results'))
OUT  = os.path.join(RES, 'POWER.md')

WLS      = [1, 4, 28, 31, 55, 58, 73, 76]     # 8 carichi reali (regime x cut_in del dataset dei 99)
IDLE_W   = [200, 1000, 5000]
FCLK     = 40.0
ACT_CLK  = 582            # MISURATO da P0 (555 di latenza + 27 di protocollo AXI)
CTRL_S   = 0.1
LABEL = {1: 'highway | no-cut-in', 4: 'highway | cut-in', 28: 'urban | no-cut-in', 31: 'urban | cut-in',
         55: 'truck | no-cut-in', 58: 'truck | cut-in', 73: 'mixed | no-cut-in', 76: 'mixed | cut-in'}


def die(m):
    print('GEN-ABORT: ' + m, file=sys.stderr); sys.exit(1)


def parse(path):
    t = io.open(path, encoding='utf-8', errors='replace').read()
    def g(pat, cast=float):
        m = re.search(pat, t, re.M)
        return cast(m.group(1)) if m else None
    d = dict(
        tot  = g(r'^\|\s*Total On-Chip Power \(W\)\s*\|\s*([\d.]+)'),
        dyn  = g(r'^\|\s*Dynamic \(W\)\s*\|\s*([\d.]+)'),
        sta  = g(r'^\|\s*Device Static \(W\)\s*\|\s*([\d.]+)'),
        conf = g(r'^\|\s*Confidence Level\s*\|\s*(\w+)', str),
        covp = g(r'^\|\s*Design Nets Matched\s*\|\s*(\d+)%', int),
        covn = g(r'^\|\s*Design Nets Matched\s*\|\s*\d+%\s*\((\d+)/(\d+)\)', str),
    )
    m = re.search(r'^\|\s*Design Nets Matched\s*\|\s*\d+%\s*\((\d+)/(\d+)\)', t, re.M)
    d['cov'] = (int(m.group(1)), int(m.group(2))) if m else None
    for key, pat in (('clk', 'Clocks'), ('logic', 'Slice Logic'), ('sig', 'Signals'),
                     ('bram', 'Block RAM'), ('dsp', 'DSPs')):
        mm = re.search(r'^\|\s*%s\s*\|\s*(<?[\d.]+)\s*\|' % pat, t, re.M)
        d[key] = mm.group(1) if mm else None
    # CANCELLO: senza copertura SAIF il numero non e' pubblicabile. L'audit di T8 trovo' proprio questo
    # buco: watt riportati senza dire su quanti net l'attivita' fosse davvero nota.
    if d['tot'] is None or d['dyn'] is None:
        die('potenze non trovate in %s' % os.path.basename(path))
    if d['cov'] is None or d['conf'] is None:
        die('copertura SAIF o confidenza assenti in %s -- il watt non e\' pubblicabile senza'
            % os.path.basename(path))
    return d


def need(tag):
    p = os.path.join(RES, 'power_%s.rpt' % tag)
    if not os.path.exists(p):
        die('manca power_%s.rpt -- la fase energia non e\' completa' % tag)
    return parse(p)


act  = {i: need('saif_act_g1_wl%d' % i) for i in WLS}
idle = {w: need('saif_idle_g0_w%d' % w) for w in IDLE_W}
idle_g1 = need('saif_idle_g1_w200')
duty = need('saif_duty_g1')

# copertura: deve essere la STESSA per tutti (stesso progetto implementato); se non lo e', va detto.
covs = {r['cov'] for r in list(act.values()) + list(idle.values()) + [idle_g1, duty]}
confs = {r['conf'] for r in list(act.values()) + list(idle.values()) + [idle_g1, duty]}

dmax = max(act.values(), key=lambda r: r['dyn'])
imax = [i for i in WLS if act[i]['dyn'] == dmax['dyn']]
dmin = min(r['dyn'] for r in act.values())
duty_frac = ACT_CLK / (CTRL_S * FCLK * 1e6)
comp = dmax['dyn'] * duty_frac + idle[200]['dyn'] * (1 - duty_frac)

L = []; a = L.append
a('# T7b · Energia — misurata al duty REALE, non composta\n')
a('> Rigenerabile: `bash hw/run_power.sh 40 12.5 <stadio>` (idle | active | duty | report | all);')
a('> questa tabella: `python hw/gen_power_report.py`, che **parsa** i `power_*.rpt` in `results/`.\n')
a('Flusso: SAIF da simulazione della **netlist post-place&route** (funcsim), poi `report_power` in una')
a('sola sessione Vivado con `reset_switching_activity` fra un SAIF e il successivo.\n')

a('## Copertura e configurazione — dentro il numero, non in nota\n')
if len(covs) == 1 and len(confs) == 1:
    n, tt = covs.pop(); c = confs.pop()
    a('| Grandezza | Valore |')
    a('|---|---|')
    a('| Copertura SAIF (`Design Nets Matched`) | **%d / %d net = %.1f %%** |' % (n, tt, 100.0 * n / tt))
    a('| `Confidence Level` | **%s** |' % c)
    a('| Gating | **ON** (configurazione di deployment) per attiva e duty; idle misurata in entrambi |')
    a('| Frequenza | %g MHz (punto deployabile) |' % FCLK)
    a('\nSul **%.0f %%** dei net l\'attivita\' NON viene dal SAIF ma dal modello vectorless del tool: e\' una')
    a('proprieta\' della misura, e va letta insieme ai watt.\n' % (100.0 - 100.0 * n / tt))
else:
    a('⚠️ **La copertura o la confidenza NON sono uniformi fra i report**: %s · %s.'
      % (sorted(covs), sorted(confs)))
    a('I valori non sono direttamente confrontabili fra loro.\n')

a('## Idle: la finestra converge (la premessa e\' verificata, non assunta)\n')
a('| Finestra | Totale [W] | Dinamica [W] | Statica [W] |')
a('|---|---|---|---|')
for w in IDLE_W:
    r = idle[w]; a('| %d cicli | %.3f | %.3f | %.3f |' % (w, r['tot'], r['dyn'], r['sta']))
conv = len({round(idle[w]['dyn'], 4) for w in IDLE_W}) == 1
if conv:
    a('\nValori **identici** ⇒ l\'idle e\' **stazionario** e la finestra da 200 cicli basta. Il controllo')
    a('verifica anche la PREMESSA — che il circuito sia davvero fermo quando non calcola: se avesse avuto')
    a('FSM o contatori attivi il valore non si sarebbe stabilizzato. Non era garantito, ed e\' la condizione')
    a('perche\' il clock gating abbia qualcosa da spegnere.\n')
else:
    a('\n⚠️ **I valori NON coincidono**: l\'idle non e\' stazionario su queste finestre. La misura di idle')
    a('dipende dalla finestra scelta e **non** puo\' essere usata come valore unico.\n')

a('## Clock gating: idle gatata contro non gatata\n')
a('| Configurazione | Totale [W] | Dinamica [W] |')
a('|---|---|---|')
a('| idle **non** gatata (`gate_mode`=0) | %.3f | %.3f |' % (idle[200]['tot'], idle[200]['dyn']))
a('| idle **gatata** (`gate_mode`=1) | %.3f | %.3f |' % (idle_g1['tot'], idle_g1['dyn']))
if abs(idle_g1['dyn'] - idle[200]['dyn']) < 1e-9:
    a('\n⚠️ **Nessuna differenza nel sommario** — e in T6b fu accertato **perche\'**: `report_power` deriva la')
    a('potenza dei net di clock dal **VINCOLO di frequenza**, non dall\'attivita\' del SAIF. Li\' il gating')
    a('risulto\' comunque **funzionante** guardando i conteggi di commutazione DENTRO il SAIF (`TC 400 → 0`).')
    a('Conclusione onesta: il gating agisce, ma **il suo guadagno in watt non e\' misurabile con questo')
    a('flusso**. Nessuna stima viene qui spacciata per misura.\n')

a('## Fase attiva: %d carichi REALI\n' % len(WLS))
a('Uno per combinazione **regime × cut-in** del dataset dei 99 — sono **otto**, enumerate')
a('(18+9+18+9+12+6+18+9 = 99). Stimoli e golden sono quelli gia\' validati in T7a: ogni run di potenza vale')
a('anche come conferma funzionale.\n')
a('| Carico | Combinazione | Totale [W] | **Dinamica [W]** | Clocks | Logic | Signals | BRAM | DSP |')
a('|---|---|---|---|---|---|---|---|---|')
for i in WLS:
    r = act[i]
    a('| wl%d | `%s` | %.3f | **%.3f** | %s | %s | %s | %s | %s |'
      % (i, LABEL[i], r['tot'], r['dyn'], r['clk'], r['logic'], r['sig'], r['bram'], r['dsp']))
a('\n**Massimo OSSERVATO fra i carichi reali: %.3f W** (wl%s) · minimo %.3f W · dispersione %.1f %%.'
  % (dmax['dyn'], '/'.join(map(str, imax)), dmin, 100.0 * (dmax['dyn'] - dmin) / dmax['dyn'] if dmax['dyn'] else 0))
a('\n⚠️ E\' un **massimo osservato**, non un limite superiore. Il worst-case sintetico **non e\' stato')
a('prodotto**: in T6b risulto\' il **piu\' basso di tutti** (0,041 W contro 0,045 del massimo reale), quindi')
a('come bound e\' stato smentito su misura. Trovare il regime peggiore richiederebbe uno studio a se\'.\n')

a('## Duty REALE: misurato, non composto\n')
a('| Grandezza | Valore | Natura |')
a('|---|---|---|')
a('| Finestra attiva | **%d clock** | **misurata** dal banco (555 di latenza + %d di protocollo AXI) |'
  % (ACT_CLK, ACT_CLK - 555))
a('| Control-step | %d clock a %g MHz | definizione |' % (int(CTRL_S * FCLK * 1e6), FCLK))
a('| **Duty** | **%.4f %%** | derivata dalle due sopra |' % (100 * duty_frac))
a('| **Potenza al duty reale** | **%.3f W** totale · **%.3f W** dinamica | **MISURATA** su un control-step intero |'
  % (duty['tot'], duty['dyn']))
a('| Energia per control-step | **%.2f mJ** | `P × %g s` |' % (duty['tot'] * CTRL_S * 1000, CTRL_S))
a('\n⚠️ **Perche\' misurata e non composta.** In T6b/M3.4 la composizione lineare `P_att·δ + P_idle·(1−δ)`')
a('fu **invalidata** dal suo stesso cross-check (0,0094 W composto contro 0,015 W misurato: sottostima 1,6×),')
a('con lo scarto localizzato sui DSP. Qui i DSP sono **69** invece di 52.\n')
a('A titolo di confronto, la composizione darebbe **%.4f W** contro i **%.4f W** misurati.'
  % (comp, duty['dyn']))
a('⚠️ Attenzione a leggerci troppo: a un duty dello **%.4f %%** il valore e\' dominato dall\'idle per')
a('costruzione (il circuito calcola per %.4f %% del tempo), quindi qui il confronto **non discrimina** —'
  % (100 * duty_frac, 100 * duty_frac))
a('diversamente da T6b, dove il cross-check girava a duty **3,85 %%** e la differenza si vedeva.')
a('Il valore di questa misura non e\' smentire la composizione: e\' **non doverla usare**.\n')

io.open(OUT, 'w', encoding='utf-8', newline='').write('\n'.join(L) + '\n')
print('GEN-OK %s | %d carichi | idle conv=%s | duty %.3f W | copertura %s'
      % (os.path.basename(OUT), len(WLS), conv, duty['dyn'],
         '%d/%d' % duty['cov'] if duty['cov'] else '?'))
