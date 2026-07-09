# document/papers/ — Paper e riferimenti

Materiale bibliografico **esterno** (PDF): non è prodotto dal progetto e nessun codice dipende da
esso. Serve a chi consulta il repository per **verificare le fonti senza doverle cercare online**.
Il contenuto è di due tipi:

- **Approfondimenti tematici** — una selezione ragionata di lavori sul filone più vicino a CF_FSNN.
- **Archivio dei riferimenti citati** (`riferimenti_report/`) — le opere elencate nelle bibliografie
  dei report, raccolte e ordinate per tema.

## Approfondimenti tematici

### PIDL-CF basato su IDM/

Modelli di car-following *physics-informed* / data-driven basati su IDM — il filone teorico da cui
deriva l'approccio PINN + ACC-IIDM di CF_FSNN:

- *A hybrid stochastic car-following model based on data-driven and theory-driven methods*
- *Modelli Car-Following con Acceleratori AI*
- *Modelli Car - Spiking*

### SNN-Driven Deep Reinforcement Learning (Spiking-AC) — Multi-Step DRL/

SNN applicate al controllo veicolare e alle reti V2X (contesto di dominio):

- *An Intelligent Car-Following Model Based on Multi-Step Deep Reinforcement Learning*
- *Energy-Efficient and Intelligent ISAC in V2X Networks With Spiking Neural Networks-Driven DRL*

## Archivio dei riferimenti citati — `riferimenti_report/`

Le fonti elencate nelle bibliografie dei report ([`../../report/`](../../report/)), scaricate dove
disponibili in forma **libera e lecita** (preprint arXiv, open-access, copie ufficiali d'autore,
pagine ufficiali di editori/enti) e ordinate per tema. Le opere che non è lecito ridistribuire —
**libri** (Springer, Wiley, Cambridge), **standard a pagamento** (ISO, JEDEC) e **articoli
IEEE/APS/JASA senza versione aperta** — sono indicate con la sola **fonte ufficiale**. Delle 37
fonti, **25 sono archiviate localmente** e 12 sono solo-link.

### SNN, neuroni e apprendimento spiking — `SNN_neuroni/`

