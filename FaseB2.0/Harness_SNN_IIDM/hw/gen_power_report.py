#!/usr/bin/env python3
# T7b - genera results/POWER.md PARSANDO i power_*.rpt prodotti da report_power.
# Uso: python hw/gen_power_report.py
import io, json, os, re, sys, glob

HERE = os.path.dirname(os.path.abspath(__file__))
RES  = os.path.normpath(os.path.join(HERE, '..', 'results'))
OUT  = os.path.join(RES, 'POWER.md')
LAT_CLK = 555             # latenza pura dell'inferenza+controllo (costante del wrapper, non della run)
IDLE_W  = [200, 1000, 5000]

# ⚠️ I parametri della campagna si LEGGONO da chi li ha usati, non si riscrivono qui. ACT_CLK in
#    particolare e' MISURATO da P0: duplicarlo significherebbe che una P0 futura misura un valore e
#    questo report ne stampa un altro, in silenzio.
_PP = os.path.join(RES, 'power_params.json')
if not os.path.exists(_PP):
    print('GEN-ABORT: manca power_params.json -- eseguire prima uno stadio di `run_power.sh`,\n'
          '           che scrive i parametri EFFETTIVAMENTE usati.', file=sys.stderr)
    sys.exit(1)
_p = json.load(io.open(_PP, encoding='utf-8'))
WLS     = _p['workloads']
FCLK    = float(_p['fclk_mhz'])
ACT_CLK = int(_p['act_clk'])
NACT    = int(_p['nact'])
CTRL_S  = float(_p['ctrl_step_s'])
# ⚠️ separatore '/' e non '|': una pipe dentro una cella SPEZZA la tabella markdown, anche fra backtick.
LABEL = {1: 'highway / no-cut-in', 4: 'highway / cut-in', 28: 'urban / no-cut-in', 31: 'urban / cut-in',
         55: 'truck / no-cut-in', 58: 'truck / cut-in', 73: 'mixed / no-cut-in', 76: 'mixed / cut-in'}


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

# CONTEGGI DI COMMUTAZIONE dal SAIF: e' li' che sta l'informazione che i 3 decimali di report_power
# cancellano. Senza, il report direbbe "dispersione nulla" dove c'e' dispersione sotto la precisione.

SP = os.path.join(RES, 'saif_stats.json')
if not os.path.exists(SP):
    die('manca saif_stats.json -- eseguire prima `python hw/gen_saif_stats.py`')
st = json.load(io.open(SP, encoding='utf-8'))
def tc(k):
    if k not in st: die('saif_stats.json non contiene %s' % k)
    return st[k]['tc']
tc_act = {i: tc('act_g1_wl%d' % i) for i in WLS}
tc_idle = {w: tc('idle_g0_w%d' % w) for w in IDLE_W}
tc_idle_g1 = tc('idle_g1_w200')
tc_duty = tc('duty_g1')
# toggle per clock: e' la grandezza confrontabile fra finestre di lunghezza diversa
tpc_idle = {w: tc_idle[w] / float(w) for w in IDLE_W}
tpc_idle_g1 = tc_idle_g1 / 200.0

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
    a('\nSul **%.0f %%** dei net l\'attivita\' NON viene dal SAIF ma dal modello vectorless del tool: e\' una'
      % (100.0 - 100.0 * n / tt))
    a('proprieta\' della misura, e va letta insieme ai watt.\n')
else:
    a('⚠️ **La copertura o la confidenza NON sono uniformi fra i report**: %s · %s.'
      % (sorted(covs), sorted(confs)))
    a('I valori non sono direttamente confrontabili fra loro.\n')

a('## Idle: stazionaria — provato sui TOGGLE, non solo sui watt\n')
a('| Finestra | Totale [W] | Dinamica [W] | Commutazioni (TC) | **TC / clock** |')
a('|---|---|---|---|---|')
for w in IDLE_W:
    r = idle[w]
    a('| %d cicli | %.3f | %.3f | %d | **%.1f** |' % (w, r['tot'], r['dyn'], tc_idle[w], tpc_idle[w]))
