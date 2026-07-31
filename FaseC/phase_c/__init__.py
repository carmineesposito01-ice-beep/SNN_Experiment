"""Fase C - validazione su silicio e chiusura mesoscopica.

Tre regole di collocazione, che valgono per ogni file aggiunto qui dentro:

  1. La LOGICA vive in questo pacchetto ed e' importabile. Le facciate (run_phase_c.sh,
     notebook/phase_c.ipynb) stanno fuori e non contengono logica propria -- altrimenti il
     cancello di parita' fra le due non puo' essere verde.
  2. I NUMERI vivono solo in results/. Mai nella chat, mai in una cella del notebook, mai in
     un commento. Un numero senza artefatto non e' un risultato.
  3. Un file di test per modulo, con lo stesso nome: c1_functional.py -> tests/test_c1.py.

I percorsi qui sotto sono VERIFICATI, non supposti: sono l'unico posto in cui vivono.
"""
import os

# FaseC/phase_c/__init__.py -> FaseC/
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# L'unico posto in cui atterrano gli artefatti.
RESULTS = os.path.join(ROOT, 'results')

# Radice del progetto: FaseC/ e' SORELLA di FaseB2.0/, utils/, matlab/, champions/.
# La Fase C non e' un harness della Fase B2.0: ne consuma gli artefatti.
PROJECT = os.path.dirname(ROOT)

# Golden bit-esatti prodotti da T7a (axi_stim/gold/len_<i>.mem, i = 1..99).
# Sovrascrivibile per postazione; il valore di default e' quello usato in B2.0.
T7_WORK = os.environ.get('T7_WORK', 'C:/t7bw')

# Dataset dei 99 scenari (N=600, dt=0,1 s, seme 12345). Percorso verificato: NON sta in data/.
DATASET = os.path.join(PROJECT, 'matlab', 'Quantizzation_Study', 'test_dataset_exhaustive.mat')

os.makedirs(RESULTS, exist_ok=True)
