#!/usr/bin/env python3
"""audit_harness_snn_iidm_report.py — verifica AVVERSARIALE del report T7.

Ricarica le fonti in modo INDIPENDENTE dal generatore e controlla che ogni grandezza che il report
dichiara vi corrisponda davvero. Non e' una rilettura: e' un cancello ripetibile, che fallisce se il
generatore e gli artefatti divergono.

⚠️ Il controllo e' fatto sul .md GENERATO, non sul sorgente del generatore: cosi' intercetta anche gli
errori introdotti nella formattazione, non solo quelli nei dati.

Uso:   python scripts/audit_harness_snn_iidm_report.py [percorso_md]
Esito: exit 0 se tutto torna, 1 con l'elenco dei disallineamenti.
"""
import io, json, os, re, sys
import scipy.io as sio

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RES  = os.path.join(ROOT, 'FaseB2.0', 'Harness_SNN_IIDM', 'results')
BITS = os.path.join(ROOT, 'FaseB2.0', 'Harness_SNN_IIDM', 'bitstream')
MD   = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'report', 'B2_0_HARNESS_SNN_IIDM_REPORT.md')

if not os.path.exists(MD):
    sys.exit('AUDIT-ABORT: manca %s' % MD)
doc = io.open(MD, encoding='utf-8').read()
# nel report i migliaia sono separati da spazio: si normalizza per poterli cercare
flat = doc.replace(' ', ' ')
flat_nospace = re.sub(r'(?<=\d) (?=\d\d\d\b)', '', flat)


def J(n):
    p = os.path.join(RES, n)
    if not os.path.exists(p):
        sys.exit('AUDIT-ABORT: manca la fonte %s' % p)
    return json.load(io.open(p, encoding='utf-8'))


SW, NL, PW, PP, ST, MET = (J(x) for x in ('sweep.json', 'netlist.json', 'power.json',
                                          'power_params.json', 'saif_stats.json', 'metrics.json'))
M = sio.loadmat(os.path.join(RES, 't7_results.mat'), squeeze_me=True, struct_as_record=False)
V = M['V']

bad, checked = [], 0


def must(label, needle, source):
    """La stringa DEVE comparire nel report. `source` documenta da dove viene il valore atteso."""
    global checked
    checked += 1
    n = str(needle)
    if n not in flat and n not in flat_nospace:
        bad.append('%-46s atteso %-22r  (da %s) — NON compare nel report' % (label, n, source))


def must_not(label, needle, why):
    """⚠️ Confini di PAROLA obbligatori: cercare '52 MHz' come sottostringa lo trova dentro
    '15.152 MHz' (la quantizzazione del PS7) e produce un falso positivo. Un controllo con falsi
    positivi non e' solo rumoroso: ne nasconde anche di reali, perche' chi lo legge impara a
    ignorarlo. Errore gia' commesso una volta su questo progetto, con l'audit dei formati."""
    global checked
    checked += 1
    pat = r'(?<![\d.,])' + re.escape(str(needle))
    if re.search(pat, flat) or re.search(pat, flat_nospace):
        bad.append('%-46s NON deve comparire %-14r — %s' % (label, str(needle), why))


# ---- T7a: dall'esito primario -------------------------------------------------
must('T7-EXACT disallineamenti', int(V.nExact), 't7_results.mat V.nExact')
must('T7-EXACT confronti', '%d' % int(V.nTot), 't7_results.mat V.nTot')
must('PARAM-RANGE fuori dominio', int(V.nRange), 't7_results.mat V.nRange')
must('NO-REPEAT passi ripetuti', '%d' % int(V.nRep), 't7_results.mat V.nRep')
must('control-step per scenario', int(M['K']), 't7_results.mat K')
rep_pc = 100.0 * int(V.nRep) / int(V.nTot)
must('percentuale passi ripetuti', '%.1f' % rep_pc, 'calcolata da V.nRep/V.nTot')

# ---- T7a: metriche ------------------------------------------------------------
S = MET['_summary']
must('numero di scenari', S['n_scenari'], 'metrics.json _summary')
must('numero di metriche', S['n_metriche'], 'metrics.json _summary')
must('collisioni RTL', S['coll_rtl'], 'metrics.json _summary')
must('collisioni aggiuntive', S['coll_extra'], 'metrics.json _summary')

# ---- T7b: sweep ---------------------------------------------------------------
must('frequenza deployabile', '%g MHz' % SW['deployable_mhz'], 'sweep.json')
must('WNS al punto deployabile', '%+.3f' % SW['deployable_wns_ns'], 'sweep.json')
must('WHS al punto deployabile', '%+.3f' % SW['deployable_whs_ns'], 'sweep.json')
must('limite del cammino critico', '%.1f MHz' % SW['datapath_limit_mhz'], 'sweep.json')
must('WNS in OOC', '%+.3f' % SW['ooc_wns_ns'], 'sweep.json')
for k, lab in (('lut', 'LUT'), ('ff', 'FF'), ('dsp', 'DSP')):
    must('utilizzo %s' % lab, SW['util'][k], 'sweep.json util')
must('percentuale LUT', '%.1f %%' % SW['util']['lut_pct'], 'sweep.json util')
must('percentuale DSP', '%.1f %%' % SW['util']['dsp_pct'], 'sweep.json util')
must('LUT di align', SW['hier']['u_align']['lut'], 'sweep.json hier')
for q in SW['quantized']:
    must('quantizzazione PS7 %d MHz' % q['req'], '%.3f MHz' % q['mhz'], 'sweep.json quantized')

