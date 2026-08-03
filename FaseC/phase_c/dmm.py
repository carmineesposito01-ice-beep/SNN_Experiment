"""Acquisizione della corrente: strato SOTTILE e sostituibile.

`c3_power` non deve sapere da dove viene il numero. Qui vivono le sorgenti possibili, dietro
un'interfaccia sola:

    leggi_mA()  -> float      una lettura, ADESSO
    sorgente    -> str        finisce nella provenienza dell'artefatto

⚠️ Perche' "adesso" e' in maiuscolo. Una prima versione di questo modulo prevedeva un foglio
compilato in differita, con Tj e VCCINT letti dall'XADC in una passata e la corrente trascritta
dopo. E' fisicamente sbagliato: Tj e la corrente devono descrivere lo STESSO istante termico,
altrimenti si attribuisce alla configurazione un consumo misurato a una temperatura diversa da
quella registrata -- ed e' proprio la temperatura la variabile che tutto C3 esiste per controllare.
La lettura manuale quindi avviene al PROMPT, quando il runner la chiede.

⚠️ Perche' la sorgente sta nella provenienza e NON e' un campo volatile: una misura letta a mano
e una letta dallo strumento non sono lo stesso dato. Anche col prompt resta all'operatore la
trascrizione di un display che oscilla, e la tendenza naturale e' aspettare che il numero "sembri
stabile". E' una versione sottile dello stesso bias che l'ordine sorteggiato esiste per eliminare,
e va dichiarata invece che dimenticata.
"""
import io
import os
import time


class SorgenteDMM(object):
    """Interfaccia. Chi la implementa dichiara come si ottiene il numero."""
    sorgente = 'astratta'

    def leggi_mA(self, etichetta=''):
        raise NotImplementedError


class PromptDMM(SorgenteDMM):
    """L'operatore legge il display QUANDO il runner lo chiede.

    E' il percorso che funziona sempre, ed e' il ripiego se la seriale non collabora. Il runner
    chiama `leggi_mA` subito dopo l'equilibrio termico e la lettura XADC, cosi' l'istante della
    lettura non lo sceglie l'operatore -- che deve solo trascrivere.
    """
    sorgente = 'manuale-prompt'

    def __init__(self, chiedi=None):
        # `chiedi` iniettabile: nei test si sostituisce senza toccare stdin.
        self._chiedi = chiedi or (lambda p: input(p))

    def leggi_mA(self, etichetta=''):
        while True:
            testo = self._chiedi('  corrente [mA] %s > ' % etichetta).strip()
            if not testo:
                print('  valore vuoto: serve il numero letto sul display (niente da inventare).')
                continue
            try:
                return float(testo.replace(',', '.'))
            except ValueError:
                print('  %r non e\' un numero. Trascrivere solo le cifre, senza unita\'.' % testo)


class ReplayDMM(SorgenteDMM):
    """Rigioca una campagna GIA' fatta, dal foglio che il runner ha scritto.

    Serve per ri-aggregare senza rifare le misure -- p.es. cambiando la banda termica di scarto.
    NON e' un modo di raccogliere dati: i punti devono esistere gia'.
    """
    sorgente = 'rigioco'

    def __init__(self, csv_path):
        self.csv_path = csv_path
        self._righe = None
        self._i = 0

    def _carica(self):
        if self._righe is None:
            if not os.path.isfile(self.csv_path):
                raise FileNotFoundError(
                    'foglio di campagna assente: %s. Il rigioco richiede una campagna gia\' '
                    'eseguita: non e\' un modo di raccogliere i dati.' % self.csv_path)
            righe = [r.strip().split(',') for r in io.open(self.csv_path, encoding='utf-8')
                     if r.strip() and not r.startswith('#')]
            self._righe = righe[1:]          # salta l'intestazione
        return self._righe

    def leggi_mA(self, etichetta=''):
        r = self._carica()
        if self._i >= len(r):
            raise IndexError('il foglio ha %d punti, ne e\' stato chiesto uno in piu\'' % len(r))
        val = r[self._i][-1].strip()
        self._i += 1
        if not val:
            raise ValueError('punto %d del foglio senza valore: la campagna non e\' completa, '
                             'e un campo vuoto letto come zero sarebbe un punto inventato in '
                             'mezzo ai misurati.' % (self._i - 1))
        return float(val)


