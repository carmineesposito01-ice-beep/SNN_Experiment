"""C3 e' la misura che puo' ingannare: 114 mW dentro 2 W, letti con un multimetro da 9999
conteggi. Questi test non provano che il numero sia giusto -- non c'e' hardware -- ma che il
METODO impedisca i tre modi noti di ottenere un numero credibile e sbagliato.
"""
import pytest

from phase_c.c3_power import plan_sequence, aggregate, differenza_mW, ThermalReject
from phase_c.xadc import at_equilibrium, EQ_BAND_C, EQ_N


CFG = ('blank', 'g0', 'g1')


# --------------------------------------------------------------- 1. l'ordine e' sorteggiato

def test_l_ordine_e_RANDOMIZZATO_non_alternato():
    """Mytkowicz 2009: il bias di misura vale +-10%, abbastanza a invertire una conclusione.
    Un A/B/A alternato correla la configurazione con l'istante ed e' vulnerabile proprio alla
    deriva che pretende di cancellare."""
    seqs = {tuple(plan_sequence(CFG, repeats=6, seed=s)) for s in range(8)}
    assert len(seqs) > 1, 'la sequenza non cambia col seme: non e\' sorteggiata'
    alternata = tuple(list(CFG) * 6)
    assert alternata not in seqs


def test_ogni_configurazione_compare_lo_STESSO_numero_di_volte():
    for s in range(5):
        seq = plan_sequence(CFG, repeats=6, seed=s)
        assert len(seq) == 18
        assert all(seq.count(c) == 6 for c in CFG)


def test_lo_stesso_seme_da_la_stessa_sequenza():
    """Il seme sta nell'artefatto: senza, la sequenza non e' ripetibile e la misura nemmeno."""
    assert plan_sequence(CFG, 6, 42) == plan_sequence(CFG, 6, 42)


def test_repeats_a_zero_e_un_errore_non_una_sequenza_vuota():
    with pytest.raises(ValueError):
        plan_sequence(CFG, repeats=0, seed=0)


# ------------------------------------------------------------------ 2. Tj come cancello

def test_i_punti_fuori_equilibrio_termico_si_SCARTANO():
    pts = [{'cfg': 'g0', 'mA': 400.0, 'tj': 45.0},
           {'cfg': 'g0', 'mA': 402.0, 'tj': 45.2},
           {'cfg': 'g0', 'mA': 398.0, 'tj': 61.0}]
    r = aggregate(pts, tj_window=(40.0, 50.0))
    assert r['g0']['n'] == 2 and r['g0']['n_scartati'] == 1


def test_gli_scartati_RESTANO_nell_artefatto():
    """Uno scarto silenzioso e' uno scarto che nessuno potra' piu' rimettere in discussione."""
    pts = [{'cfg': 'g0', 'mA': 400.0, 'tj': 45.0}, {'cfg': 'g0', 'mA': 1.0, 'tj': 90.0}]
    r = aggregate(pts, tj_window=(40.0, 50.0))
    assert r['g0']['n_scartati'] == 1
    assert r['g0']['tj_max'] == 90.0, 'la Tj estrema deve restare visibile'


def test_scarta_TUTTO_se_nessun_punto_e_in_banda():
    with pytest.raises(ThermalReject, match='esponenziale in Tj'):
        aggregate([{'cfg': 'g0', 'mA': 400.0, 'tj': 70.0}], tj_window=(40.0, 50.0))


def test_il_criterio_di_equilibrio_e_DICHIARATO_e_funziona_nei_due_versi():
    assert at_equilibrium([45.0 + 0.01 * k for k in range(EQ_N)]) is True
    assert at_equilibrium([45.0 + 0.2 * k for k in range(EQ_N)]) is False   # deriva
    assert at_equilibrium([45.0] * (EQ_N - 1)) is False                     # troppo pochi
    assert EQ_BAND_C == 0.5 and EQ_N == 12