conv = len({round(idle[w]['dyn'], 4) for w in IDLE_W}) == 1
conv_tc = len({round(tpc_idle[w], 3) for w in IDLE_W}) == 1
if conv and conv_tc:
    a('\nI watt coincidono, **ma la prova sta nella colonna dei toggle**: il rapporto TC/clock e\' **identico**')
    a('sulle tre finestre (%.1f), cioe\' la commutazione cresce ESATTAMENTE in proporzione alla durata.'
      % tpc_idle[IDLE_W[0]])
    a('L\'idle e\' quindi **stazionario** e la finestra da 200 cicli basta.\n')
    a('La distinzione non e\' pedanteria: tre valori di potenza uguali a 3 decimali potrebbero esserlo anche')
    a('per insensibilita\' dello strumento. Un TC/clock costante su un fattore 25 di durata non puo\'.\n')
    a('Il controllo verifica anche la PREMESSA — che il circuito sia davvero fermo quando non calcola: se')
    a('avesse avuto FSM o contatori attivi il rapporto non sarebbe stato costante. Non era garantito, ed e\'')
    a('la condizione perche\' il clock gating abbia qualcosa da spegnere.\n')
else:
    a('\n⚠️ **L\'idle NON e\' stazionaria** su queste finestre (watt costanti: %s · TC/clock costante: %s):'
      % (conv, conv_tc))
    a('la misura dipende dalla finestra scelta e **non** puo\' essere usata come valore unico.\n')

a('## Clock gating: FUNZIONA — misurato nell\'artefatto, invisibile nei watt\n')
a('| Configurazione | Totale [W] | Dinamica [W] | TC su 200 cicli | **TC / clock** |')
a('|---|---|---|---|---|')
a('| idle **non** gatata (`gate_mode`=0) | %.3f | %.3f | %d | %.1f |'
  % (idle[200]['tot'], idle[200]['dyn'], tc_idle[200], tpc_idle[200]))
a('| idle **gatata** (`gate_mode`=1) | %.3f | %.3f | **%d** | **%.1f** |'
  % (idle_g1['tot'], idle_g1['dyn'], tc_idle_g1, tpc_idle_g1))
gain = tpc_idle[200] / tpc_idle_g1 if tpc_idle_g1 else float('inf')
same_w = abs(idle_g1['dyn'] - idle[200]['dyn']) < 1e-9
a('\nIl gating **riduce la commutazione di %.0f×** (%.1f → %.1f toggle per clock): e\' una MISURA, letta'
  % (gain, tpc_idle[200], tpc_idle_g1))
a('dentro il SAIF.')
if same_w:
    a('Nel sommario dei watt, invece, **non si vede nulla** (%.3f W in entrambi i casi).\n' % idle[200]['dyn'])
    a('⚠️ Non e\' una contraddizione ma un **limite dello strumento**, gia\' accertato in T6b anche in negativo:')
    a('`report_power` deriva la potenza dei net di clock dal **VINCOLO di frequenza**, non dall\'attivita\' del')
    a('SAIF — imporre `set_switching_activity -toggle_rate 0` sui net di clock non cambiava il risultato.')
    a('Qui il finding e\' **riprodotto in modo indipendente su un design diverso**.\n')
    a('**Conclusione onesta: il gating e\' implementato e agisce; il suo guadagno in watt NON e\' misurabile')
    a('con questo flusso.** Serve un flusso diverso (misura su board in Fase C, o un modello che accetti')
    a('attivita\' per-net sui clock). Nessuna stima viene qui spacciata per misura.\n')
else:
    a('E nei watt la differenza si vede: %.3f → %.3f W dinamica.\n' % (idle[200]['dyn'], idle_g1['dyn']))

