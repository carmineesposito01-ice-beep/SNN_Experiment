#!/usr/bin/env python3
# T7b - genera results/RESULTS_HW.md, la SINTESI della caratterizzazione hardware.
#
# Non ri-parsa le fonti grezze e non legge il markdown generato: compone i sommari JSON che i tre
# generatori di dettaglio emettono accanto ai propri .md. UN NUMERO NASCE IN UN POSTO SOLO.
#   sweep.json   <- gen_sweep_report.py    (timing_*.rpt, util_*.rpt)
#   netlist.json <- gen_netlist_report.py  (netlist_func.log)
#   power.json   <- gen_power_report.py    (power_*.rpt)
#
# Ogni riga porta la NATURA del numero: misurato | derivato | stima | prodotto. Non e' decorazione:
# l'audit di T6b aveva imposto di distinguere un Fmax letto stringendo il vincolo (derivato) da uno
# osservato chiudere (misurato), e un guadagno atteso (stima) da uno misurato.
import io, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
RES  = os.path.normpath(os.path.join(HERE, '..', 'results'))
OUT  = os.path.join(RES, 'RESULTS_HW.md')
LAT_CLK, CTRL_S = 555, 0.1


def load(name, what):
    p = os.path.join(RES, name)
    if not os.path.exists(p):
        print('GEN-ABORT: manca %s -- %s non e\' stato eseguito. La sintesi NON viene scritta parziale:\n'
              '           un RESULTS_HW.md a cui manca una sezione somiglia troppo a uno completo.'
              % (name, what), file=sys.stderr)
        sys.exit(1)
    return json.load(io.open(p, encoding='utf-8'))


sw = load('sweep.json',   'lo sweep FCLK')
nl = load('netlist.json', 'la simulazione di netlist')
pw = load('power.json',   'lo studio energetico')
bit = os.path.join(RES, '..', 'bitstream', 'donatello_snn_iidm.bit')
has_bit = os.path.exists(bit)

lat_us = LAT_CLK / (sw['deployable_mhz'] * 1e6) * 1e6
margin = CTRL_S / (lat_us * 1e-6)
cov_n, cov_t = pw['saif_cov']

L = []; a = L.append
a('# T7b · Caratterizzazione hardware di `Donatello_SNN_IIDM` — sintesi\n')
a('> **Generato**, non scritto a mano: `python hw/gen_results_hw.py`, che compone i sommari JSON emessi dai')
a('> tre generatori di dettaglio. Ogni numero nasce in UN posto solo, dal proprio report grezzo.')
a('> Dettaglio: [`SWEEP_FCLK.md`](SWEEP_FCLK.md) · [`NETLIST.md`](NETLIST.md) · [`POWER.md`](POWER.md) ·')
a('> [`COSIM_AXI.md`](COSIM_AXI.md) · [`RESULTS.md`](RESULTS.md) (T7a, livello RTL).\n')
a('Dispositivo **xc7z020clg400-1** (PYNQ-Z1), Vivado 2026.1, `-jobs` fisso per il determinismo.\n')

a('## I numeri, con la loro natura\n')
a('| Grandezza | Valore | Natura |')
a('|---|---|---|')
a('| Params letti dal **PS via AXI** == blocco | **0 / 58 522** su 99 scenari, gating ON e OFF | misurato |')
a('| Netlist **post-place&route** == blocco | **%d / %d** (%d scenari dichiarati, funcsim) | misurato |'
  % (nl['nmismatch'], nl['n'], nl['nscen']))
a('| **Frequenza deployabile** | **%g MHz** — WNS %+.3f ns · WHS %+.3f ns | **misurato** |'
  % (sw['deployable_mhz'], sw['deployable_wns_ns'], sw['deployable_whs_ns']))
a('| **Limite del cammino critico** | **%.1f MHz** — al punto piu\' stretto (%g MHz), che NON chiude | **derivato** |'
  % (sw['datapath_limit_mhz'], sw['limit_from_mhz']))
u = sw['util']
a('| Risorse post-route @%g MHz | %d LUT (%.1f %%) · %d FF (%.1f %%) · %d DSP (%.1f %%) · %g BRAM (%.1f %%) | misurato |'
  % (sw['deployable_mhz'], u['lut'], u['lut_pct'], u['ff'], u['ff_pct'], u['dsp'], u['dsp_pct'],
     u['bram'], u['bram_pct']))
a('| Finestra attiva (inferenza + protocollo AXI) | **%d clock** (%d di latenza + %d di AXI) | misurato |'
  % (pw['act_clk'], LAT_CLK, pw['act_clk'] - LAT_CLK))
a('| Latenza / margine sul control-step %g s | %.1f µs / **≈%.0f×** (duty **%.4f %%**) | derivato |'
  % (CTRL_S, lat_us, margin, 100 * pw['duty_frac']))
a('| Potenza **idle** (dinamica) | **%.3f W** — finestra convergente su 200/1000/5000 | misurato |'
  % pw['idle_dyn_w'])