| Riferimento | Nel repo | Fonte |
|---|---|---|
| McCulloch & Pitts (1943). A logical calculus of the ideas immanent in nervous activity. | [PDF](riferimenti_report/SNN_neuroni/McCulloch_1943_calculus.pdf) | doi.org/10.1007/BF02478259 |
| Hodgkin & Huxley (1952). A quantitative description of membrane current… | [PDF](riferimenti_report/SNN_neuroni/Hodgkin_1952_membrane.pdf) | J. Physiol. 117:500 |
| Maass (1997). Networks of spiking neurons: the third generation… | [PDF](riferimenti_report/SNN_neuroni/Maass_1997_third_generation.pdf) | Neural Networks 10(9) |
| Bi & Poo (1998). Synaptic modifications in cultured hippocampal neurons (STDP). | [PDF](riferimenti_report/SNN_neuroni/Bi_1998_STDP.pdf) | J. Neurosci. 18(24) |
| Izhikevich (2003). Simple model of spiking neurons. | [PDF](riferimenti_report/SNN_neuroni/Izhikevich_2003_simple.pdf) | IEEE TNN 14(6) |
| Brette & Gerstner (2005). Adaptive exponential integrate-and-fire model (AdEx). | [PDF](riferimenti_report/SNN_neuroni/Brette_2005_AdEx.pdf) | J. Neurophysiol. 94 |
| Gerstner, Kistler, Naud, Paninski (2014). Neuronal Dynamics. | — (libro Cambridge UP) | [neuronaldynamics.epfl.ch](https://neuronaldynamics.epfl.ch) — HTML gratuito |
| Bellec et al. (2018). LSTM and learning-to-learn in networks of spiking neurons (LSNN). | [PDF](riferimenti_report/SNN_neuroni/Bellec_2018_LSNN.pdf) | arXiv:1803.09574 |
| Neftci, Mostafa, Zenke (2019). Surrogate gradient learning in SNNs. | [PDF](riferimenti_report/SNN_neuroni/Neftci_2019_surrogate.pdf) | arXiv:1901.09948 |
| Wunderlich & Pehle (2021). Event-based backpropagation can compute exact gradients… | [PDF](riferimenti_report/SNN_neuroni/Wunderlich_2021_eventprop.pdf) | Sci. Rep. 11:12829 (open) |
| Diehl et al. (2015). Fast-classifying, high-accuracy spiking deep networks. | — (IEEE, closed) | [doi.org/10.1109/IJCNN.2015.7280696](https://doi.org/10.1109/IJCNN.2015.7280696) |
| Rueckauer et al. (2017). Conversion of continuous-valued deep networks to event-driven. | [PDF](riferimenti_report/SNN_neuroni/Rueckauer_2017_conversion.pdf) | Front. Neurosci. 11:682 (open) |

### Car-following e traffico — `car_following_traffico/`

| Riferimento | Nel repo | Fonte |
|---|---|---|
| Greenshields (1935). A study of traffic capacity. | [PDF](riferimenti_report/car_following_traffico/Greenshields_1935_traffic_capacity.pdf) | Highway Research Board 14 |
| Treiber, Hennecke, Helbing (2000). Congested traffic states… (IDM). | [PDF](riferimenti_report/car_following_traffico/Treiber_2000_IDM.pdf) | arXiv:cond-mat/0002177 |
| Kesting, Treiber, Helbing (2010). Enhanced intelligent driver model (ACC/CAH). | [PDF](riferimenti_report/car_following_traffico/Kesting_2010_enhanced_IDM.pdf) | arXiv:0912.3613 |
| Treiber & Kesting (2013). Traffic Flow Dynamics: Data, Models and Simulation. | — (libro Springer) | [doi.org/10.1007/978-3-642-32460-4](https://doi.org/10.1007/978-3-642-32460-4) |
| Hayward (1972). Near-miss determination through a scale of danger (TTC). | — (scan TRB) | [trid.trb.org/View/115323](https://trid.trb.org/View/115323) |

### Metodi, PINN e ottimizzazione — `metodi_ottimizzazione/`

| Riferimento | Nel repo | Fonte |
|---|---|---|
| Uhlenbeck & Ornstein (1930). On the theory of the Brownian motion. | — (APS, closed) | [doi.org/10.1103/PhysRev.36.823](https://doi.org/10.1103/PhysRev.36.823) |
| Werbos (1990). Backpropagation through time. | — (IEEE, closed) | [doi.org/10.1109/5.58337](https://doi.org/10.1109/5.58337) |
| Transtrum, Machta, Sethna (2011). Geometry of nonlinear least squares (sloppy models). | [PDF](riferimenti_report/metodi_ottimizzazione/Transtrum_2011_geometry.pdf) | arXiv:1010.1449 |
| Bengio, Léonard, Courville (2013). Straight-Through Estimator. | [PDF](riferimenti_report/metodi_ottimizzazione/Bengio_2013_STE.pdf) | arXiv:1308.3432 |
| Kingma & Ba (2015). Adam: a method for stochastic optimization. | [PDF](riferimenti_report/metodi_ottimizzazione/Kingma_2015_Adam.pdf) | arXiv:1412.6980 (ICLR) |
| Raissi, Perdikaris, Karniadakis (2019). Physics-informed neural networks. | [PDF](riferimenti_report/metodi_ottimizzazione/Raissi_2019_PINN.pdf) | arXiv:1711.10561 |
| Mishchenko & Defazio (2023). Prodigy: an adaptive parameter-free learner. | [PDF](riferimenti_report/metodi_ottimizzazione/Mishchenko_2023_Prodigy.pdf) | arXiv:2306.06101 |

### Hardware, FPGA ed energia — `hardware_FPGA/`

| Riferimento | Nel repo | Fonte |
|---|---|---|
| Volder (1959). The CORDIC trigonometric computing technique. | — (IEEE, closed) | [doi.org/10.1109/TEC.1959.5222693](https://doi.org/10.1109/TEC.1959.5222693) |
| Kleinrock (1975). Queueing Systems, Volume 1: Theory. | — (libro Wiley) | ISBN 9780471491101 |
| Horowitz (2014). Computing's energy problem (and what we can do about it). | [PDF](riferimenti_report/hardware_FPGA/Horowitz_2014_EnergyProblem.pdf) | doi.org/10.1109/ISSCC.2014.6757323 |
| Miyashita, Lee, Murmann (2016). CNNs using logarithmic data representation (po2). | [PDF](riferimenti_report/hardware_FPGA/Miyashita_2016_LogarithmicCNN.pdf) | arXiv:1603.01025 |
| Umuroglu et al. (2017). FINN: a framework for fast, scalable BNN inference. | [PDF](riferimenti_report/hardware_FPGA/Umuroglu_2017_FINN.pdf) | arXiv:1612.07119 |
| Xilinx (2018). Zynq-7000 SoC Data Sheet: Overview (DS190). | [PDF](riferimenti_report/hardware_FPGA/Xilinx_2018_Zynq7000_DS190.pdf) | AMD DS190 v1.11.1 |
| JEDEC JESD89A (2006). Measurement and reporting of soft errors. | — (registrazione) | [jedec.org/…/jesd-89a](https://www.jedec.org/standards-documents/docs/jesd-89a) |
| ISO 26262 (2018). Road vehicles — Functional safety. | — (standard a pagamento) | [iso.org/standard/68383.html](https://www.iso.org/standard/68383.html) |

### V2X, comunicazione e statistica — `V2X_statistica_norme/`

| Riferimento | Nel repo | Fonte |
|---|---|---|
| Massey (1951). The Kolmogorov-Smirnov test for goodness of fit. | — (JASA, closed) | [doi.org/10.1080/01621459.1951.10500769](https://doi.org/10.1080/01621459.1951.10500769) |
| Gilbert (1960). Capacity of a burst-noise channel. | [PDF](riferimenti_report/V2X_statistica_norme/Gilbert_1960_BurstNoiseChannel.pdf) | BSTJ 39 (Internet Archive) |
| ISO 2631-1 (1997). Mechanical vibration — whole-body vibration. | — (standard a pagamento) | [iso.org/standard/7612.html](https://www.iso.org/standard/7612.html) |
| Kaul, Yates, Gruteser (2012). Real-time status: how often should one update? (AoI) | [PDF](riferimenti_report/V2X_statistica_norme/Kaul_2012_AgeOfInformation.pdf) | IEEE INFOCOM 2012 |
| ETSI EN 302 637-2 (2019). ITS; Cooperative Awareness Basic Service (CAM). | [PDF](riferimenti_report/V2X_statistica_norme/ETSI_2019_EN302637-2_CAM.pdf) | ETSI, V1.4.1 |

> Le **bibliografie complete e verificate** che sostengono le affermazioni restano in coda a
> ciascun documento di [`../../report/`](../../report/); questo archivio ne raccoglie i PDF.
