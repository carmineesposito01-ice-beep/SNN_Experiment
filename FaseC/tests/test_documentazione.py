"""STATO.md deve dire quello che dicono gli artefatti.

Un documento di ripresa e' esattamente il posto dove un numero sbagliato fa piu' danno: viene
letto da chi NON ha il contesto per accorgersene, e viene creduto. E i numeri invecchiano in
silenzio -- un artefatto rigenerato non aggiorna la prosa che lo cita.

Questa e' la stessa disciplina della tabella delle repliche nel RUNBOOK, controllata in
`test_c3.py::test_la_tabella_del_RUNBOOK_viene_dal_CODICE`.

⚠️ Se uno di questi test diventa rosso, la domanda giusta e' "quale dei due ha ragione?", non
"come faccio a farlo passare". In caso di divergenza vince l'ARTEFATTO: STATO.md lo dichiara
nella sua intestazione.
"""
import io
import json
import os
import re

import pytest

FASEC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _doc(nome):
    return io.open(os.path.join(FASEC, nome), encoding='utf-8').read()


def _art(nome):
    p = os.path.join(FASEC, 'results', nome)
    if not os.path.isfile(p):
        pytest.skip('artefatto assente: %s' % nome)
    return json.load(io.open(p, encoding='utf-8'))['data']


def _num(t):
    """'8 453' -> 8453.0 ; '+0,022' -> 0.022 ; '−1,060' -> -1.06 (meno unicode incluso)."""
    t = t.replace('−', '-').replace(' ', '').replace(' ', '').replace(',', '.')
    return float(t)


# ------------------------------------------------------------------ bitstream

def test_la_tabella_dei_bitstream_dice_quello_che_dice_l_artefatto():
    d = _art('bitstream_set.json')['bitstream']
    righe = re.findall(
        r'^\| `(blank|x1|x2)` \| ([\d  ]+) \| ([\d  ]+) \| (\d+) \| (\d+) \|'
        r' \*?\*?([^|*]+?)\*?\*? \|', _doc('STATO.md'), re.M)
    assert len(righe) == 3, 'tabella dei bitstream non trovata o incompleta in STATO.md'
    for nome, lut, ff, dsp, bram, wns in righe:
        a = d[nome]
        assert _num(lut) == a['lut'], '%s: STATO dice LUT %s, artefatto %s' % (nome, lut, a['lut'])
        assert _num(ff) == a['ff'] and _num(dsp) == a['dsp'] and _num(bram) == a['bram']
        if a['wns_ns'] is not None:
            assert _num(wns.replace('ns', '')) == pytest.approx(a['wns_ns'], abs=1e-6), \
                '%s: STATO dice WNS %s, artefatto %s' % (nome, wns, a['wns_ns'])


def test_il_WNS_citato_e_quello_di_SETUP_non_quello_di_HOLD():
    """Su x1 il WNS di setup vale +0,022 e su x2 l'HOLD vale +0,022: numeri identici per
    coincidenza. Citare la riga sbagliata darebbe un bitstream 'che chiude' quando non chiude."""
    for nome in ('x1', 'x2'):
        p = os.path.join(FASEC, 'bitstream', 'timing_%s.rpt' % nome)
        if not os.path.isfile(p):
            pytest.skip('report di timing assente: %s' % p)
        testo = io.open(p, encoding='utf-8', errors='replace').read()
        m = re.search(r'^Setup\s*:\s*(\d+)\s+Failing Endpoints,\s+Worst Slack\s+(-?[\d.]+)ns',
                      testo, re.M)
        assert m, 'riga "Setup :" non trovata in timing_%s.rpt' % nome
        assert _art('bitstream_set.json')['bitstream'][nome]['wns_ns'] == pytest.approx(
            float(m.group(2)), abs=1e-6), \
            '%s: l\'artefatto non riporta lo slack di SETUP del report' % nome


def test_gli_endpoint_falliti_di_x2_vengono_dal_REPORT():
    """Il numero totale era sbagliato in tre posti (21 861 invece di 15 549), copiato da un
    report precedente. Un numero copiato non ha una fonte: ha un'origine dimenticata."""
    p = os.path.join(FASEC, 'bitstream', 'timing_x2.rpt')
    if not os.path.isfile(p):
        pytest.skip('report di timing assente')
    testo = io.open(p, encoding='utf-8', errors='replace').read()
    falliti = int(re.search(r'^Setup\s*:\s*(\d+)\s+Failing', testo, re.M).group(1))
    totale = int(re.search(r'^clk_fpga_0\s+-?[\d.]+\s+-?[\d.]+\s+(\d+)\s+(\d+)',
                           testo, re.M).group(2))
    atteso = '%d endpoint su %s' % (falliti, '{:,}'.format(totale).replace(',', ' '))
    for nome in ('STATO.md',):
        assert atteso in _doc(nome), '%s deve dire "%s"' % (nome, atteso)
    src = io.open(os.path.join(FASEC, 'phase_c', 'c3_power.py'), encoding='utf-8').read()
    assert atteso in src, 'anche il commento in c3_power.py deve dire "%s"' % atteso


