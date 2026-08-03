"""Il campione deployato e i parametri veri degli scenari. Da UN posto solo.

Il campione non si sceglie: e' quello che sta nel bitstream. La catena di provenienza e'

    champions/PE_t05_gp0002/best_model.pt          il checkpoint addestrato
      -> scripts/export_champions.py               quantizza i pesi a potenze di 2 (po2)
      -> matlab/champions_export.mat               i pesi DEPLOYATI
      -> matlab/build_hdl_variants.m               costruisce il blocco Simulink
      -> snn_champions_lib/Donatello_SNN_IIDM      il blocco da cui nasce l'RTL
      -> il bitstream a 40 MHz

Il nome sta scritto in `scripts/export_champions.py:19` (CHAMPIONS['Donatello']), e questo
modulo lo rilegge DA LI' invece di ricopiarlo: se un giorno cambiasse, cambierebbe anche qui,
e non ci sarebbero due verita' in disaccordo.

⚠️ Attenzione a un tranello gia' preso: i pesi del `.pt` NON coincidono con quelli del `.mat`
(scarto fino a 0,4). Non e' un altro checkpoint -- e' la quantizzazione po2 voluta. Il motore
del plotone (EventPropStepper) applica lo stesso po2, quindi misura la rete come e' deployata.
"""
import os
import re

import numpy as np
import scipy.io as sio

from . import PROJECT, DATASET

_BLOCCO = 'Donatello'                    # il blocco che diventa il composto Donatello_SNN_IIDM
_EXPORTER = os.path.join(PROJECT, 'scripts', 'export_champions.py')

# Topologia attesa del campione deployato. Non e' documentazione: e' un cancello.
TOPOLOGIA = {'hidden': 32, 'input': 4, 'rank': 16, 'output': 5}
VARIANTE = 'eventprop_alif_full'

_ds = None
_champ = None


def champion_name():
    """Il nome della directory del campione, LETTO dall'esportatore.

    Ricopiarlo qui creerebbe un secondo posto in cui la stessa decisione vive, e prima o poi
    i due divergerebbero in silenzio.
    """
    src = open(_EXPORTER, encoding='utf-8').read()
    m = re.search(r'^\s*"%s"\s*:\s*"([^"]+)"' % _BLOCCO, src, re.M)
    if not m:
        raise RuntimeError('non trovo CHAMPIONS[%r] in %s: l\'esportatore e\' cambiato di forma '
                           'e la catena di provenienza va riverificata' % (_BLOCCO, _EXPORTER))
    return m.group(1)


def champion_path():
    return os.path.join(PROJECT, 'champions', champion_name(), 'best_model.pt')


def load_champion(device='cpu'):
    """Il ChampionHandle del campione deployato, con la topologia VERIFICATA.

    Restituisce l'handle (non il modello nudo) perche' `variant`, `topology`, `epoch` e
    `val_loss` sono provenienza da mettere nell'artefatto.
    """
    global _champ
    if _champ is None:
        import sys
        if PROJECT not in sys.path:
            sys.path.insert(0, PROJECT)
        from utils.champion_io import load_champion as _load
        h = _load(champion_path(), device=device)
        if h.variant != VARIANTE or h.topology != TOPOLOGIA:
            raise RuntimeError(
                'il campione caricato non e\' quello deployato: variante %r topologia %r, '
                'attesi %r e %r. Misurare una rete diversa da quella sul silicio produrrebbe '
                'numeri credibili e senza valore.' % (h.variant, h.topology, VARIANTE, TOPOLOGIA))
        _champ = h
    return _champ


# --------------------------------------------------------------------------------- dataset

def _dataset():
    global _ds
    if _ds is None:
        if not os.path.isfile(DATASET):
            raise FileNotFoundError('dataset assente: %s' % DATASET)
        _ds = sio.loadmat(DATASET)['trajectories']
    return _ds


def n_scenarios():
    return int(_dataset().shape[1])


def _unwrap(v):
    """Sbuccia gli array-oggetto annidati che scipy produce dagli struct MATLAB.

    Un solo posto: farlo al volo a ogni chiamata e' come si finisce per sbucciare un livello
    di troppo in un punto e uno di meno in un altro, con letture che sembrano valide.
    """
    while isinstance(v, np.ndarray) and v.dtype == object and v.size == 1:
        v = v.ravel()[0]
    return v


def _campo(i, nome):
    return _unwrap(_dataset()[0, i][nome])


def load_gt_params(i):
    """Parametri veri [v0, T, s0, a, b] dello scenario i (base 0)."""
    return np.asarray(_campo(i, 'gt_params'), dtype=np.float64).ravel()


def load_leader(i):
    """Profilo di velocita' del leader dello scenario i."""
    return np.asarray(_campo(i, 'v_leader'), dtype=np.float64).ravel()


def load_scenario(i):
    """Lo scenario completo, nella forma che serve all'anello chiuso di C2."""
    cut = np.asarray(_campo(i, 'cut_in')).ravel()
    return {'idx': i + 1,                                   # i file golden sono in base 1
            'nome': str(np.asarray(_campo(i, 'name')).ravel()[0]),
            'regime': str(np.asarray(_campo(i, 'regime')).ravel()[0]),
            's_init': float(np.asarray(_campo(i, 's_init'), dtype=np.float64).ravel()[0]),
            'v_init': float(np.asarray(_campo(i, 'v_init'), dtype=np.float64).ravel()[0]),
            'vl': load_leader(i),
            'gt_params': load_gt_params(i),
            'cut_in': (int(cut[0]), float(cut[1])) if cut.size >= 2 else None}
