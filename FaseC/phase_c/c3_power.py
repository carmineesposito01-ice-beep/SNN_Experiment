"""C3 - potenza differenziale a livello di scheda.

Il PL consuma 114 mW su 1,5-2,5 W di scheda: in assoluto e' invisibile a un multimetro da 9999
conteggi. Ma il numero cercato non e' assoluto. Stesso hardware, stesso stato del processore,
cambia SOLO il bitstream:

    (b) - (a)   isola il PL          a = blank, b = una istanza
    (b) - (c)   il guadagno del gating   c = una istanza col gating spento

Il consumo del processore, dei regolatori e della periferia si cancella nella differenza.

Tre condizioni perche' la differenza significhi qualcosa. Qui sono CODICE, non raccomandazioni:

  1. ordine RANDOMIZZATO, non alternato. Un A/B/A e' vulnerabile proprio alla deriva che
     pretende di cancellare, e il bias di misura vale +-10% -- abbastanza a invertire una
     conclusione (Mytkowicz et al., ASPLOS 2009).
  2. Tj registrata a ogni punto, punti fuori equilibrio SCARTATI. La statica e' 103 mW su 114
     ed e' esponenziale nella temperatura (WP221).
  3. il risultato e' una DISTRIBUZIONE con l'incertezza dichiarata, non un numero. Un valore
     singolo su una differenza di pochi mA non e' un risultato, e' un'illusione di precisione.
"""
import io
import os
import random
import statistics


# Le configurazioni MISURATE, coi bitstream che esistono davvero (results/bitstream_set.json).
#
#   blank  PL vuoto (LUT 0).            (x1) - (blank) isola il contributo della logica.
#   x1     una istanza, WNS +0,022.     Funzionale.
#   x2     due istanze, WNS -1,060.     SOLO potenza A RIPOSO -- vedi sotto.
#
# ⚠️ x3 NON ESISTE, e non e' un'omissione: il clock gating e' un BUFGCTRL, e lo Zynq-7020 vuole
# la cascata BUFG->BUFGCTRL ADIACENTE. Con tre gate sullo stesso BUFG il piazzatore fallisce
# (rule_cascaded_bufg, misurato). Cio' che impedisce di replicare e' il gate stesso, cioe' la
# funzione da misurare: l'amplificazione massima e' x2, non x3.
#
# ⚠️ x2 non chiude i tempi (94 endpoint su 21 861, cammino DEC->IIDM, lo stesso collo gia' noto
# da T7b). Va usato SOLO per la potenza a riposo, dove nessun dato commuta e quindi nessuna
# violazione di setup si verifica -- la potenza della rete di clock non dipende dallo slack sui
# percorsi dati. NON usarlo per C1/C2.
CONFIGURAZIONI = ('blank', 'x1', 'x2')
GATING = ('on', 'off')          # slv_reg4[1]: un BIT DI REGISTRO, non un bitstream diverso


class ThermalReject(RuntimeError):
    pass


def punti_di_misura(configs=CONFIGURAZIONI, gating=GATING):
    """I punti realmente distinti: (configurazione, stato del gating).

    Su `blank` il PL e' vuoto e il bit di gating non comanda nulla: un punto solo, marcato '-'.
    Misurare blank/on e blank/off separatamente darebbe due repliche della stessa cosa spacciate
    per due condizioni, e ne gonfierebbe il peso nell'aggregato.
    """
    punti = []
    for c in configs:
        if c == 'blank':
            punti.append((c, '-'))
        else:
            punti.extend((c, g) for g in gating)
    return punti


def plan_sequence(punti, repeats, seed):
    """Sequenza di misura SORTEGGIATA.

    Non alternata: alternare A/B/A/B correla la condizione con l'istante, ed e' esattamente
    il modo in cui una deriva termica lenta si traveste da differenza fra configurazioni.
    Il seme va DICHIARATO nell'artefatto: senza, la sequenza non e' ripetibile.

    Il sorteggio copre i PUNTI, non le sole configurazioni. Il gating si cambia con una scrittura
    di registro invece che con un bitstream, quindi verrebbe naturale visitarlo sempre nello
    stesso ordine dentro ogni configurazione -- e sarebbe di nuovo una condizione correlata
    all'istante, cioe' la cosa che il sorteggio esiste per rompere.
    """
    if repeats < 1:
        raise ValueError('repeats deve essere >= 1')
    seq = [p for p in punti for _ in range(repeats)]
    random.Random(seed).shuffle(seq)
    return seq


