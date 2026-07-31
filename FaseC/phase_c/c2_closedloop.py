"""C2 - anello chiuso col plant sul processore e l'acceleratore sul silicio.

Decomposizione, la stessa di T7a: in C2 il plant gira sul PS, quindi una sua divergenza si
presenterebbe come un errore del silicio. Per questo il PLANT-PAR viene PRIMA e da solo, e C2
si RIFIUTA di partire finche' non e' verde. Non e' prudenza: un C2 lanciato su un plant che
diverge misura la divergenza del plant e la attribuisce all'acceleratore.
"""
from .plant_ps import run_plant, DT
from .regmap import to_fix, IN_NFRAC, IN_NBITS


class PlantParFailure(RuntimeError):
    pass


def check_plant_par(res):
    """Cancello. Solleva se il plant del processore non riproduce il riferimento."""
    if res['nmismatch'] != 0:
        f = res.get('first') or {}
        raise PlantParFailure(
            'PLANT-PAR rosso: %d disallineamenti su %d (primo al passo %s, delta_s %.3e). '
            'L\'anello NON si chiude finche\' il plant del processore non riproduce il '
            'riferimento: un C2 lanciato ora misurerebbe la divergenza del plant e la '
            'attribuirebbe all\'acceleratore.'
            % (res['nmismatch'], res['n'], f.get('k'), f.get('ds', float('nan'))))
    return True


def run_c2(driver, scenari, plant_par_result, dt=DT):
    """Anello chiuso su uno o piu' scenari.

    `scenari`: lista di dict {'idx', 's_init', 'v_init', 'vl' (lista), 'cut_in' (o None)}.
    Il reset dell'acceleratore a inizio scenario e' obbligatorio: stesso vincolo di C1.
    """
    check_plant_par(plant_par_result)

    out = {}
    for sc in scenari:
        driver.reset_dut(sc['idx'])

        def accel_fun(s, v, dv, vl, first):
            # first e' gia' gestito dal reset_dut a inizio scenario: qui non si rifa'.
            return driver.infer(to_fix(s, IN_NFRAC, IN_NBITS),
                                to_fix(v, IN_NFRAC, IN_NBITS),
                                to_fix(dv, IN_NFRAC, IN_NBITS),
                                to_fix(vl, IN_NFRAC, IN_NBITS))

        out[sc['idx']] = run_plant(sc['s_init'], sc['v_init'], sc['vl'],
                                   accel_fun, cut_in=sc.get('cut_in'), dt=dt)
    return out


def compare_trajectories(hw, ref, tol=0.0):
    """Confronto fra la traiettoria ottenuta sul silicio e quella di riferimento.

    Con tol=0 il confronto e' bit-esatto: e' cio' che ci si aspetta, perche' l'acceleratore
    esegue lo stesso RTL gia' provato bit-esatto e il plant e' lo stesso codice.
    """
    n = min(len(hw['s']), len(ref['s']))
    nmis = 0
    first = None
    max_ds = 0.0
    for k in range(n):
        d = abs(float(hw['s'][k]) - float(ref['s'][k]))
        max_ds = max(max_ds, d)
        if d > tol:
            nmis += 1
            if first is None:
                first = {'k': k, 'hw': hw['s'][k], 'ref': ref['s'][k]}
    return {'n': n, 'nmismatch': nmis, 'max_delta_s': max_ds, 'first': first,
            'len_hw': len(hw['s']), 'len_ref': len(ref['s']),
            'collided_hw': hw['collided'], 'collided_ref': ref['collided'],
            'bit_esatto': nmis == 0 and len(hw['s']) == len(ref['s'])}