# ------------------------------------------------------ 3. distribuzione, non un numero

def test_il_risultato_e_una_DISTRIBUZIONE():
    pts = [{'cfg': 'g1', 'mA': 400.0 + 0.1 * i, 'tj': 45.0} for i in range(20)]
    r = aggregate(pts, tj_window=(40.0, 50.0))
    for k in ('mediana', 'p99', 'minimo', 'massimo', 'iqr', 'n', 'n_scartati'):
        assert k in r['g1']


def test_una_differenza_NETTA_e_dichiarata_separabile():
    pts = ([{'cfg': 'g0', 'mA': 400.0 + 0.05 * i, 'tj': 45.0} for i in range(20)] +
           [{'cfg': 'g1', 'mA': 380.0 + 0.05 * i, 'tj': 45.0} for i in range(20)])
    d = differenza_mW(aggregate(pts, (40.0, 50.0)), 'g0', 'g1')
    assert d['separabile'] and d['delta_mW_per_istanza'] < 0


def test_una_differenza_DENTRO_IL_RUMORE_e_dichiarata_NON_separabile():
    """E' l'esito che conta di piu': dire "non separabile" e' un risultato, inventare un
    numero dentro il rumore no."""
    pts = ([{'cfg': 'g0', 'mA': 400.0 + (i % 7), 'tj': 45.0} for i in range(20)] +
           [{'cfg': 'g1', 'mA': 399.8 + (i % 7), 'tj': 45.0} for i in range(20)])
    d = differenza_mW(aggregate(pts, (40.0, 50.0)), 'g0', 'g1')
    assert not d['separabile']
    assert 'NON separabile' in d['nota']


def test_la_differenza_e_PER_ISTANZA():
    """La replicazione x3 serve ad amplificare il segnale: il numero riportato torna a una."""
    pts = ([{'cfg': 'blank', 'mA': 400.0, 'tj': 45.0}] * 8 +
           [{'cfg': 'x3', 'mA': 430.0, 'tj': 45.0}] * 8)
    d = differenza_mW(aggregate(pts, (40.0, 50.0)), 'blank', 'x3', n_istanze=3)
    assert d['delta_mW_per_istanza'] == pytest.approx(30.0 * 5.0 / 3.0)


def test_configurazione_assente_e_un_errore_esplicito():
    pts = [{'cfg': 'g0', 'mA': 400.0, 'tj': 45.0}]
    with pytest.raises(KeyError, match='assente'):
        differenza_mW(aggregate(pts, (40.0, 50.0)), 'g0', 'mai_misurata')


# ------------------------------------- 4. la campagna: punti, sorteggio, cancello sorgente

from phase_c.c3_power import (punti_di_misura, chiave_condizione, esegui_campagna,
                              SorgenteNonValidata, CONFIGURAZIONI)
from phase_c.dmm import PromptDMM, SerialDMM


def test_su_blank_il_gating_NON_e_una_condizione():
    """Il PL e' vuoto: il bit non comanda nulla. Misurare blank/on e blank/off darebbe due
    repliche della stessa cosa spacciate per due condizioni, gonfiandone il peso."""
    p = punti_di_misura()
    assert ('blank', '-') in p
    assert not [x for x in p if x[0] == 'blank' and x[1] != '-']
    assert ('x1', 'on') in p and ('x1', 'off') in p
    assert len(p) == 5                     # blank + (x1,x2) x (on,off)


def test_il_sorteggio_copre_anche_il_GATING_non_solo_la_configurazione():
    """Il gating si cambia con una scrittura di registro: verrebbe naturale visitarlo sempre
    nello stesso ordine dentro ogni configurazione, ricreando la correlazione con l'istante."""
    seq = plan_sequence(punti_di_misura(), repeats=4, seed=7)
    dentro_x1 = [g for c, g in seq if c == 'x1']
    assert dentro_x1 != ['on'] * 4 + ['off'] * 4
    assert dentro_x1 != ['on', 'off'] * 4