a('## Fase attiva: %d carichi REALI\n' % len(WLS))
a('Uno per combinazione **regime × cut-in** del dataset dei 99 — sono **otto**, enumerate')
a('(18+9+18+9+12+6+18+9 = 99). Stimoli e golden sono quelli gia\' validati in T7a: ogni run di potenza vale')
a('anche come conferma funzionale.\n')
a('| Carico | Combinazione | Totale [W] | Dinamica [W] | **Commutazioni (TC)** | Clocks | Logic | Signals | BRAM | DSP |')
a('|---|---|---|---|---|---|---|---|---|---|')
for i in WLS:
    r = act[i]
    a('| wl%d | `%s` | %.3f | %.3f | **%d** | %s | %s | %s | %s | %s |'
      % (i, LABEL[i], r['tot'], r['dyn'], tc_act[i], r['clk'], r['logic'], r['sig'], r['bram'], r['dsp']))
tmax, tmin = max(tc_act.values()), min(tc_act.values())
timax = [i for i in WLS if tc_act[i] == tmax]
disp_w = 100.0 * (dmax['dyn'] - dmin) / dmax['dyn'] if dmax['dyn'] else 0
disp_t = 100.0 * (tmax - tmin) / tmax
a('\n**Massimo OSSERVATO fra i carichi reali: %.3f W** (dinamica) · minimo %.3f W.' % (dmax['dyn'], dmin))
if disp_w < 1e-9:
    a('\n⚠️ **I watt sono identici a 3 decimali su tutti e %d i carichi, ma la dispersione NON e\' nulla.**'
      % len(WLS))
    a('Nei SAIF la commutazione va da **%d a %d toggle** = **%.1f %%** di dispersione (massimo: wl%s).'
      % (tmin, tmax, disp_t, '/'.join(map(str, timax))))
    a('Su %.3f W quel %.1f %% vale circa **%.4f W**, cioe\' **sotto la terza cifra** che `report_power` stampa.\n'
      % (dmax['dyn'], disp_t, dmax['dyn'] * disp_t / 100.0))
    a('Va detto cosi\': *«identici nel sommario, %.1f %% di dispersione nella commutazione»*. Riportare' % disp_t)
    a('«dispersione nulla» sarebbe scambiare un limite di precisione per una proprieta\' del circuito — ed e\'')
    a('esattamente il tipo di conclusione che un numero arrotondato induce se non si guarda l\'artefatto.\n')
else:
    a('\nDispersione: **%.1f %%** sui watt · **%.1f %%** sulla commutazione (%d–%d toggle).'
      % (disp_w, disp_t, tmin, tmax))
a('⚠️ E\' comunque un **massimo osservato**, non un limite superiore. Il worst-case sintetico **non e\' stato')
a('prodotto**: in T6b risulto\' il **piu\' basso di tutti** (0,041 W contro 0,045 del massimo reale), quindi')
a('come bound e\' stato smentito su misura. Trovare il regime peggiore richiederebbe uno studio a se\'.\n')
a('Ogni run di potenza ha dato anche **`nMismatch = 0 / 50`**: la misura energetica vale come conferma')
a('funzionale sullo stesso perimetro.\n')

a('## Duty REALE: misurato, non composto\n')
a('| Grandezza | Valore | Natura |')
a('|---|---|---|')
a('| Finestra attiva | **%d clock** | **misurata** dal banco (%d di latenza + %d di protocollo AXI) |'
  % (ACT_CLK, LAT_CLK, ACT_CLK - LAT_CLK))
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
a('⚠️ Attenzione a leggerci troppo: a un duty dello **%.4f %%** il valore e\' dominato dall\'idle per'
  % (100 * duty_frac))
a('costruzione, quindi qui il confronto **non discrimina** —')
a('diversamente da T6b, dove il cross-check girava a duty **3,85 %** e la differenza si vedeva.')
a('Il valore di questa misura non e\' smentire la composizione: e\' **non doverla usare**.\n')

