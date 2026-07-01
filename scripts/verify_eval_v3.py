"""scripts/verify_eval_v3.py — verifica POST-RUN dell'evaluate v3 (esaustivo).

Da lanciare DOPO il run Azure di Eval_v3_TURTLE_POWER.ipynb:
    python scripts/verify_eval_v3.py
Controlla che (a) ogni CSV/PNG atteso esista, (b) l'oracolo (Master Splinter) sia presente dove previsto,
(c) i bug siano risolti (AoI popolata, quant fixed+po2, string a 3 nozioni), (d) nessun ERROR_<sez>.txt.
Exit 0 = tutto ok; exit 1 = manca qualcosa (stampa il dettaglio). Nessun checkpoint/HW richiesto.
"""
import os
import sys

RESULTS = os.path.join('results', 'evaluate', 'v3_TURTLE_POWER!!!')
ORACLE = 'Master Splinter'

# file ATTESI per cartella (csv + png). I raster sono controllati a parte (>=1).
EXPECTED = {
    '00_Scorecard': ['master_scorecard.csv', 'radar.png'],
    '01_Accuracy': ['accuracy.csv', 'accuracy.png'],
    '02_Safety_ClosedLoop': ['safety.csv', 'safety_scorecard.png', 'brake_margin.png',
                             'per_scenario_min_gap.png', 'ssm_distribution.png', 'delta_vs_oracle.png',
                             'comfort_iso.png'],
    '03_StringStability': ['string_stability.csv', 'string_stability.png', 'amp_profile.png', 'string_latency.png'],
    '04_Identifiability': ['fim.csv', 'fim.png', 'causal_sensitivity.csv', 'causal.png',
                           'nrmse_stratified.csv', 'nrmse_stratified.png',
                           'naturalisticity_calibration.csv', 'naturalisticity_calibration.png'],
    '05_Quantization': ['quantization.csv', 'quantization.png', 'quant_perparam.csv', 'quant_perparam.png',
                        'quant_weight_ablation.csv', 'quant_weight_ablation.png'],
    '06_V2X_Robustness': ['v2x.csv', 'v2x.png', 'v2x_holdmode.png', 'v2x_aoi.png', 'v2x_burst.png'],
    '07_VehicleDynamics': ['plant.csv', 'plant.png'],
    '08_Energy_Spiking': ['energy.csv', 'energy.png'],
    '09_Trajectories': ['traj_hard_brake.png', 'traj_cut_in.png', 'traj_panic_stop.png',
                        'traj_aggressive_cut_in.png', 'traj_stop_and_go.png'],
    '10_Reachability': ['reachability.csv', 'reachability.png'],
    '11_Breakdown': ['breakdown.csv', 'breakdown.png'],
    '12_Mesoscopic': ['meso_summary.csv', 'meso_gain.png', 'meso_spacetime.png', 'meso_scorecard.png'],
    '13_Macroscopic': ['macro_summary.csv', 'macro_fundamental_diagram.png', 'macro_scorecard.png', 'macro_stopandgo.png'],
    # 14_Showcase: file per-champion (showcase_<alias>.png) -> controllato a parte (>=1)
}

problems = []


def _p(*a):
    return os.path.join(RESULTS, *a)


def _read_csv(rel):
    import pandas as pd
    return pd.read_csv(_p(rel))


def check_files():
    for folder, files in EXPECTED.items():
        for f in files:
            if not os.path.isfile(_p(folder, f)):
                problems.append('MANCA file: %s/%s' % (folder, f))
    # raster: almeno 1 png in 08_Energy_Spiking/raster
    rdir = _p('08_Energy_Spiking', 'raster')
    if not (os.path.isdir(rdir) and any(x.endswith('.png') for x in os.listdir(rdir))):
        problems.append('MANCA almeno un raster in 08_Energy_Spiking/raster/')
    # showcase: almeno 1 showcase_<champion>.png in 14_Showcase
    sdir = _p('14_Showcase')
    if not (os.path.isdir(sdir) and any(x.startswith('showcase_') and x.endswith('.png') for x in os.listdir(sdir))):
        problems.append('MANCA almeno una vetrina showcase_<champion>.png in 14_Showcase/')


