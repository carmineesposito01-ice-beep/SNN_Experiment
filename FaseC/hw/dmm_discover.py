"""Sonda: che cosa emette davvero la seriale dello ZT-702S?

Non scrive un parser: ne raccoglie l'EVIDENZA. Il formato del frame dei multimetri economici
non e' documentato in modo affidabile e a volte cambia fra revisioni dello stesso modello, quindi
un parser scritto "da manuale" restituirebbe numeri PLAUSIBILI se il formato fosse diverso --
il modo di fallire piu' pericoloso che ci sia.

COME SI COLLEGA -- dal manuale dello strumento (fonte primaria, pagina delle porte):

  USB-C   "Communicate with the computer and charge the battery through the TYPE-C data
          cable". E' il canale col PC E la ricarica.
  tonda   terminale di MASSA.
  quadra  terminale di SEGNALE, "constant output 3V/1KHZ".

⚠️ La porta quadra e' un'uscita di CALIBRAZIONE a onda quadra fissa, non una seriale
configurabile. Una versione precedente di questo file proponeva di prenderci un UART con un
adattatore USB-UART, sulla base del manuale del ZT-703S trovato in rete: NON e' sostenuto dal
manuale di questo strumento. Resta da verificare se una voce di menu (F4 -> serial port output)
ne cambi la funzione; finche' non e' vista sullo strumento, e' un'ipotesi.

⚠️ MISURATO il 2026-08-03: collegato via USB-C col cavo a disposizione, Windows non ha enumerato
NULLA -- nessuna porta COM (pyserial 3.5 presente), nessun dispositivo senza driver o in errore,
nessun evento PnP.

Quella misura dice che in QUELLA configurazione non e' comparso niente. Non dice che la USB-C non
sia un canale dati: il manuale afferma il contrario, e un'assenza di enumerazione ha diverse cause
possibili, in ordine di probabilita':

  1. cavo USB-C di sola ALIMENTAZIONE (2 fili). E' la causa piu' comune in assoluto, e si
     distingue in un secondo: lo strumento si carica ma il PC non vede nulla.
  2. modalita' di collegamento al PC da attivare sullo strumento prima che enumeri.
  3. porta USB dello strumento o del PC guasta.

Da provare in quest'ordine, con un cavo che si SA portare dati (p.es. quello di un disco esterno).

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
        print('nessuna porta seriale trovata.')
        print()
        print('Il manuale indica la USB-C come canale col PC, quindi l\'assenza va spiegata.')
        print('Da provare in quest\'ordine:')
        print('  1. un cavo USB-C che si SA portare dati (molti sono di sola alimentazione:')
        print('     e\' la causa piu\' comune, e si riconosce perche\' lo strumento si carica')
        print('     lo stesso mentre il PC non vede nulla)')
        print('  2. la modalita\' di collegamento al PC, da attivare sullo strumento')
        print('  3. la strada alternativa: UART sulla porta del generatore (F4 -> serial port')
        print('     output) con un adattatore USB-UART (CH340 / CP2102 / FT232)')
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
    print("(se non esce nulla, provare altri baud: 115200 e' quello documentato, poi 9600, "
          "19200, 38400, 2400)")
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
        print('NESSUN BYTE ricevuto. Da controllare, in ordine:')
        print("  1. l'uscita seriale e' ABILITATA sullo strumento (F4 -> serial port output)")
        print('  2. il filo e\' sulla porta del GENERATORE, non sulla USB-C')
        print('  3. il baud (115200 documentato; provare anche 9600 e 19200)')
        print('  4. massa in comune fra adattatore e strumento')
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
    ap.add_argument('--baud', type=int, default=115200,
                    help='115200 secondo il manuale ZOYI (ipotesi, non verificata '
                         'su questo esemplare)')
    ap.add_argument('--secondi', type=int, default=10)
    a = ap.parse_args(argv)
    if a.lista or not a.porta:
        return lista_porte()
    return ascolta(a.porta, a.baud, a.secondi)


if __name__ == '__main__':
    raise SystemExit(_main(sys.argv[1:]))