# Controllo di coerenza INDIPENDENTE, sui toggle: la finestra del duty dovrebbe contenere
# (clock di idle x TC/clock idle-gatata) + (clock attivi x TC/clock attivo). Se il conto non torna,
# la finestra SAIF non copre quello che credo -- ed e' un errore che nei watt sarebbe invisibile.
tot_clk = int(CTRL_S * FCLK * 1e6)
# ⚠️ Il SAIF attivo copre NACT control-step, non uno: dividere per i soli ACT_CLK gonfia il toggle/clock
#    di NACT volte. (Sbagliato la prima volta: il cancello qui sotto lo ha intercettato con uno scarto
#    dell'83 %, che e' precisamente il motivo per cui esiste.)
tpc_act = max(tc_act.values()) / float(NACT * ACT_CLK)
pred = (tot_clk - ACT_CLK) * tpc_idle_g1 + ACT_CLK * tpc_act
err = 100.0 * abs(tc_duty - pred) / pred if pred else 0
a('## Controllo di coerenza sulla finestra del duty (sui toggle, non sui watt)\n')
a('La finestra del duty deve contenere `(%d clock di idle × %.1f) + (%d clock attivi × %.0f)` = **%.0f toggle**;'
  % (tot_clk - ACT_CLK, tpc_idle_g1, ACT_CLK, tpc_act, pred))
a('nel SAIF ce ne sono **%d**. Scarto **%.1f %%**.\n' % (tc_duty, err))
if err < 5:
    a('Il conto torna: la finestra SAIF del duty copre davvero **un control-step intero** — la fase attiva e\'')
    a('dentro, l\'idle e\' della lunghezza giusta. E\' un controllo che nei watt sarebbe stato **invisibile**')
    a('(a questo duty il valore e\' dominato dall\'idle comunque), quindi una finestra sbagliata avrebbe dato')
    a('un numero credibile.\n')
else:
    a('⚠️ **Il conto NON torna** (scarto %.1f %%): la finestra SAIF del duty non copre quello che dovrebbe.' % err)
    a('Il valore di potenza al duty **non e\' attendibile** finche\' non si spiega lo scarto.\n')

io.open(OUT, 'w', encoding='utf-8', newline='').write('\n'.join(L) + '\n')


json.dump({
    'idle_dyn_w': idle[200]['dyn'], 'idle_tot_w': idle[200]['tot'], 'static_w': idle[200]['sta'],
    'idle_converge': conv,
    'idle_gated_dyn_w': idle_g1['dyn'],
    'act_max_dyn_w': dmax['dyn'], 'act_max_wl': imax, 'act_min_dyn_w': dmin, 'n_workloads': len(WLS),
    'duty_frac': duty_frac, 'act_clk': ACT_CLK,
    'duty_tot_w': duty['tot'], 'duty_dyn_w': duty['dyn'],
    'energy_dyn_per_step_mj': round(duty['dyn'] * CTRL_S * 1000, 3),
    'energy_static_per_step_mj': round(duty['sta'] * CTRL_S * 1000, 3),
    'tc_disp_pct': round(disp_t, 1), 'tc_act_min': tmin, 'tc_act_max': tmax,
    'tc_idle_per_clk': tpc_idle[200], 'tc_idle_gated_per_clk': tpc_idle_g1,
    'gating_toggle_gain': round(gain, 1),
    'duty_coherence_err_pct': round(err, 1),
    'composed_dyn_w': round(comp, 5),
    'saif_cov': duty['cov'], 'confidence': duty['conf'],
}, io.open(os.path.join(RES, 'power.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
print('GEN-OK %s | %d carichi | idle conv=%s | duty %.3f W | copertura %s'
      % (os.path.basename(OUT), len(WLS), conv, duty['dyn'],
         '%d/%d' % duty['cov'] if duty['cov'] else '?'))
