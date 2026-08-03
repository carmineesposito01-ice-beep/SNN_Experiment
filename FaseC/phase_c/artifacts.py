"""Artefatti con provenienza. I numeri vivono qui, non nella chat.

`stable_view` isola cio' su cui le due facciate DEVONO coincidere. Senza questa separazione il
cancello di parita' fallirebbe sempre (l'orario differisce), verrebbe disattivato, e cosi' un
cancello smette di servire. Ma la vista stabile non deve appiattire troppo: se nascondesse anche
i dati, o il bitstream, la parita' sarebbe verde per costruzione e non direbbe piu' nulla.
"""
import datetime
import hashlib
import io
import json
import os

# Cambiano legittimamente fra una facciata e l'altra: non sono una divergenza.
VOLATILE = ('timestamp', 'frontend', 'host', 'cwd')


def file_sig(path, _chunk=1 << 20):
    """Firma del CONTENUTO di un file (tipicamente il bitstream), non del suo nome.

    Nome distinto dal parametro `bitstream_sig` di write(): omonimi, l'uno ombreggerebbe
    l'altro dentro write e sarebbe una trappola per chi legge dopo.

    Lega il numero all'esatto bitstream che l'ha prodotto: due misure identiche ottenute da
    bitstream diversi non sono lo stesso risultato, e senza questa firma non c'e' modo di
    accorgersene mesi dopo.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError('file assente: %s' % path)
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for blk in iter(lambda: f.read(_chunk), b''):
            h.update(blk)
    return h.hexdigest()


def write(path, data, frontend, bitstream_sig, **extra):
    """Scrive {data, prov}. `frontend` e `bitstream_sig` sono obbligatori di proposito:
    un artefatto senza l'uno non e' confrontabile, senza l'altro non e' tracciabile."""
    obj = {'data': data,
           'prov': dict(timestamp=datetime.datetime.now().isoformat(timespec='seconds'),
                        frontend=frontend, bitstream_sig=bitstream_sig,
                        cwd=os.getcwd(), **extra)}
    io.open(str(path), 'w', encoding='utf-8', newline='').write(
        json.dumps(obj, indent=1, ensure_ascii=False, sort_keys=True))
    return obj


def read(path):
    return json.load(io.open(str(path), encoding='utf-8'))


def stable_view(obj):
    """Tutto tranne i campi volatili: e' cio' su cui le due facciate devono coincidere.

    `bitstream_sig` NON e' volatile -- resta dentro apposta.
    """
    prov = {k: v for k, v in obj['prov'].items() if k not in VOLATILE}
    return {'data': obj['data'], 'prov': prov}