def test_x1_acceso_e_x1_spento_NON_finiscono_nello_stesso_gruppo():
    """E' il guadagno del gating, cioe' il numero che C3 cerca: fonderli lo cancellerebbe
    nella media lasciando un risultato credibile e vuoto."""
    pts = ([{'cfg': 'x1', 'gating': 'on', 'mA': 400.0, 'tj': 45.0}] * 6 +
           [{'cfg': 'x1', 'gating': 'off', 'mA': 380.0, 'tj': 45.0}] * 6)
    agg = aggregate(pts, (40.0, 50.0))
    assert set(agg) == {'x1/on', 'x1/off'}
    assert agg['x1/on']['mediana'] == 400.0 and agg['x1/off']['mediana'] == 380.0
    d = differenza_mW(agg, 'x1/off', 'x1/on')
    assert d['delta_mW_per_istanza'] == pytest.approx(20.0 * 5.0)


def test_un_punto_SENZA_gating_resta_indicizzato_dalla_sola_cfg():
    assert chiave_condizione({'cfg': 'x1'}) == 'x1'
    assert chiave_condizione({'cfg': 'x1', 'gating': 'off'}) == 'x1/off'


# --- il cancello sulla sorgente

class _BancoFinto(object):
    def __init__(self):
        self.caricati, self.gating = [], []

    def carica(self, cfg):
        self.caricati.append(cfg)

    def imposta_gating(self, stato):
        self.gating.append(stato)

    def leggi_tj(self):
        return 45.0

    def leggi_vccint(self):
        return 0.998


def _dmm_finto(val=400.0):
    return PromptDMM(chiedi=lambda p: str(val))


def test_una_seriale_NON_validata_ferma_la_campagna_PRIMA_di_misurare():
    """Il cancello che mancava: verifica_contro_display esisteva ma nessuno la pretendeva.
    Un cancello facoltativo non e' un cancello."""
    seriale = SerialDMM('COM_finta', parser=lambda ser: 400.0)      # mai validata
    banco = _BancoFinto()
    with pytest.raises(SorgenteNonValidata, match='numero verosimile'):
        esegui_campagna(seriale, banco, seed=1, repeats=1, stampa=lambda *_: None)
    assert banco.caricati == [], 'si e\' fermata DOPO aver gia\' toccato l\'hardware'


def test_una_seriale_VALIDATA_passa():
    """L'altra direzione: il cancello deve anche lasciar passare il caso vero."""
    seriale = SerialDMM('COM_finta', parser=lambda ser: 400.0)
    seriale._ser = object()
    seriale.verifica_contro_display(400.0)
    r = esegui_campagna(seriale, _BancoFinto(), seed=1, repeats=1,
                        punti=[('x1', 'on')], intervallo_s=0, stampa=lambda *_: None)
    assert len(r['punti']) == 1 and r['sorgente_dmm'] == 'seriale'


def test_il_prompt_e_il_rigioco_non_hanno_nulla_da_validare():
    r = esegui_campagna(_dmm_finto(), _BancoFinto(), seed=3, repeats=2,
                        intervallo_s=0, stampa=lambda *_: None)
    assert len(r['punti']) == 10           # 5 punti x 2 repliche
    assert r['n_deriva_durante_lettura'] == 0, \
        'a temperatura costante il contatore delle derive deve restare a zero, altrimenti ' \
        'marca tutto e non distingue nulla'


def test_il_seme_e_la_sequenza_FINISCONO_nel_risultato():
    """Senza il seme nell'artefatto la campagna non e' ripetibile, e il sorteggio diventa
    solo un disordine di cui nessuno puo' rifare la strada."""
    r = esegui_campagna(_dmm_finto(), _BancoFinto(), seed=99, repeats=1,
                        intervallo_s=0, stampa=lambda *_: None)
    assert r['seed'] == 99
    assert r['sequenza'] == ['%s/%s' % p for p in plan_sequence(punti_di_misura(), 1, 99)]