def check_errors():
    if os.path.isdir(RESULTS):
        errs = [x for x in os.listdir(RESULTS) if x.startswith('ERROR_') and x.endswith('.txt')]
        for e in errs:
            problems.append('SEZIONE FALLITA: %s (una cella ha lanciato un errore)' % e)


def check_oracle_present():
    # oracolo atteso nelle sezioni closed-loop / scorecard / string / plant
    for folder, fname, col in [('02_Safety_ClosedLoop', 'safety.csv', 'champion'),
                               ('07_VehicleDynamics', 'plant.csv', 'champion'),
                               ('03_StringStability', 'string_stability.csv', 'champion'),
                               ('00_Scorecard', 'master_scorecard.csv', 'champion')]:
        if os.path.isfile(_p(folder, fname)):
            try:
                df = _read_csv(os.path.join(folder, fname))
                if ORACLE not in set(df[col].astype(str)):
                    problems.append('ORACOLO assente in %s/%s' % (folder, fname))
            except Exception as e:
                problems.append('lettura fallita %s/%s: %s' % (folder, fname, e))


def check_bugfixes():
    # AoI popolata + 6 assi + oracolo sotto canale
    if os.path.isfile(_p('06_V2X_Robustness', 'v2x.csv')):
        df = _read_csv(os.path.join('06_V2X_Robustness', 'v2x.csv'))
        if 'aoi' not in df.columns or df['aoi'].notna().sum() == 0:
            problems.append('BUG: colonna aoi assente o tutta vuota in v2x.csv')
        axes = set(df['axis'].astype(str)) if 'axis' in df.columns else set()
        need = {'pdr', 'latency', 'jitter', 'gilbert', 'hold_mode', 'blackout'}
        if not need <= axes:
            problems.append('V2X non esaustivo: assi presenti=%s, mancano=%s' % (sorted(axes), sorted(need - axes)))
        if 'collision_rate_oracle' not in df.columns:
            problems.append('V2X: manca collision_rate_oracle (oracolo sotto canale)')
    # quantizzazione fixed + po2, bit spinti fino a 2
    if os.path.isfile(_p('05_Quantization', 'quantization.csv')):
        df = _read_csv(os.path.join('05_Quantization', 'quantization.csv'))
        modes = set(df['mode'].astype(str)) if 'mode' in df.columns else set()
        if not {'fixed', 'po2'} <= modes:
            problems.append('QUANT non esaustivo: modi=%s (attesi fixed+po2)' % sorted(modes))
        bits = set(str(b) for b in df.get('frac_bits', []))
        if '2' not in bits:
            problems.append('QUANT: bit-width non spinto fino a 2 (bits=%s)' % sorted(bits))
    # string a 3 nozioni
    if os.path.isfile(_p('03_StringStability', 'string_stability.csv')):
        df = _read_csv(os.path.join('03_StringStability', 'string_stability.csv'))
        for c in ['head_to_tail', 'peak_gain', 'frac_strict_stable']:
            if c not in df.columns:
                problems.append('STRING: manca la nozione %s in string_stability.csv' % c)


def main():
    if not os.path.isdir(RESULTS):
        print('[verify] cartella risultati assente: %s — il run Azure non e\' stato eseguito?' % RESULTS)
        return 1
    check_files(); check_errors(); check_oracle_present(); check_bugfixes()
    if problems:
        print('[verify] PROBLEMI (%d):' % len(problems))
        for p in problems:
            print('  -', p)
        return 1
    n_png = sum(len(files) for files in EXPECTED.values())
    print('[verify] OK — tutti i file attesi presenti, oracolo esteso, AoI popolata, quant fixed+po2, string 3-nozioni, nessun ERROR_*.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
