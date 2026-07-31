"""C1 - il silicio riproduce la simulazione, BIT-ESATTO.

Non "entro tolleranza": T7a ha provato l'RTL bit-esatto al blocco su 58 522 confronti, e il
silicio esegue quello stesso RTL. Una discrepanza qui e' un errore di DEPLOYMENT -- formato,
indirizzi, protocollo -- non un errore d'algoritmo. Accettare una tolleranza significherebbe
rendere invisibile proprio la classe di difetti che C1 esiste per trovare.

La scaletta diagnostica e' ordinata per PROBABILITA' data la firma osservata, non per gusto.
Il formato numerico sta in cima perche' e' l'unico che produce risultati PLAUSIBILI.
"""

# (chiave, sintomo, dove guardare)
SOSPETTI = (
    ('formato numerico al confine',
     'valori plausibili ma sbagliati, con errore che SCALA con la grandezza',
     'En20 in ingresso, sfix13_En8 in uscita, larghezza del campo letto (13/16/32)'),
    ('mappa degli indirizzi',
     'letture a zero o costanti fin dal primo campione',
     'offset dei registri contro snniidm_axi_lite.v'),
    ('START che non si auto-azzera',
     'la PRIMA inferenza e\' giusta, tutte le successive no',
     'ritorno a idle della macchina a stati; commit tenuto alto'),
    ('polarita del reset',
     'stato sempre nullo: l\'acceleratore non esce dal reset',
     'verso del reset al confine del wrapper'),
    ('pipelining insufficiente',
     'errori INTERMITTENTI e sparsi, non sistematici',
     'report di timing PRIMA di incolpare l\'algoritmo'),
)


def diagnose(first, n, nmismatch, ratios=None):
    """Ordina i sospettati per compatibilita' col quadro osservato.

    `ratios`: got/exp sui campioni discrepanti, quando exp != 0. Un rapporto COSTANTE e diverso
    da 1 e' la firma del formato: e' un fattore di scala, cioe' un errore di esponente.
    """
    tutti = (n > 0 and nmismatch == n)
    peso = {k: 0 for k, _, _ in SOSPETTI}

    if ratios:
        r = [x for x in ratios if x is not None]
        if r:
            costante = (max(r) - min(r)) < 1e-6 * max(1.0, abs(max(r)))
            # Un rapporto costante e diverso da 1 e' un errore di ESPONENTE: il formato.
            # Ma un rapporto costante ZERO non lo e': non e' "scalato", non e' tornato nulla.
            # Confonderli manderebbe a cercare il formato mentre il bus e' muto.
            if costante and abs(r[0] - 1.0) > 1e-9 and abs(r[0]) > 1e-12:
                peso['formato numerico al confine'] += 3
            if not costante and 0 < nmismatch < max(1, int(0.2 * n)):
                peso['pipelining insufficiente'] += 2

    if tutti and first and first.get('got') == 0:
        peso['mappa degli indirizzi'] += 3
        peso['polarita del reset'] += 2
    if n > 1 and nmismatch == n - 1 and first and first.get('k') == 1:
        peso['START che non si auto-azzera'] += 4
    if 0 < nmismatch < max(1, int(0.05 * n)):
        peso['pipelining insufficiente'] += 2

    ordinati = sorted(SOSPETTI, key=lambda t: -peso[t[0]])
    return ['%s -> %s. Guardare: %s' % t for t in ordinati]


def run_c1(driver, goldens, max_report=20, reset_between=True):
    """Replay degli scenari sugli ingressi REGISTRATI, confronto bit-esatto.

    Ingressi registrati, non rigenerati: cosi' C1 misura l'acceleratore e nient'altro. Se il
    plant girasse qui dentro, una sua divergenza si presenterebbe come un errore del silicio.

    `reset_between=True` NON e' una precauzione, e' un vincolo dell'hardware: nel wrapper
    `started` si alza al primo commit e non torna basso senza reset AXI, quindi lo stato della
    rete non e' azzerabile dai registri. Ogni golden pero' e' stato prodotto con la rete
    azzerata all'inizio di QUEL scenario. `False` esiste solo per PROVARE che il vincolo e'
    reale -- non usarlo per misurare.
    """
    n = nmis = 0
    first = None
    ratios = []
    per_scen = []
    campioni = []

    for g in goldens:
        if reset_between:
            driver.reset_dut(g.idx)
        s_n = s_mis = 0
        for k, (stim, exp) in enumerate(zip(g.stim, g.gold)):
            got = driver.infer(*stim)
            n += 1
            s_n += 1
            if got != exp:
                nmis += 1
                s_mis += 1
                if first is None:
                    first = {'scen': g.idx, 'k': k, 'got': got, 'exp': exp}
                if exp != 0:
                    ratios.append(got / exp)
                if len(campioni) < max_report:
                    campioni.append({'scen': g.idx, 'k': k, 'got': got, 'exp': exp})
        per_scen.append({'scen': g.idx, 'n': s_n, 'nmismatch': s_mis})

    res = {'n': n, 'nmismatch': nmis, 'n_scenari': len(goldens),
           'bit_esatto': nmis == 0, 'first': first, 'per_scenario': per_scen}
    if nmis:
        res['campioni'] = campioni
        res['diagnosi'] = diagnose(first, n, nmis, ratios)
    return res
