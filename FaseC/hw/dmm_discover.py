"""Sonda: che cosa emette davvero la seriale dello ZT-702S?

Non scrive un parser: ne raccoglie l'EVIDENZA. Il formato del frame dei multimetri economici
non e' documentato in modo affidabile e a volte cambia fra revisioni dello stesso modello, quindi
un parser scritto "da manuale" restituirebbe numeri PLAUSIBILI se il formato fosse diverso --
il modo di fallire piu' pericoloso che ci sia.

Uso:
    python dmm_discover.py --lista                       # quali porte esistono
    python dmm_discover.py --porta COM3 --secondi 10     # ascolta e mostra i byte

Come si legge l'uscita: si tiene il display su un valore STABILE e noto, e si cerca quel numero
dentro i byte -- in ASCII, in BCD, o come intero binario. La struttura si riconosce dai byte che
NON cambiano fra un frame e l'altro (delimitatori, unita') contro quelli che cambiano (le cifre).

Poi, tenendo il display su un SECONDO valore noto, si verifica che l'ipotesi regga: un formato
indovinato su un solo valore e' quasi sempre sbagliato.
"""
import argparse
import binascii
import sys
import time


def lista_porte():
    try:
        from serial.tools import list_ports
    except ImportError:
        print('pyserial non installato:  pip install pyserial')
        return 1
    porte = list(list_ports.comports())
    if not porte:
        print('nessuna porta seriale trovata. Lo strumento e\' collegato e acceso?')
        print('Molti multimetri usano un cavo ottico USB: la porta compare solo col cavo inserito.')
        return 1
    print('porte disponibili:')
    for p in porte:
        print('  %-10s %s  (hwid %s)' % (p.device, p.description, p.hwid))
    return 0


def ascolta(porta, baud, secondi, mostra_ascii=True):
    try:
        import serial
    except ImportError:
        print('pyserial non installato:  pip install pyserial')
        return 1
    print('ascolto %s a %d baud per %d s -- tenere il display su un valore STABILE e NOTO' %
          (porta, baud, secondi))
    print('(se non esce nulla, provare altri baud: 2400, 4800, 9600, 19200, 115200)')
    print()
    try:
        ser = serial.Serial(porta, baud, timeout=0.5)
    except Exception as e:
        print('apertura fallita: %s' % e)
        return 1

    t0 = time.time()
    buf = bytearray()
    n_righe = 0
    try:
        while time.time() - t0 < secondi:
            d = ser.read(64)
            if not d:
                continue
            buf.extend(d)
            while len(buf) >= 16:
                blocco, buf = bytes(buf[:16]), buf[16:]
                hx = binascii.hexlify(blocco, ' ').decode()
                if mostra_ascii:
                    txt = ''.join(chr(b) if 32 <= b < 127 else '.' for b in blocco)
                    print('  %-47s |%s|' % (hx, txt))
                else:
                    print('  %s' % hx)
                n_righe += 1
    finally:
        ser.close()

    print()
    if n_righe == 0:
        print('NESSUN BYTE ricevuto. Da controllare, in ordine: il baud, che lo strumento sia in')
        print('modalita\' di trasmissione (spesso c\'e\' un tasto RS232/SEND da attivare), e il cavo.')
        return 1
    print('%d blocchi da 16 byte ricevuti.' % n_righe)
    print()
    print('Cosa guardare adesso:')
    print('  1. la LUNGHEZZA del frame -- si riconosce dal periodo con cui si ripete un byte fisso')
    print('  2. i byte COSTANTI fra un frame e l\'altro: delimitatori, unita\', segno')
    print('  3. il valore del display dentro i byte: ASCII, BCD, o intero binario')
    print('  4. ripetere con un SECONDO valore noto: un formato indovinato su uno solo')
    print('     e\' quasi sempre sbagliato')
    return 0


def _main(argv):
    ap = argparse.ArgumentParser(description='sonda della seriale del multimetro')
    ap.add_argument('--lista', action='store_true', help='elenca le porte e esci')
    ap.add_argument('--porta', default=None)
    ap.add_argument('--baud', type=int, default=2400)
    ap.add_argument('--secondi', type=int, default=10)
    a = ap.parse_args(argv)
    if a.lista or not a.porta:
        return lista_porte()
    return ascolta(a.porta, a.baud, a.secondi)


if __name__ == '__main__':
    raise SystemExit(_main(sys.argv[1:]))
