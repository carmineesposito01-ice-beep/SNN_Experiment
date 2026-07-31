"""Cancello di riproducibilita': il pacchetto si importa e gli artefatti hanno dove andare.

Sembra banale. Non lo e': se `phase_c` e' importabile solo dalla cwd giusta, le due facciate
(run_phase_c.sh e il notebook) divergeranno per un motivo che non c'entra niente con la Fase C,
e il cancello di parita' diventera' rumore invece che informazione.
"""
import os

import phase_c

FASEC = os.path.dirname(os.path.dirname(os.path.abspath(phase_c.__file__)))


def test_il_pacchetto_si_importa_e_dichiara_dove_e():
    assert os.path.basename(FASEC) == 'FaseC'
    assert phase_c.ROOT == FASEC


def test_fasec_e_di_primo_livello_sorella_di_faseb2():
    """La Fase C non e' un harness della Fase B2.0: ne consuma gli artefatti."""
    assert os.path.isdir(os.path.join(phase_c.PROJECT, 'FaseB2.0')), \
        'FaseC/ deve stare accanto a FaseB2.0/, non dentro'
    assert os.path.isdir(os.path.join(phase_c.PROJECT, 'utils'))


def test_results_esiste_ed_e_scrivibile():
    d = phase_c.RESULTS
    assert os.path.isdir(d)
    p = os.path.join(d, '.write_probe')
    open(p, 'w').write('x')
    os.remove(p)


def test_i_golden_di_t7a_sono_raggiungibili():
    """Se i golden non ci sono, meta' del piano non e' eseguibile: meglio saperlo ORA."""
    assert os.path.isfile(os.path.join(phase_c.T7_WORK, 'axi_gold_1.mem')), \
        'golden di T7a assenti in %s -- impostare la variabile T7_WORK' % phase_c.T7_WORK