def test_il_gating_NON_si_scrive_sul_punto_blank():
    banco = _BancoFinto()
    esegui_campagna(_dmm_finto(), banco, seed=5, repeats=1, punti=[('blank', '-')],
                    intervallo_s=0, stampa=lambda *_: None)
    assert banco.caricati == ['blank'] and banco.gating == []


def test_il_foglio_si_scrive_RIGA_PER_RIGA(tmp_path):
    """Una campagna dura ore: un'interruzione a meta' non deve costare i punti gia' misurati."""
    csv = str(tmp_path / 'campagna.csv')
    esegui_campagna(_dmm_finto(412.5), _BancoFinto(), seed=2, repeats=1, csv_path=csv,
                    intervallo_s=0, stampa=lambda *_: None)
    righe = open(csv, encoding='utf-8').read().strip().split('\n')
    assert len(righe) == 6 and righe[0].startswith('idx,cfg,gating')
    assert '412.5000' in righe[1]


def test_una_DERIVA_durante_la_lettura_viene_CONTATA(tmp_path):
    """La trascrizione manuale dura secondi: se Tj si muove nel frattempo, la temperatura
    registrata non descrive l'istante della corrente."""
    class BancoCheScalda(_BancoFinto):
        def __init__(self):
            _BancoFinto.__init__(self)
            self.k = 0

        def leggi_tj(self):
            self.k += 1
            return 45.0 + (3.0 if self.k > 13 else 0.0)   # salta DOPO l'equilibrio

    r = esegui_campagna(_dmm_finto(), BancoCheScalda(), seed=4, repeats=1,
                        punti=[('x1', 'on')], intervallo_s=0, stampa=lambda *_: None)
    assert r['n_deriva_durante_lettura'] == 1
    assert r['punti'][0]['deriva_c'] == pytest.approx(3.0)


# --------------------------- 5. dispersione di UNA lettura != incertezza della MEDIANA

def _punti(cfg, gating, n, centro, ampiezza=4.0):
    """n letture attorno a `centro`, con la STESSA dispersione qualunque sia n.

    ⚠️ `n` dev'essere multiplo di 5: il motivo del ciclo e' che ogni valore compaia lo stesso
    numero di volte. Con un ciclo incompleto l'IQR cambia con n, e il test misurerebbe quello
    invece dell'effetto delle repliche.
    """
    assert n % 5 == 0, 'n deve essere multiplo di 5, altrimenti la dispersione dipende da n'
    return [{'cfg': cfg, 'gating': gating, 'tj': 45.0,
             'mA': centro + ampiezza * ((i % 5) - 2) / 2.0} for i in range(n)]


def test_le_REPLICHE_contano_a_parita_di_effetto_e_di_dispersione():
    """E' la ragione della formula. Con l'incertezza presa dall'IQR le repliche non servivano a
    niente -- l'incertezza non scendeva mai -- e il guadagno atteso del gating (~1,4 mA su un
    fondo di ~400) sarebbe stato "non separabile" con qualunque numero di letture: un limite
    dell'aritmetica spacciato per un limite dello strumento."""
    def esito(n):
        pts = _punti('x1', 'off', n, 400.0) + _punti('x1', 'on', n, 398.6)   # 1,4 mA di effetto
        return differenza_mW(aggregate(pts, (40.0, 50.0)), 'x1/off', 'x1/on')

    poche, molte = esito(10), esito(400)
    assert not poche['separabile'], 'con 10 letture 1,4 mA non deve essere distinguibile'
    assert molte['separabile'], 'con 400 letture deve esserlo: e\' il senso delle repliche'
    assert molte['dispersione_mW'] == pytest.approx(poche['dispersione_mW'], rel=0.2), \
        'la DISPERSIONE non deve cambiare: e\' l\'errore standard che scende, non lo strumento'
    assert molte['incertezza_mW'] < poche['incertezza_mW'] / 3