if pw['act_max_dyn_w'] == pw['act_min_dyn_w']:
    a('| Potenza **attiva** (mentre calcola), su %d carichi reali | **%.3f W** dinamica — identica a 3 decimali '
      'su tutti; la dispersione vera e\' **%.1f %%** sui *toggle* | misurato |'
      % (pw['n_workloads'], pw['act_max_dyn_w'], pw.get('tc_disp_pct', 0.0)))
else:
    a('| Potenza **attiva**, massimo osservato su %d carichi reali | **%.3f W** (wl%s) · minimo %.3f W | misurato |'
      % (pw['n_workloads'], pw['act_max_dyn_w'], '/'.join(map(str, pw['act_max_wl'])), pw['act_min_dyn_w']))
a('| **Potenza al duty REALE** (control-step intero) | **%.3f W** dinamica (+ %.3f W di statica) | **misurato, NON composto** |'
  % (pw['duty_dyn_w'], pw['static_w']))
# ⚠️ L'energia del PROGETTO si calcola sulla DINAMICA. Usare la potenza totale ci mette dentro la statica
#    del device, che e' il pavimento del chip: a questo duty domina il conto e "l'energia per control-step"
#    diventerebbe una misura del silicio acceso, non del lavoro svolto.
a('| **Energia dinamica** per control-step | **%.2f mJ** | derivato (`P_dyn × %g s`) |'
  % (pw['duty_dyn_w'] * CTRL_S * 1000, CTRL_S))
a('| Statica del device (pavimento del chip, **separata**) | %.3f W → %.1f mJ per control-step | misurato |'
  % (pw['static_w'], pw['static_w'] * CTRL_S * 1000))
a('| **Copertura SAIF** / confidenza | **%d / %d net = %.1f %%** · `%s` | misurato |'
  % (cov_n, cov_t, 100.0 * cov_n / cov_t, pw['confidence']))
if has_bit:
    a('| **Bitstream PYNQ-Z1** @%g MHz (`.bit`/`.hwh`/`.xsa`) | %.2f MB | prodotto |'
      % (sw['deployable_mhz'], os.path.getsize(bit) / 1e6))
else:
    a('| Bitstream PYNQ-Z1 | **non ancora prodotto** | — |')

a('\n## Tre cose che questi numeri NON dicono\n')
a('| Domanda | Stato | Perche\' |')
a('|---|---|---|')
a('| La netlist e\' equivalente su **tutti** i 99 scenari? | **non provato** (N=%d dichiarato) | costo: ~%.0f h '
  '(penalizzazione gate-level **%.0f×**, misurata qui) |' % (nl['nscen'], nl['full99_hours'], nl['gate_level_ratio']))
a('| Il **worst case** energetico? | **non determinato** | si riporta il **massimo osservato** fra carichi reali. '
  'Il worst sintetico fu **smentito su misura** in T6b: risulto\' il piu\' basso di tutti |')
a('| Il guadagno in watt del **clock gating**? | **non misurabile con questo flusso** | `report_power` deriva la '
  'potenza dei net di clock dal VINCOLO di frequenza, non dal SAIF (accertato in T6b anche in negativo) |')

a('\n## Due premesse su cui NON costruire\n')
if sw.get('quantized'):
    a('- **Il PS7 quantizza la frequenza richiesta** (%s). Il periodo **non** e\' `1000/f_richiesta`: va letto'
      % ', '.join('%d→%.3f MHz' % (q['req'], q['mhz']) for q in sw['quantized']))
    a('  dalla tabella dei clock del `report_timing`. Una tabella costruita sull\'assunzione aveva **4 righe')
    a('  sbagliate su 8**.')
if sw.get('ooc_wns_ns') is not None:
    a('- **OOC e sistema sono perimetri diversi e i numeri non si scambiano.** Lo stesso circuito a %g MHz'
      % sw['deployable_mhz'])
    a('  **chiude nel sistema** (WNS %+.3f) e **non chiude in OOC** (WNS %+.3f). Un numero OOC non e\' una'
      % (sw['deployable_wns_ns'], sw['ooc_wns_ns']))
    a('  capacita\' del progetto ed e\' confrontabile solo con altri numeri OOC dello stesso perimetro.')

a('\n## Riesecuzione\n')
a('```bash')
a('bash hw/run_harness_snniidm_hw.sh summary     # i numeri in pochi secondi, dagli artefatti')
a('bash hw/run_harness_snniidm_hw.sh <stadio>    # check | cosim | sweep | netlist | power | bitstream | all')
a('```')
a('Lo stadio `check` confronta la firma md5 dei sorgenti con quella registrata in `results/src.sig`: una')
a('differenza **blocca** gli stadi di calcolo, perche\' i risultati qui si riferirebbero ad altri sorgenti.')

io.open(OUT, 'w', encoding='utf-8', newline='').write('\n'.join(L) + '\n')
print('GEN-OK %s | deployabile %g MHz | netlist %d/%d | duty %.3f W | bitstream %s'
      % (os.path.basename(OUT), sw['deployable_mhz'], nl['nmismatch'], nl['n'], pw['duty_tot_w'],
         'si' if has_bit else 'no'))