class SorgenteNonValidata(RuntimeError):
    pass


def _pretendi_sorgente_valida(dmm):
    """Il cancello sulla sorgente, PRIMA di misurare.

    Una sorgente che porta l'attributo `validato` dichiara di aver bisogno di essere provata
    contro il display: e' il caso della seriale, il cui parser sbagliato non da' errore ma numeri
    verosimili. Chi non lo porta (prompt, rigioco) non ha nulla da validare e passa.
    Lasciarlo facoltativo lo renderebbe un cancello che non si chiude mai.
    """
    if getattr(dmm, 'validato', None) is False:
        raise SorgenteNonValidata(
            'la sorgente %r non e\' stata validata contro il display. Eseguire '
            'verifica_contro_display() con un valore stabile e noto: senza, non c\'e\' modo di '
            'distinguere un parser corretto da uno che restituisce un numero verosimile.'
            % getattr(dmm, 'sorgente', dmm))


def chiave_condizione(p):
    """La condizione sperimentale di un punto, in UN SOLO posto.

    Non e' la configurazione: `x1` col gating acceso e `x1` col gating spento sono due condizioni
    diverse, ed e' proprio la loro differenza il numero che C3 cerca. Raggruppare per sola `cfg`
    le fonderebbe nella stessa mediana e il guadagno del gating sparirebbe nella media -- un
    risultato credibile e vuoto.

    Un punto senza campo `gating` (formato piu' vecchio) resta indicizzato dalla sola cfg.
    """
    g = p.get('gating')
    return p['cfg'] if g is None else '%s/%s' % (p['cfg'], g)


def _pct(vals, q):
    s = sorted(vals)
    return s[min(len(s) - 1, int(q * len(s)))]


def aggregate(points, tj_window):
    """Da punti grezzi a distribuzione per CONDIZIONE (vedi `chiave_condizione`).

    `points`: [{'cfg', 'gating', 'mA', 'tj'}, ...]. `tj_window`: (min, max) in gradi Celsius.
    I punti fuori banda si SCARTANO e il conteggio degli scartati resta nell'artefatto: un
    punto scartato in silenzio e' un punto che nessuno potra' piu' rimettere in discussione.
    """
    lo, hi = tj_window
    out = {}
    for cfg in sorted({chiave_condizione(p) for p in points}):
        tutti = [p for p in points if chiave_condizione(p) == cfg]
        buoni = [float(p['mA']) for p in tutti if lo <= float(p['tj']) <= hi]
        if not buoni:
            raise ThermalReject(
                'configurazione %r: nessuno dei %d punti sta nella banda termica '
                '[%.1f, %.1f] degC. La misura non e\' utilizzabile: la dispersione statica e\' '
                'esponenziale in Tj e la statica domina il consumo del PL.'
                % (cfg, len(tutti), lo, hi))
        b = sorted(buoni)
        q1, q3 = _pct(b, 0.25), _pct(b, 0.75)
        out[cfg] = dict(mediana=statistics.median(b), minimo=b[0], massimo=b[-1],
                        p99=_pct(b, 0.99), iqr=q3 - q1,
                        n=len(b), n_scartati=len(tutti) - len(buoni),
                        tj_min=min(float(p['tj']) for p in tutti),
                        tj_max=max(float(p['tj']) for p in tutti))
    return out


def differenza_mW(agg, a, b, volt=5.0, n_istanze=1):
    """(b - a) in mW per istanza, con l'incertezza propagata dalla dispersione.

    L'incertezza non e' un ornamento: se e' dello stesso ordine della differenza, la
    conclusione e' "non separabile con questo strumento" -- e va scritta cosi'.
    """
    for k in (a, b):
        if k not in agg:
            raise KeyError('configurazione %r assente dall\'aggregato' % k)
    d_mA = agg[b]['mediana'] - agg[a]['mediana']
    unc_mA = (agg[a]['iqr'] + agg[b]['iqr']) / 2.0
    d_mW = d_mA * volt / n_istanze
    u_mW = unc_mA * volt / n_istanze
    return {'delta_mW_per_istanza': d_mW, 'incertezza_mW': u_mW,
            'n_istanze': n_istanze, 'volt': volt,
            'separabile': abs(d_mW) > 2.0 * u_mW,
            'nota': ('differenza maggiore del doppio dell\'incertezza: separabile'
                     if abs(d_mW) > 2.0 * u_mW else
                     'differenza dello stesso ordine dell\'incertezza: NON separabile con '
                     'questo strumento. Aumentare le repliche o le istanze, oppure dichiararlo '
                     'come limite invece di riportare un numero.')}


