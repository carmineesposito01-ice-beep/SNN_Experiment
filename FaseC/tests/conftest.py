"""Fixture condivise: i golden bit-esatti prodotti da T7a.

Il caricamento e il formato dei file vivono in `phase_c/golden.py`, non qui: servono anche a
`cli.py` per gli stadi su scheda, e due copie darebbero due posti dove cambiare il formato --
con la copia dimenticata a leggere davvero i dati.

Qui resta solo la traduzione "golden assente -> skip", che e' l'unica cosa specifica dei test.
"""
import pytest

from phase_c.golden import Golden, GoldenAssente, load_golden as _load    # noqa: F401


def load_golden(idx):
    """Come `phase_c.golden.load_golden`, ma un file mancante SALTA il test invece di romperlo."""
    try:
        return _load(idx)
    except GoldenAssente as e:
        pytest.skip(str(e))


@pytest.fixture(scope='session')
def golden_scen1():
    return load_golden(1)


@pytest.fixture(scope='session')
def golden_pochi():
    """Tre scenari, per provare che il replay attraversa piu' di un file."""
    return [load_golden(i) for i in (1, 2, 3)]
