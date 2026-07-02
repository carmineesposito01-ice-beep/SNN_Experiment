"""scripts/verify_fpga_eval.py -- verifica manifest post-run dell'FPGA-evaluate.

Controlla che ogni sezione abbia le sue figure (>= n attese da FF.SECTIONS) + i CSV
deliverable, e che non ci siano ERROR_<sez>.txt. Exit 0 = OK, 1 = problemi.
Uso: python scripts/verify_fpga_eval.py
"""
import os
import sys
import glob

sys.path.insert(0, os.getcwd())
import scripts.fpga_figures as FF

RESULTS = os.path.join('results', 'evaluate', 'FPGA')
EXPECTED_CSV = {
    '00_Readiness': ['scorecard.csv'], '01_Weights_po2': ['weight_stats.csv'],
    '02_FixedPoint': ['state_ranges.csv'], '04_Energy': ['energy_power.csv'],
    '05_Timing_WCET': ['latency_dse.csv'], '07_SEU_ISO26262': ['seu_sensitivity.csv'],
    '08_IO_HIL': ['io_hil.csv'],
}


def main():
    if not os.path.isdir(RESULTS):
        print('[verify] cartella risultati assente:', RESULTS); return 1
    problems = []
    for folder, figs in FF.SECTIONS.items():
        d = os.path.join(RESULTS, folder)
        pngs = glob.glob(os.path.join(d, '*.png'))
        if len(pngs) < len(figs):
            problems.append('%s: %d/%d figure' % (folder, len(pngs), len(figs)))
    for folder, csvs in EXPECTED_CSV.items():
        for c in csvs:
            if not os.path.isfile(os.path.join(RESULTS, folder, c)):
                problems.append('manca CSV %s/%s' % (folder, c))
    for e in glob.glob(os.path.join(RESULTS, 'ERROR_*.txt')):
        problems.append('ERROR file: ' + os.path.basename(e))
    if problems:
        print('[verify] PROBLEMI (%d):' % len(problems))
        for p in problems:
            print('  -', p)
        return 1
    n_fig = sum(len(v) for v in FF.SECTIONS.values())
    print('[verify] OK — %d figure attese su %d sezioni + CSV deliverable presenti, nessun ERROR'
          % (n_fig, len(FF.SECTIONS)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
