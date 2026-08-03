"""L'acquisizione della corrente.

I cancelli che contano qui non riguardano il numero, ma il MODO in cui arriva: che un parser non
validato non possa essere usato, che una misura presa durante una deriva termica non passi per
buona, e che il rigioco non si trasformi in un modo di raccogliere dati.
"""
import io

import pytest

from phase_c.dmm import PromptDMM, ReplayDMM, SerialDMM, attendi_equilibrio


def _foglio(tmp_path, righe):
    p = tmp_path / 'campagna.csv'
    with io.open(str(p), 'w', encoding='utf-8', newline='') as f:
        f.write('idx,cfg,gating,tj,vccint,mA\n' + '\n'.join(righe) + '\n')
    return str(p)


# ------------------------------------------------------------------ lettura al prompt

def test_trascrive_il_numero_letto():
    d = PromptDMM(chiedi=lambda p: ' 412,3 ')          # virgola decimale: si accetta
    assert d.leggi_mA() == 412.3
    assert d.sorgente == 'manuale-prompt'


def test_l_etichetta_del_punto_arriva_all_operatore():
    """Senza, l'operatore non sa a quale configurazione sta rispondendo."""
    visti = []
    d = PromptDMM(chiedi=lambda p: (visti.append(p), '1.0')[1])
    d.leggi_mA(etichetta='x1/gating=off')
    assert 'x1/gating=off' in visti[0]


def test_un_valore_vuoto_o_non_numerico_RICHIEDE_di_nuovo_invece_di_inventare():
    risposte = iter(['', 'quattrocento', '400.5'])
    d = PromptDMM(chiedi=lambda p: next(risposte))
    assert d.leggi_mA() == 400.5           # ha insistito finche' non e' arrivato un numero


# ------------------------------------------------------------------ rigioco

def test_rigioca_i_punti_nell_ordine_del_foglio(tmp_path):
    p = _foglio(tmp_path, ['0,x1,on,45.1,0.998,412.3', '1,blank,-,45.2,0.997,389.7'])
    d = ReplayDMM(p)
    assert (d.leggi_mA(), d.leggi_mA()) == (412.3, 389.7)
    assert d.sorgente == 'rigioco'


def test_una_riga_NON_compilata_e_un_errore_non_uno_zero(tmp_path):
    """Un campo vuoto letto come 0 sarebbe un punto inventato in mezzo ai misurati."""
    p = _foglio(tmp_path, ['0,x1,on,45.1,0.998,412.3', '1,blank,-,45.2,0.997,'])
    d = ReplayDMM(p)
    d.leggi_mA()
    with pytest.raises(ValueError, match='campagna non e\' completa'):
        d.leggi_mA()


def test_il_rigioco_NON_e_un_modo_di_raccogliere_dati(tmp_path):
    with pytest.raises(FileNotFoundError, match='campagna gia\' eseguita'):
        ReplayDMM(str(tmp_path / 'mai_creato.csv')).leggi_mA()


def test_chiedere_piu_punti_di_quelli_misurati_e_un_errore(tmp_path):
    d = ReplayDMM(_foglio(tmp_path, ['0,x1,on,45.1,0.998,412.3']))
    d.leggi_mA()
    with pytest.raises(IndexError):
        d.leggi_mA()


# ------------------------------------------------------------------ percorso seriale

def test_SENZA_parser_lo_strumento_NON_si_usa():
    """Il cancello piu' importante del modulo. Un parser scritto 'da manuale' su un formato non
    documentato non da' errore: da' numeri PLAUSIBILI. Meglio rifiutarsi di partire."""
    with pytest.raises(ValueError, match='parser esplicito'):
        SerialDMM('COM3', parser=None)


def test_finche_non_e_validato_lo_strumento_si_dichiara_NON_validato():
    d = SerialDMM('COM_finta', parser=lambda ser: 400.0)
    assert d.validato is False


def test_la_verifica_contro_il_display_PUO_fallire():
    """Un cancello che non si e' mai visto fallire non e' un cancello."""
    d = SerialDMM('COM_finta', parser=lambda ser: 400.0)
    d._ser = object()                       # niente porta vera: il parser ignora l'argomento
    assert d.verifica_contro_display(400.02, tolleranza=0.05)['ok']
    assert d.validato is True
    with pytest.raises(ValueError, match='non e\' quello assunto'):
        d.verifica_contro_display(412.0, tolleranza=0.05)
    assert d.validato is False              # un fallimento REVOCA la validazione


# ------------------------------------------------------------- equilibrio termico

def test_l_equilibrio_si_riconosce_quando_la_temperatura_si_ferma():
    letture = iter([45.0 + 0.3 * k for k in range(6)] + [46.5] * 20)
    r = attendi_equilibrio(lambda: next(letture), band_c=0.5, n=12, intervallo_s=0,
                           max_attesa_s=30)
    assert r['ok'] and r['escursione_c'] <= 0.5


def test_una_DERIVA_non_passa_per_equilibrio():
    """E' il caso che conta: misurare durante una deriva attribuirebbe alla configurazione un
    effetto che e' della temperatura."""
    k = [0]

    def sale():
        k[0] += 1
        return 40.0 + 0.4 * k[0]

    with pytest.raises(TimeoutError, match='attribuirebbe alla configurazione'):
        attendi_equilibrio(sale, band_c=0.5, n=12, intervallo_s=0, max_attesa_s=0.3)


def test_il_criterio_e_una_CONDIZIONE_non_una_pausa_fissa():
    """Una pausa fissa sarebbe scelta a occhio, e sui punti lenti risulterebbe troppo corta
    proprio dove serve di piu'."""
    import inspect
    from phase_c import dmm
    assert 'max(ultimi) - min(ultimi)' in inspect.getsource(dmm.attendi_equilibrio)