class SerialDMM(SorgenteDMM):
    """Lettura dallo strumento via seriale.

    ⚠️ Il `parser` NON ha un default. Il formato del frame dello ZT-702S non e' documentato in
    modo affidabile, e scriverne uno "da manuale" darebbe numeri PLAUSIBILI se il formato fosse
    diverso -- il modo di fallire piu' pericoloso che ci sia.

    Il parser si ricava da `hw/dmm_discover.py`, che ascolta e mostra i byte grezzi, e si
    VALIDA contro il display: `verifica_contro_display()` deve passare prima di misurare.
    """
    sorgente = 'seriale'

    def __init__(self, porta, parser, baud=2400, timeout_s=2.0):
        if parser is None:
            raise ValueError(
                'SerialDMM richiede un parser esplicito. Ricavarlo con hw/dmm_discover.py e '
                'validarlo contro il display: un parser sbagliato non da\' errore, da\' numeri '
                'plausibili.')
        self.porta, self.parser, self.baud, self.timeout_s = porta, parser, baud, timeout_s
        self._ser = None
        self.validato = False               # il runner lo pretende: vedi c3_power

    def _apri(self):
        if self._ser is None:
            import serial                                    # pyserial, opzionale
            self._ser = serial.Serial(self.porta, self.baud, timeout=self.timeout_s)
        return self._ser

    def leggi_mA(self, etichetta=''):
        return float(self.parser(self._apri()))

    def verifica_contro_display(self, atteso_mA, tolleranza=0.05):
        """CANCELLO: quello che il parser legge deve coincidere con quello che si vede.

        Da eseguire PRIMA di ogni campagna, con un valore stabile sul display. Senza, non c'e'
        modo di distinguere un parser corretto da uno che restituisce un numero verosimile.
        """
        letto = self.leggi_mA()
        if abs(letto - atteso_mA) > tolleranza:
            self.validato = False
            raise ValueError(
                'il parser legge %.4f mA ma il display mostra %.4f (tolleranza %.3f). Il '
                'formato del frame non e\' quello assunto: rifare hw/dmm_discover.py.'
                % (letto, atteso_mA, tolleranza))
        self.validato = True
        return {'ok': True, 'letto_mA': letto, 'display_mA': atteso_mA}


def attendi_equilibrio(leggi_tj, band_c=0.5, n=12, intervallo_s=5.0, max_attesa_s=600.0):
    """Attende l'equilibrio termico secondo il criterio DICHIARATO IN ANTICIPO.

    Non e' una pausa fissa: e' una condizione sullo stato. Una pausa fissa sarebbe una scelta
    fatta a occhio, e sui punti lenti risulterebbe troppo corta proprio dove serve di piu'.
    Solleva se l'equilibrio non arriva: proseguire misurando durante una deriva darebbe un
    numero che verrebbe poi attribuito alla configurazione sotto test.
    """
    storia = []
    t0 = time.time()
    while time.time() - t0 < max_attesa_s:
        storia.append(float(leggi_tj()))
        if len(storia) >= n:
            ultimi = storia[-n:]
            if (max(ultimi) - min(ultimi)) <= band_c:
                return {'ok': True, 'attesa_s': round(time.time() - t0, 1),
                        'tj_finale': ultimi[-1], 'escursione_c': round(max(ultimi) - min(ultimi), 3)}
        time.sleep(intervallo_s)
    raise TimeoutError(
        'equilibrio termico non raggiunto entro %.0f s (escursione %.2f degC su %d letture, '
        'banda richiesta %.2f). Misurare durante una deriva attribuirebbe alla configurazione '
        'un effetto che e\' della temperatura.'
        % (max_attesa_s, max(storia[-n:]) - min(storia[-n:]) if len(storia) >= n else -1,
           n, band_c))