def test_la_dispersione_resta_RIPORTATA_accanto_all_errore_standard():
    """Serve a decidere quante repliche fare: e' la proprieta' dello strumento, non della stima."""
    pts = _punti('x1', 'off', 20, 400.0) + _punti('x1', 'on', 20, 390.0)
    d = differenza_mW(aggregate(pts, (40.0, 50.0)), 'x1/off', 'x1/on')
    assert d['dispersione_mW'] > d['incertezza_mW'], \
        'con n>1 l\'errore standard deve stare SOTTO la dispersione'
    assert d['n_punti'] == {'x1/off': 20, 'x1/on': 20}


def test_quando_NON_e_separabile_dice_quante_repliche_servirebbero():
    """Un "non separabile" senza il numero e' un vicolo cieco; col numero e' una decisione."""
    pts = _punti('x1', 'off', 10, 400.0) + _punti('x1', 'on', 10, 399.6)
    d = differenza_mW(aggregate(pts, (40.0, 50.0)), 'x1/off', 'x1/on')
    assert not d['separabile']
    import re
    m = re.search(r'circa (\d+) repliche', d['nota'])
    assert m, 'la nota deve contenere il numero di repliche'
    assert int(m.group(1)) > d['n_punti']['x1/off'], \
        'deve chiedere PIU\' repliche di quelle gia\' fatte: un numero minore sarebbe una ' \
        'risposta senza senso, e il test la accetterebbe senza accorgersene'


def test_un_punto_solo_non_puo_dichiarare_nulla_di_separabile():
    """Con n=1 l'errore standard non e' stimabile: separabile=True sarebbe una certezza inventata."""
    pts = [{'cfg': 'a', 'gating': '-', 'mA': 400.0, 'tj': 45.0},
           {'cfg': 'b', 'gating': '-', 'mA': 300.0, 'tj': 45.0}]
    d = differenza_mW(aggregate(pts, (40.0, 50.0)), 'a/-', 'b/-')
    assert not d['separabile'], 'una differenza enorme su un punto solo non e\' un risultato'


# ------------------------------- 6. pre-flight: quante repliche, e quanto costano

from phase_c.c3_power import repliche_necessarie, misura_dispersione, EFFETTO_ATTESO_MA


def test_piu_rumore_vuole_piu_repliche_e_va_col_QUADRATO():
    """Non e' un dettaglio: fra IQR 2 e IQR 4 la campagna passa da mezza giornata a due."""
    n2, n4 = repliche_necessarie(2.0), repliche_necessarie(4.0)
    assert n4 > n2
    assert n4 == pytest.approx(4 * n2, rel=0.1), 'raddoppiare il rumore quadruplica le repliche'


def test_amplificare_le_ISTANZE_abbassa_le_repliche_col_quadrato():
    """E' l'intera ragione per cui x2 esiste: segnale doppio, rumore invariato."""
    assert repliche_necessarie(4.0, n_istanze=2) == pytest.approx(
        repliche_necessarie(4.0, n_istanze=1) / 4.0, rel=0.15)


def test_il_numero_suggerito_RENDE_davvero_separabile_l_effetto():
    """Il cancello che conta: la formula inversa deve concordare con differenza_mW, altrimenti
    e' un numero che sembra una risposta. Provato anche UNA replica sotto."""
    iqr, eff = 3.0, EFFETTO_ATTESO_MA
    n = repliche_necessarie(iqr, n_istanze=1)
    agg_n = {'a': {'mediana': 400.0, 'iqr': iqr, 'n': n},
             'b': {'mediana': 400.0 - eff, 'iqr': iqr, 'n': n}}
    agg_meno = {'a': {'mediana': 400.0, 'iqr': iqr, 'n': n - 1},
                'b': {'mediana': 400.0 - eff, 'iqr': iqr, 'n': n - 1}}
    assert differenza_mW(agg_n, 'a', 'b')['separabile'], 'n suggerito deve bastare'
    assert not differenza_mW(agg_meno, 'a', 'b')['separabile'], 'n-1 non deve bastare: e\' il MINIMO'