# --------------------------------------------------------------------- la campagna

class BancoDiMisura(object):
    """Cio' che il runner si aspetta dall'hardware. L'implementazione vera vive in `cli.py`.

    Tenerla fuori da qui e' voluto: questo modulo decide il METODO (ordine, equilibrio, scarto),
    e non deve sapere se sotto c'e' una PYNQ, un mock o una registrazione. Con l'hardware cablato
    dentro, il metodo non sarebbe provabile senza scheda.
    """

    def carica(self, cfg):
        """Porta il PL nella configurazione `cfg` (ricarica del bitstream)."""
        raise NotImplementedError

    def imposta_gating(self, stato):
        """Scrive il bit di gating: 'on' | 'off'. Mai chiamato per il punto '-'."""
        raise NotImplementedError

    def leggi_tj(self):
        raise NotImplementedError

    def leggi_vccint(self):
        raise NotImplementedError


_INTESTAZIONE = 'idx,cfg,gating,tj,vccint,mA,tj_dopo,deriva_c\n'


def esegui_campagna(dmm, banco, seed, repeats=8, punti=None, csv_path=None,
                    intervallo_s=5.0, max_attesa_s=600.0, stampa=print):
    """Esegue la campagna C3 e restituisce i punti grezzi + la provenienza della sequenza.

    `seed` NON ha default: e' la decisione che rende la campagna ripetibile, e un default
    silenzioso darebbe una sequenza "sorteggiata" che nessuno ha scelto.

    Il foglio si scrive RIGA PER RIGA con flush: una campagna dura ore e un'interruzione a meta'
    non deve costare i punti gia' misurati.
    """
    from phase_c.dmm import attendi_equilibrio
    from phase_c.xadc import EQ_BAND_C

    _pretendi_sorgente_valida(dmm)
    punti = list(punti if punti is not None else punti_di_misura())
    seq = plan_sequence(punti, repeats=repeats, seed=seed)

    f = None
    if csv_path:
        nuovo = not os.path.exists(csv_path)
        f = io.open(csv_path, 'a', encoding='utf-8', newline='')
        if nuovo:
            f.write(_INTESTAZIONE)
            f.flush()

    misure, sospetti = [], 0
    try:
        for i, (cfg, gate) in enumerate(seq):
            stampa('[%3d/%d] %s gating=%s -- carico e attendo l\'equilibrio' %
                   (i + 1, len(seq), cfg, gate))
            banco.carica(cfg)
            if gate != '-':
                banco.imposta_gating(gate)

            eq = attendi_equilibrio(banco.leggi_tj, intervallo_s=intervallo_s,
                                    max_attesa_s=max_attesa_s)
            tj, vcc = banco.leggi_tj(), banco.leggi_vccint()
            mA = dmm.leggi_mA(etichetta='%s gating=%s' % (cfg, gate))
            tj_dopo = banco.leggi_tj()

            # La lettura manuale puo' durare una decina di secondi: se la temperatura si e' mossa
            # nel frattempo, la Tj registrata non descrive l'istante della corrente. Si annota
            # invece di scartare al volo -- e' l'aggregato, con la sua banda, a decidere.
            deriva = abs(tj_dopo - tj)
            if deriva > EQ_BAND_C:
                sospetti += 1
                stampa('  ATTENZIONE: Tj si e\' mossa di %.2f degC durante la lettura '
                       '(banda %.2f): punto marcato.' % (deriva, EQ_BAND_C))

            p = {'idx': i, 'cfg': cfg, 'gating': gate, 'mA': mA, 'tj': tj, 'vccint': vcc,
                 'tj_dopo': tj_dopo, 'deriva_c': deriva, 'attesa_equilibrio_s': eq['attesa_s']}
            misure.append(p)
            if f:
                f.write('%d,%s,%s,%.4f,%.5f,%.4f,%.4f,%.4f\n' %
                        (i, cfg, gate, tj, vcc, mA, tj_dopo, deriva))
                f.flush()
    finally:
        if f:
            f.close()

    return {'punti': misure, 'seed': seed, 'repeats': repeats,
            'sequenza': ['%s/%s' % (c, g) for c, g in seq],
            'punti_previsti': ['%s/%s' % (c, g) for c, g in punti],
            'sorgente_dmm': getattr(dmm, 'sorgente', 'ignota'),
            'n_deriva_durante_lettura': sospetti,
            'csv': csv_path}