# ---- T7b: netlist -------------------------------------------------------------
must('netlist disallineamenti', NL['nmismatch'], 'netlist.json')
must('netlist confronti', '%d' % NL['n'], 'netlist.json')
must('netlist scenari', NL['nscen'], 'netlist.json')
must('penalizzazione gate-level', '%.0f' % NL['gate_level_ratio'], 'netlist.json')
must('ore per i 99 scenari', '%.0f ore' % NL['full99_hours'], 'netlist.json')

# ---- T7b: energia -------------------------------------------------------------
must('finestra attiva', '%d cicli' % PP['act_clk'], 'power_params.json')
must('duty', '%.4f %%' % (100.0 * PP['act_clk'] / PP['tot_clk']), 'power_params.json')
must('potenza idle', '%.3f W' % PW['idle_dyn_w'], 'power.json')
must('potenza attiva', '%.3f W' % PW['act_max_dyn_w'], 'power.json')
must('potenza al duty reale', '%.3f W' % PW['duty_dyn_w'], 'power.json')
must('potenza statica', '%.3f W' % PW['static_w'], 'power.json')
must('energia dinamica', '%.2f mJ' % PW['energy_dyn_per_step_mj'], 'power.json')
must('energia statica', '%.1f mJ' % PW['energy_static_per_step_mj'], 'power.json')
must('copertura SAIF (numeratore)', '%d' % PW['saif_cov'][0], 'power.json')
must('copertura SAIF (denominatore)', '%d' % PW['saif_cov'][1], 'power.json')
must('confidenza', PW['confidence'], 'power.json')
must('dispersione sui toggle', '%.1f %%' % PW['tc_disp_pct'], 'power.json')
must('guadagno del gating', '%.0f' % PW['gating_toggle_gain'], 'power.json')
must('scarto di coerenza del duty', '%.1f %%' % PW['duty_coherence_err_pct'], 'power.json')
must('numero di carichi', len(PP['workloads']), 'power_params.json')

# ---- IL CONTROLLO CHE COPRE IL CASO "NUMERO CORROTTO" -------------------------
# Un valore sbagliato nel report puo' venire solo da due posti: dal GENERATORE (e allora e' uno dei
# controlli qui sopra a trovarlo, perche' confrontano col sorgente dei dati) oppure da una modifica
# fatta al .md DOPO la generazione. Il secondo caso non si intercetta con le espressioni regolari --
# ci ho provato, e il tentativo pretendeva un valore unico da parole ("confronti", "scenari") che nel
# report descrivono grandezze diverse. Si intercetta RIGENERANDO: il documento e' deterministico.
import hashlib, subprocess
def _md5(p):
    return hashlib.md5(io.open(p, 'rb').read()).hexdigest()
if os.environ.get('AUDIT_SKIP_REGEN') != '1' and os.path.abspath(MD) == os.path.abspath(
        os.path.join(ROOT, 'report', 'B2_0_HARNESS_SNN_IIDM_REPORT.md')):
    checked += 1
    before = _md5(MD)
    r = subprocess.run([sys.executable, os.path.join(HERE, 'build_harness_snn_iidm_report.py')],
                       capture_output=True, text=True)
    if r.returncode != 0:
        bad.append('%-46s la rigenerazione FALLISCE: %s' % ('determinismo', r.stderr.strip()[:120]))
    elif _md5(MD) != before:
        bad.append('%-46s il .md NON coincide con quello rigenerato dalle fonti: '
                   'era stato modificato a valle, oppure le fonti sono cambiate' % 'determinismo')

# ---- coerenza dei toggle col SAIF (fonte ancora diversa) ----------------------
tpc_i = ST['idle_g0_w200']['tc'] / 200.0
tpc_g = ST['idle_g1_w200']['tc'] / 200.0
if abs(tpc_i - PW['tc_idle_per_clk']) > 1e-9 or abs(tpc_g - PW['tc_idle_gated_per_clk']) > 1e-9:
    bad.append('%-46s power.json e saif_stats.json NON concordano sui toggle/clock' % 'coerenza toggle')
checked += 1

# ---- bitstream ----------------------------------------------------------------
bitp = os.path.join(BITS, 'donatello_snn_iidm.bit')
if os.path.exists(bitp):
    must('dimensione del bitstream', '%.2f MB' % (os.path.getsize(bitp) / 1e6), 'dimensione del file .bit')

# ---- CONTRO-CONTROLLI: numeri che NON devono comparire -------------------------
# Il report NON deve citare i numeri del blocco SNN da solo (primo report): sono un altro perimetro,
# e confonderli e' l'errore che questo progetto ha gia' pagato una volta.
must_not('frequenza del primo report', '52 MHz', 'e\' la deployabile del Tier da solo, altro perimetro')
must_not('limite del primo report', '58,5 MHz', 'e\' il limite del Tier da solo')
must_not('Fmax OOC del solo DUT', '41,5 MHz', 'numero OOC di un altro perimetro: §6.2 spiega perche\' non si usa')

# ---- struttura ----------------------------------------------------------------
for want in ('## 1. Sintesi', '## 12. Conclusioni', '## Riferimenti'):
    checked += 1
    if want not in doc:
        bad.append('%-46s sezione mancante: %s' % ('struttura', want))
nfig = doc.count('![')
checked += 1
if nfig < 8:
    bad.append('%-46s solo %d figure referenziate (attese >= 8)' % ('struttura', nfig))
checked += 1
if re.search(r'%\.[0-9]+[fd]|%\s?[ds]\b', doc):
    bad.append('%-46s specificatori di formato non sostituiti nel testo' % 'formattazione')

# ---- esito --------------------------------------------------------------------
print('AUDIT — %d controlli su %s' % (checked, os.path.basename(MD)))
if bad:
    print('\nDISALLINEAMENTI (%d):' % len(bad))
    for b in bad:
        print('  ' + b)
    sys.exit(1)
print('tutti i controlli passano: ogni grandezza del report corrisponde alla sua fonte.')