def test_una_dispersione_nulla_non_chiede_infinite_repliche():
    assert repliche_necessarie(0.0) == 2


# --- misura della dispersione: una sola visita

def test_la_dispersione_si_misura_in_UNA_visita_non_in_k():
    """Se pagasse un'attesa di equilibrio per lettura non sarebbe un pre-flight: costerebbe
    quanto la campagna che deve dimensionare."""
    banco = _BancoFinto()
    valori = iter([400.0, 401.0, 399.0, 402.0, 400.5, 401.5, 399.5, 400.2, 401.2, 399.8])
    dmm = PromptDMM(chiedi=lambda p: str(next(valori)))
    r = misura_dispersione(dmm, banco, k=10, intervallo_s=0, stampa=lambda *_: None)
    assert banco.caricati == ['blank'], 'una sola visita, una sola ricarica'
    assert r['iqr_mA'] > 0 and r['k'] == 10


def test_le_letture_della_dispersione_NON_si_chiamano_punti():
    """Pseudo-replicazione: usarle come repliche restringerebbe l'errore standard senza che
    nulla di reale sia stato ripetuto. Il nome del campo lo rende difficile per sbaglio."""
    banco = _BancoFinto()
    valori = iter([400.0 + (i % 3) for i in range(10)])
    dmm = PromptDMM(chiedi=lambda p: str(next(valori)))
    r = misura_dispersione(dmm, banco, k=10, intervallo_s=0, stampa=lambda *_: None)
    assert 'punti' not in r and 'letture' in r
    assert 'pseudo-replicazione' in r['nota']


def test_la_dispersione_SUGGERISCE_le_repliche_per_x1_e_x2():
    banco = _BancoFinto()
    valori = iter([400.0 + 2.0 * ((i % 5) - 2) for i in range(10)])
    dmm = PromptDMM(chiedi=lambda p: str(next(valori)))
    r = misura_dispersione(dmm, banco, k=10, intervallo_s=0, stampa=lambda *_: None)
    s = r['repliche_suggerite']
    assert s['x1'] == repliche_necessarie(r['iqr_mA'], n_istanze=1)
    assert s['x2'] < s['x1'], 'x2 amplifica: deve chiederne meno'


def test_anche_il_preflight_pretende_una_sorgente_VALIDATA():
    """Misurare la dispersione con un parser non validato darebbe un rumore che non e' quello
    dello strumento -- e dimensionerebbe l'intera campagna su un numero sbagliato."""
    seriale = SerialDMM('COM_finta', parser=lambda ser: 400.0)
    with pytest.raises(SorgenteNonValidata):
        misura_dispersione(seriale, _BancoFinto(), k=3, intervallo_s=0, stampa=lambda *_: None)


def test_la_tabella_del_RUNBOOK_viene_dal_CODICE():
    """Una tabella scritta a mano diverge dalla formula al primo ritocco, e la versione letta
    dall'operatore sarebbe quella sbagliata."""
    import io as _io
    import os as _os
    import re
    p = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), 'RUNBOOK.md')
    testo = _io.open(p, encoding='utf-8').read()
    righe = re.findall(r'^\| (\d,\d) \| \*?\*?(\d+)\*?\*? \| (\d+) \|', testo, re.M)
    assert len(righe) >= 4, 'tabella delle repliche non trovata nel RUNBOOK'
    for iqr_txt, n1, n2 in righe:
        iqr = float(iqr_txt.replace(',', '.'))
        assert int(n1) == repliche_necessarie(iqr, n_istanze=1), \
            'RUNBOOK dice %s per IQR %s su x1, la formula dice %d' % (
                n1, iqr_txt, repliche_necessarie(iqr, n_istanze=1))
        assert int(n2) == repliche_necessarie(iqr, n_istanze=2)