# ------------------------------------------------------------------ P1

def test_la_tabella_P1_dice_quello_che_dice_l_artefatto():
    d = _art('p1.json')
    righe = re.findall(r'^\| (\d+) \| ([\d,]+) \| ([\d,]+) \| (\d+)/(\d+) \| (\d+)/(\d+) \|',
                       _doc('STATO.md'), re.M)
    assert len(righe) == 4, 'tabella P1 non trovata o incompleta in STATO.md'
    for N, med, p95, stab, su_stab, coll, su_coll in righe:
        v = d['per_N'][N]
        assert _num(med) == pytest.approx(v['head_to_tail_mediana'], abs=5e-4)
        assert _num(p95) == pytest.approx(v['head_to_tail_p95'], abs=5e-4)
        assert (int(stab), int(su_stab)) == (v['n_string_stable'], v['n_stabilita'])
        assert (int(coll), int(su_coll)) == (v['n_collisi'], v['n_sicurezza'])


def test_il_perimetro_degli_88_e_quello_dichiarato():
    d = _art('p1.json')['perimetro']
    assert (d['n_perturbati'], d['n_degeneri'], d['n_totale']) == (88, 11, 99)
    assert '88 scenari perturbati' in _doc('STATO.md')
    assert '11 `static_target`' in _doc('STATO.md')


def test_ogni_collisione_e_un_aggressive_cut_in():
    """E' la conclusione di P1 che conta di piu': collidere su un taglio aggressivo non e' un
    fallimento del controllore. Se un giorno collidesse altro, la frase in STATO.md mentirebbe."""
    d = _art('p1_collisioni_per_tipo.json')
    assert d['cut_in_applicato'] is True, 'artefatto PRE-correzione del cut_in: rigenerarlo'
    for caso in d['collisioni'].values():
        assert set(caso['tipi']) == {'aggressive_cut_in'}, \
            'STATO.md dice che ogni collisione e\' un aggressive_cut_in, l\'artefatto no'
    assert d['collisioni']['ideale']['n'] == 3
    assert d['collisioni']['latenza_3']['n'] == 10


# ------------------------------------------------------------------ P2 e quantizzazione

def test_i_conteggi_P2_citati_sono_quelli_degli_artefatti():
    e, pp = _art('p2_exact.json'), _art('p2_platoon_par.json')
    assert e['bit_esatto'] and pp['bit_esatto']
    t = _doc('STATO.md')
    for n in (pp['n_confronti_totale'], e['n_confronti']):
        assert '{:,}'.format(n).replace(',', ' ') in t, 'STATO.md non cita %d' % n


def test_la_tabella_della_quantizzazione_dice_quello_che_dice_l_artefatto():
    d = _art('p2_costo_quantizzazione.json')['scarto_di_picco_per_scenario']
    righe = re.findall(r'^\| (a|v|gap) \([^)]*\) \| ([\d,]+) \| ([\d,]+) \| ([\d,]+) \|',
                       _doc('STATO.md'), re.M)
    assert len(righe) == 3, 'tabella della quantizzazione non trovata in STATO.md'
    for campo, med, p95, mx in righe:
        s = d[campo]
        assert _num(med) == pytest.approx(s['mediana'], abs=5e-4)
        assert _num(p95) == pytest.approx(s['p95'], abs=5e-4)
        assert _num(mx) == pytest.approx(s['massimo'], abs=5e-4)


def test_le_collisioni_delle_DUE_catene_coincidono_davvero():
    """STATO.md lo riporta come verifica incrociata: se smettessero di coincidere, la frase
    diventerebbe una rassicurazione invece che una prova."""
    q = _art('p2_costo_quantizzazione.json')['collisioni']
    p1 = _art('p1.json')['per_N']['4']['n_collisi']
    assert q['p1'] == q['rtl'] == p1, \
        'quantizzazione dice %s, p1.json a N=4 dice %d' % (q, p1)


# ------------------------------------------------------------------ coerenza fra documenti

def test_STATO_non_cita_artefatti_che_non_esistono():
    """Un puntatore rotto in un documento di ripresa manda chi legge a cercare un file che non
    c'e', e la conclusione naturale e' che sia lui a sbagliare cartella."""
    citati = set(re.findall(r'`results/([\w.]+\.json)`', _doc('STATO.md')))
    assert citati, 'STATO.md non cita nessun artefatto: probabilmente il formato e\' cambiato'
    for f in sorted(citati):
        assert os.path.isfile(os.path.join(FASEC, 'results', f)), \
            'STATO.md cita results/%s, che non esiste' % f


def test_i_documenti_di_Fase_C_si_puntano_a_vicenda():
    """La ripresa deve essere possibile leggendo SOLO i documenti di Fase C: se STATO non porta
    al RUNBOOK, chi riprende non trova la procedura."""
    s = _doc('STATO.md')
    for atteso in ('RUNBOOK.md', 'README.md', 'hw/README.md'):
        assert atteso in s, 'STATO.md deve puntare a %s' % atteso
    assert 'STATO.md' in _doc('README.md'), 'README deve portare a STATO.md'


