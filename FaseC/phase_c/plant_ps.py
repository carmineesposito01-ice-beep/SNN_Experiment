"""Plant sul processore: port 1:1 di qz_cl_sim.m. NESSUNA logica nuova.

L'ordine di update non e' libero (qz_cl_sim.m:26-27):

    v = max(0, v + acc*DT);      % prima la velocita' nuova, con saturazione a 0
    s = s + (vl - v)*DT;         % poi il gap, con la velocita' NUOVA

Invertirlo da' 599 disallineamenti su 600 (misurato in T7a). E' l'esempio canonico di difetto
che produce traiettorie plausibili e sbagliate.

Il teletrasporto `cut_in` (righe 19-21) avviene PRIMA di calcolare dv e di chiamare il
controllore: al passo indicato il gap viene sostituito di netto, non fatto evolvere.
"""

DT = 0.1


def step_plant(s, v, vl, accel, dt=DT):
    """Un passo di plant. Ritorna (s_new, v_new)."""
    v_new = v + accel * dt
    if v_new < 0.0:
        v_new = 0.0                       # max(0, ...): la velocita' non va negativa
    s_new = s + (vl - v_new) * dt         # con la v NUOVA, non quella vecchia
    return s_new, v_new


def run_plant(s_init, v_init, vl_all, accel_fun, cut_in=None, dt=DT):
    """Anello chiuso completo, identico a qz_cl_sim.

    `accel_fun(s, v, dv, vl, first)` -> accel. `first` e' True al primo passo: nel modello
    corrisponde al reset dello stato, sull'hardware al reset AXI.
    `cut_in`: None oppure (k_cut, nuovo_gap), con k_cut in base 1 come in MATLAB.
    """
    s, v = float(s_init), float(v_init)
    S, V, VL, DV, A = [], [], [], [], []
    collided = False
    impact_dv = 0.0

    for k in range(len(vl_all)):
        if cut_in and (k + 1) == int(cut_in[0]):      # base 1, come qz_cl_sim
            s = float(cut_in[1])                     # teletrasporto: nuovo leader piu' vicino
        vl = float(vl_all[k])
        dv = v - vl                                  # dv corrente, PRIMA dell'update
        a = accel_fun(s, v, dv, vl, k == 0)
        S.append(s); V.append(v); VL.append(vl); DV.append(dv); A.append(a)
        s, v = step_plant(s, v, vl, a, dt)
        if s <= 0.0:
            collided = True
            impact_dv = max(0.0, v - vl)
            break

    return {'s': S, 'v': V, 'vl': VL, 'dv': DV, 'a': A,
            'collided': collided, 'impact_dv': impact_dv,
            'min_gap': s if collided else (min(S) if S else float('nan')),
            'n': len(S)}


def plant_par(ref_series, dt=DT, tol=0.0):
    """PLANT-PAR: il plant del processore riproduce il riferimento SENZA acceleratore.

    Si rigiocano le accelerazioni GIA' REGISTRATE nel riferimento: se le traiettorie divergono,
    il difetto e' nel plant e non ha niente a che vedere con l'acceleratore. Farlo prima
    impedisce di attribuire al silicio una divergenza del processore.

    `ref_series`: {'s': [...], 'v': [...], 'vl': [...], 'a': [...]} dal riferimento.
    """
    s = float(ref_series['s'][0])
    v = float(ref_series['v'][0])
    n = nmis = 0
    first = None
    max_ds = max_dv = 0.0

    for k in range(len(ref_series['a'])):
        ds = abs(s - float(ref_series['s'][k]))
        dv_ = abs(v - float(ref_series['v'][k]))
        max_ds = max(max_ds, ds)
        max_dv = max(max_dv, dv_)
        n += 1
        if ds > tol or dv_ > tol:
            nmis += 1
            if first is None:
                first = {'k': k, 'ds': ds, 'dv': dv_,
                         's_ps': s, 's_ref': float(ref_series['s'][k])}
        s, v = step_plant(s, v, float(ref_series['vl'][k]), float(ref_series['a'][k]), dt)

    return {'n': n, 'nmismatch': nmis, 'first': first,
            'max_delta_s': max_ds, 'max_delta_v': max_dv, 'bit_esatto': nmis == 0}