def test_il_conteggio_dei_test_in_STATO_e_quello_vero():
    """Anche questo e' un numero copiato a mano, e invecchia come gli altri. Quando questo test
    diventa rosso la correzione e' una riga in STATO.md -- il costo di tenerlo allineato e' quello,
    e vale meno del costo di un documento di ripresa che dichiara una copertura che non ha.

    (Il conteggio include questo stesso test: e' voluto, e' cio' che lo rende esatto.)
    """
    import glob
    n = sum(len(re.findall(r'^def test_', io.open(f, encoding='utf-8').read(), re.M))
            for f in glob.glob(os.path.join(FASEC, 'tests', '*.py')))
    s = _doc('STATO.md')
    m = re.search(r'\*\*(\d+) test verdi\*\*', s)
    assert m, 'STATO.md deve dichiarare il numero di test'
    assert int(m.group(1)) == n, \
        'STATO.md dice %s test, ce ne sono %d. Aggiornare STATO.md.' % (m.group(1), n)
    assert '%d test.' % n in s, 'anche la sezione "Come rilanciare tutto" deve dire %d' % n


def test_i_cancelli_di_accensione_stanno_DAVVERO_dove_STATO_dice():
    """STATO.md §1 manda al RUNBOOK §0 per i due cancelli di accensione. Ci sono stati due
    documenti d'accordo su un rimando e un terzo posto vuoto: il rimando c'era, i cancelli no.
    Un rinvio a una sezione che non contiene quello che promette e' peggio di nessun rinvio --
    chi legge conclude di aver capito male."""
    r = _doc('RUNBOOK.md')
    sezione0 = r[r.index('## 0.'):r.index('## 1.')]
    for atteso in ('verifica_plausibile', 'prova_firma_del_reset', 'done_lat', '273'):
        assert atteso in sezione0, 'RUNBOOK §0 deve nominare %s' % atteso


def test_nessun_documento_dice_ancora_che_overlay_e_DA_SCRIVERE():
    """`_overlay()` e' scritto. Un documento che lo dichiara mancante manda chi riprende a
    scrivere codice che c'e' gia' -- ed e' successo: il blocco di ripresa lo diceva ancora
    dopo che era stato implementato."""
    from phase_c import cli
    import inspect
    src = inspect.getsource(cli._overlay)
    assert 'NotImplementedError' not in src, '_overlay() non solleva piu NotImplementedError'
    for nome in ('STATO.md', 'RUNBOOK.md', 'README.md'):
        t = _doc(nome)
        assert 'NotImplementedError' not in t, \
            '%s dice ancora che _overlay() e\' da scrivere' % nome


def test_i_bitstream_citati_dal_RUNBOOK_sono_quelli_che_il_CODICE_carica():
    """Il RUNBOOK indicava i bitstream della Fase B2.0, mentre overlay_hw.py carica quelli di
    FaseC/bitstream/. Mandare l'operatore a copiare il file sbagliato blocca il bring-up al
    passo zero."""
    from phase_c import cli
    assert os.path.basename(cli.BITSTREAM) == 'bitstream'
    assert os.path.basename(os.path.dirname(cli.BITSTREAM)) == 'FaseC'
    r = _doc('RUNBOOK.md')
    sezione0 = r[r.index('## 0.'):r.index('## 1.')]
    assert 'FaseC/bitstream/' in sezione0


def test_la_sweep_di_mutazione_copre_TUTTI_i_moduli():
    """La mappa di `mutazioni.py` E' il perimetro della sweep: cio' che non e' elencato non viene
    mai mutato, e la percentuale finale sembra una copertura che non ha. E' successo -- la prima
    stesura ometteva cinque moduli su diciassette, e il riassunto diceva "66% prese" su un
    insieme scelto invece che su tutti."""
    import glob
    import importlib.util
    spec = importlib.util.spec_from_file_location('mut', os.path.join(FASEC, 'mutazioni.py'))
    M = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(M)

    moduli = {os.path.basename(f) for f in glob.glob(os.path.join(FASEC, 'phase_c', '*.py'))}
    moduli -= {'__init__.py'}
    mancanti = moduli - set(M.COPERTURA)
    assert not mancanti, 'moduli mai mutati: %s' % sorted(mancanti)

    for modulo, testfile in M.COPERTURA.items():
        assert os.path.isfile(os.path.join(FASEC, 'tests', testfile)), \
            '%s e\' mappato su %s, che non esiste' % (modulo, testfile)


def test_la_sweep_NON_campiona_di_nascosto():
    """Un tetto per modulo lascia buchi che il riassunto non distingue dalle mutazioni prese.
    Se un giorno servisse rimetterlo per costo, va dichiarato nell'uscita, non nascosto."""
    import importlib.util
    spec = importlib.util.spec_from_file_location('mut', os.path.join(FASEC, 'mutazioni.py'))
    M = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(M)
    assert M.MAX_PER_MODULO == 0, \
        'la sweep campiona %d mutazioni per modulo: il resto non viene provato' % M.MAX_PER_MODULO
