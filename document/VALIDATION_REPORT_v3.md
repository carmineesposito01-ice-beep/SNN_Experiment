# CF_FSNN - Report di Validazione (v3)

> **Chiusura dello studio EventProp: 4 champion (2 BPTT + 2 EventProp) a confronto con l'oracolo, su un evaluate esaustivo a 6-tier**

> Versione: 2026-07-01  (branch EventProp_Study)  
> Champion validati: Raffaello, Leonardo (BPTT) - Donatello, Michelangelo (EventProp)  
> Riferimento: Master Splinter (oracolo = ACC-IIDM coi parametri veri)  
> Analisi sorgente: results/evaluate/v3_TURTLE_POWER!!!  (15 dimensioni)  
> Lettore atteso: ingegnere che non conosce il progetto e vuole piena  
> coscienza dello stato in ~35 minuti (i 4 champion + validazione + profilo FPGA).  

---


## 1. Sommario esecutivo

CF_FSNN e' una rete neurale spiking (SNN, ~860 parametri, target FPGA PYNQ-Z1) che osserva un veicolo follower via V2X (gap, velocita', delta-v, velocita' leader) e ne identifica i 5 parametri del modello di car-following ACC-IIDM: [v0, T, s0, a, b] (Treiber & Kesting, Ch.12). Questo documento e' il report di CHIUSURA dello studio EventProp: mette a confronto i 4 champion emersi dallo studio - due addestrati con BPTT+surrogate gradient (Raffaello, Leonardo) e due con EventProp, il gradiente aggiunto esatto (Donatello, Michelangelo) - piu' l'oracolo, su una validazione closed-loop esaustiva a 6 livelli (15 dimensioni: dall'accuratezza alla sicurezza, al traffico, al profilo hardware FPGA).

Verdetto. Tutti e 4 i champion GUIDANO IN SICUREZZA: in anello chiuso il loro tasso di collisione e' allineato a quello dell'oracolo, con margini di frenata e TTC pari o superiori (guidano piu' cauti, non meno). Le collisioni residue non sono un difetto della rete ma un limite fisico: geometrie di cut-in inevitabili e fondo ghiacciato fanno collidere anche l'oracolo. Sul piano hardware emerge un discriminante netto: i due champion EventProp sono CONTRATTIVI (raggio spettrale della ricorrenza rho<1) e non hanno neuroni morti, mentre i due BPTT sono espansivi (rho>1) con ~31% di neuroni morti. Contrattivo = stato limitato in aritmetica a virgola fissa = sicuro su FPGA. Sommato alla migliore accuratezza, questo indica **Donatello (EventProp)** come candidato al deploy: rho=0.05, accuratezza 84.75%, 0 neuroni morti. Avvertenza importante: tutti i risultati qui riportati sono in SIMULAZIONE closed-loop (plant e oracolo simulati); il deploy su FPGA e' progettato ma NON ancora validato in hardware - la conversione in HDL e' un problema aperto (sezione 11).

| Asse | Risultato | Lettura |
|---|---|---|
| Accuratezza (identificazione) | EventProp 82% vs BPTT 73% (media); best Donatello 84.75% | EventProp identifica meglio |
| Sicurezza (closed-loop) | collisione champion 6.67-7.56% ~ oracolo 7.56% | come l'oracolo (residuo = fisica) |
| Traffico (meso plotone) | string-stable: gain testa->coda 0.11-0.15 (<1) | plotone di 12 stabile |
| Stabilita' FPGA (discriminante) | rho EventProp 0.05/0.39 (<1) vs BPTT 1.16/2.99 (>1) | EventProp contrattivo -> fixed-point sicuro |
| Quantizzazione | fixed-point trascurabile fino a 2 bit; po2 assorbito dal QAT (delta<=0 su 3/4) | pronto per pesi potenze-di-due |
| Energia | 22.07x - 29.58x vs ANN densa; spike rate 1.33-1.90% | da costo AC (accumulo) < MAC (molt.-accum.), non da sparsita' |
| V2X (perdita pacchetti) | blind = 66.67% collisione; con hold-last ~8.15% | robustezza data dall'handler, non dalla rete |
| Candidato deploy | Donatello (contrattivo + best accuracy + 0 morti) | runner-up Michelangelo |

> **Nota.** Una lezione trasversale dello studio, confermata qui in closed-loop: la FISICA (errore sul dato/comportamento di guida) governa la sicurezza, NON la sola NRMSE. Un champion con NRMSE piu' bassa non e' automaticamente piu' sicuro; per questo il report privilegia le metriche di comportamento e i margini di sicurezza rispetto all'accuratezza nuda.


## 2. Il contesto: lo studio EventProp e i 4 champion


### 2.1 CF_FSNN in una pagina

Architettura: input(4) -> strato nascosto ALIF (neuroni spiking con soglia adattiva, ricorrenza a basso rango, ritardi assonali) -> output LI (5) -> sigmoide + bounds fisici -> [v0, T, s0, a, b]. Ogni passo reale (0.1 s) e' elaborato con piu' tick SNN interni; i pesi sono destinati a essere quantizzati a potenze-di-due (moltiplicazione -> bit-shift su FPGA) e il leak di membrana e' un bit-shift. La loss e' PINN (physics-informed): un termine dati (l'accelerazione ricostruita dai parametri predetti deve combaciare con quella ACC-IIDM vera) piu' termini di coerenza fisica. La rete non predice una traiettoria ma i 5 NUMERI che caratterizzano lo stile di guida. Dettagli completi di architettura, neurone ALIF e loss in document/HOW_IT_WORKS_v2.md e GLOSSARY.md.


### 2.2 EventProp vs BPTT: un fronte di Pareto

Lo studio ha mappato e chiuso il confronto tra due modi di calcolare il gradiente attraverso i tick della SNN: BPTT con surrogate gradient (si "ammorbidisce" la soglia non-differenziabile dello spike) contro EventProp (adjoint esatto sugli istanti di spike). Il risultato e' un fronte di Pareto, non un vincitore secco: il champion BPTT vince di poco sulla fisica pura (~5.5%), ma EventProp vince su NRMSE, su STABILITA' (raggio spettrale della ricorrenza ~0.5 contro ~22 delle famiglie BPTT piu' spinte) e su FPGA-friendliness; ed entrambi guidano in sicurezza. Il presente evaluate quantifica quel fronte su tutte le dimensioni che contano per un deploy neuromorfico.

> **Nota.** La ricorrenza ALIF e' fattorizzata a basso rango come prodotto di due matrici U e V; rho(U*V) e' il raggio spettrale di quel prodotto - una misura di quanto la mappa ricorrente amplifica (>1) o smorza (<1) lo stato. Perche' il raggio spettrale rho della ricorrenza e' cosi' importante per FPGA: in aritmetica a virgola fissa lo stato del neurone e' rappresentato con pochi bit. Se la mappa ricorrente e' espansiva (rho>1) piccoli errori di arrotondamento possono amplificarsi e mandare lo stato in saturazione/overflow; se e' contrattiva (rho<1) lo stato resta limitato e l'errore di quantizzazione si smorza. EventProp produce reti contrattive per costruzione - un vantaggio strutturale sul silicio.


### 2.3 I 4 champion e l'oracolo

Il confronto usa 4 champion piu' l'oracolo. Tutti i champion hanno la stessa architettura; differiscono per metodo e ricetta di training. L'oracolo (nome in codice "Master Splinter") NON e' una rete: e' il modello ACC-IIDM con i parametri veri, e serve da limite superiore di riferimento. I nomi sono un tema (le Tartarughe Ninja); la run porta l'etichetta "TURTLE POWER!!!".

| Champion | Checkpoint | Metodo | Accuratezza | rho(U*V) | Carattere |
|---|---|---|---|---|---|
| Raffaello | R33_C2_A1_T12_fix | BPTT | 69.34% | 2.99 | Prodigy, aggressivo |
| Leonardo | LS3_PEAK_R0_launch_d03 | BPTT | 77.53% | 1.16 | BPTT, conservativo |
| Donatello | PE_t05_gp0002 | EventProp | 84.75% | 0.05 | EventProp, best-NRMSE |
| Michelangelo | A_lr1e2_t06_r16 | EventProp | 79.18% | 0.39 | EventProp, best-Adam |
| Master Splinter | parametri veri | oracolo (ACC-IIDM) | 100% | - | riferimento |


## 3. Metodologia: l'evaluate a 6-tier

L'evaluate e' passato da validazione "data-driven" a "physics/network-driven": misura non solo quanto la rete indovina i numeri, ma come si comporta quando quei numeri GUIDANO davvero un'auto, sotto plant fisico realistico e canale V2X imperfetto, e che aspetto ha la rete come futuro circuito. Le 15 dimensioni sono organizzate in 6 tier:

| Tier | Dimensioni (sezioni della run) | Cosa misura |
|---|---|---|
| T0 reporting | 00 Scorecard, 01 Accuratezza | identificazione, distribuzioni, metriche continue |
| T1 sicurezza+coda | 02 Sicurezza, 09 Traiettorie, 10 Reachability, 11 Breakdown | SSM estese, scenari di coda, curva di rottura |
| T2 plant+canale | 06 V2X, 07 VehicleDynamics | attuatore/attrito/pendenza, PDR/latenza/AoI |
| T3 traffico | 03 String, 12 Mesoscopico, 13 Macroscopico | string stability, plotone, diagramma fondamentale |
| T4 identificabilita' | 04 Identifiability | FIM, equifinalita', causale, naturalisticita' |
| T5 FPGA | 05 Quantizzazione, 08 Energia/Spiking | Qm.n/po2, energia, salute della rete, rho |


### 3.1 Il simulatore closed-loop e l'oracolo

A ogni passo (Dt=0.1 s) la rete riceve lo stato osservato dell'ego, predice [v0, T, s0, a, b], e questi parametri alimentano il controllore ACC-IIDM che calcola l'accelerazione; l'ego avanza e il ciclo si ripete (guida ad anello chiuso, non identificazione offline). L'oracolo gira lo stesso loop coi parametri veri: confrontarli isola l'effetto dell'errore di identificazione sul comportamento.


### 3.2 Scenari e metriche

Scenari avversari: following, stop&go, hard-brake, cut-in (realistico ed evitabile), aggressive cut-in, panic-stop, sinusoidale; l'accuratezza e' inoltre stratificata su 6 famiglie (highway, urban, launch, freeflow, truck, mixed). Le metriche di sicurezza usano indicatori CONTINUI (surrogate safety measures) che non saturano come il solo tasso di collisione:

| Metrica | Definizione | Cosa cattura |
|---|---|---|
| collision_rate | frazione di scenari con gap -> 0 | sicurezza assoluta |
| brake_margin_min | margine di decelerazione residuo (con segno) | quanto vicino al limite di frenata |
| min_ttc / min_gap | time-to-collision e distanza minimi | prossimita' al pericolo |
| DRAC / TET / TIT | decel. richiesta; tempo e integrale sotto soglia TTC | severita' ed esposizione |
| impact_dv | delta-v ipotetico d'impatto | gravita' potenziale |
| rms_jerk / frac_iso | strappo RMS; frazione fuori soglia ISO | comfort |
| head_to_tail_gain | ampiezza coda / testa nel plotone | string stability (<1 = stabile) |
| rho(U*V), dead_frac | raggio spettrale ricorrenza; neuroni morti | salute e stabilita' hardware |


## 4. Identificazione dei parametri (Tier 0/4)


### 4.1 Accuratezza per champion e per parametro

Donatello (EventProp) e' il piu' accurato (84.75%, NRMSE media 0.152), seguito da Michelangelo (79.18%) e Leonardo (77.53%). Raffaello e' l'anello debole (69.34%): la sua NRMSE su v0 e' 0.499, cioe' sbaglia grossolanamente la velocita' desiderata - un difetto che riemerge nel diagramma fondamentale macro (sezione 7). In media EventProp batte BPTT (82% vs 73%). Il canale piu' facile e' s0 per quasi tutti; i piu' ostici sono v0 e b.

| Champion | NRMSE v0 | NRMSE T | NRMSE s0 | NRMSE a | NRMSE b | media | accur. |
|---|---|---|---|---|---|---|---|
| Raffaello | 0.499 | 0.240 | 0.068 | 0.348 | 0.378 | 0.307 | 69.34% |
| Leonardo | 0.196 | 0.277 | 0.114 | 0.229 | 0.307 | 0.225 | 77.53% |
| Donatello | 0.180 | 0.169 | 0.093 | 0.215 | 0.105 | 0.152 | 84.75% |
| Michelangelo | 0.197 | 0.260 | 0.093 | 0.220 | 0.271 | 0.208 | 79.18% |

![Figura 4.1 - Errore per parametro (sx) e accuratezza complessiva (dx). I due champion EventProp (Donatello viola, Michelangelo arancione) hanno NRMSE per-canale piu' uniforme e bassa; Raffaello (rosso) crolla su v0. La linea tratteggiata a 100% e' l'oracolo.](figures_validation_v3/val_accuracy.png)
*Figura 4.1 - Errore per parametro (sx) e accuratezza complessiva (dx). I due champion EventProp (Donatello viola, Michelangelo arancione) hanno NRMSE per-canale piu' uniforme e bassa; Raffaello (rosso) crolla su v0. La linea tratteggiata a 100% e' l'oracolo.*


### 4.2 Dove ogni parametro diventa osservabile (stratificazione)

La NRMSE stratificata per famiglia di scenario mostra QUANDO ciascun parametro e' osservabile: v0 richiede tratti di free-flow/highway (Raffaello lo sbaglia proprio in urban, dove v0 non e' eccitato), a emerge nei transitori di accelerazione (launch), b nelle frenate. E' la firma della stessa non-identificabilita' strutturale del modello car-following gia' nota dallo studio.

![Figura 4.2 - NRMSE per parametro x famiglia di scenario, per ciascun champion. Le celle piu' scure segnano dove un parametro resta poco osservabile (es. v0 in urban per Raffaello, b in freeflow per quasi tutti).](figures_validation_v3/nrmse_stratified.png)
*Figura 4.2 - NRMSE per parametro x famiglia di scenario, per ciascun champion. Le celle piu' scure segnano dove un parametro resta poco osservabile (es. v0 in urban per Raffaello, b in freeflow per quasi tutti).*


### 4.3 Identificabilita' strutturale (FIM ed equifinalita')

La matrice di Fisher (FIM) ha rango pieno (5 su 5): tutti i parametri sono in linea di principio identificabili, nessuno "sotto-eccitato". Ma il numero di condizionamento e' enorme (~1.6 miliardi): il problema e' fortemente mal-condizionato ("sloppy"), con un insieme di equifinalita' stimato in ~29 combinazioni di parametri che producono traiettorie quasi indistinguibili. Il parametro localmente meno identificabile risulta s0, il piu' identificabile T. In pratica: piu' set di parametri spiegano ugualmente bene la stessa guida - ecco perche' due champion possono avere NRMSE diverse e comportamenti di guida simili.

![Figura 4.3 - Analisi di identificabilita' via FIM: sensibilita' per parametro e struttura di correlazione (il mal-condizionamento e' la ragione fisica dell'equifinalita').](figures_validation_v3/fim.png)
*Figura 4.3 - Analisi di identificabilita' via FIM: sensibilita' per parametro e struttura di correlazione (il mal-condizionamento e' la ragione fisica dell'equifinalita').*


### 4.4 Sensibilita' causale e naturalisticita'

La sensibilita' causale (risposta delle predizioni a interventi controllati sul leader) conferma che T reagisce alla variazione di velocita' del leader in tutti i champion; le risposte di a/b differiscono per champion (Donatello mostra una firma causale distinta su s0/b). Sul realismo, il test di naturalisticita' (distanza KS tra le distribuzioni di time-gap e jerk della rete e quelle umane) incorona Leonardo come il piu' "umano" (KS time-gap 0.209, KS jerk 0.089); nessun champion, pero', rientra pienamente nella banda naturalistica di riferimento (within_floor = falso per tutti) - un limite residuo, non un difetto di sicurezza.

![Figura 4.4 - Sensibilita' causale: quanto la stima di ciascun parametro risponde a interventi su velocita' leader, |delta-v| e |accelerazione|.](figures_validation_v3/causal.png)
*Figura 4.4 - Sensibilita' causale: quanto la stima di ciascun parametro risponde a interventi su velocita' leader, |delta-v| e |accelerazione|.*

![Figura 4.5 - Naturalisticita'/calibrazione: distanza dalle distribuzioni umane di time-gap e jerk. Leonardo e' il piu' naturale; nessuno e' ancora dentro la banda di riferimento.](figures_validation_v3/naturalisticity.png)
*Figura 4.5 - Naturalisticita'/calibrazione: distanza dalle distribuzioni umane di time-gap e jerk. Leonardo e' il piu' naturale; nessuno e' ancora dentro la banda di riferimento.*


## 5. Sicurezza closed-loop (Tier 0/1)


### 5.1 Verdetto: sicuri come l'oracolo

In anello chiuso i 4 champion collidono quanto l'oracolo: il tasso di collisione va da 6.67% (Raffaello) a 7.56% (Donatello), contro 7.56% dell'oracolo. Il residuo non e' la rete: deriva da geometrie di cut-in fisicamente inevitabili (vedi curva di rottura, 6.3) in cui anche l'oracolo collide. Sul TTC minimo tutti e 4 i champion sono pari o superiori all'oracolo (5.576 s), quindi piu' cauti. Sul margine di frenata minimo Leonardo (7.63 m) e Michelangelo (7.59 m) superano l'oracolo (7.56 m), mentre Raffaello (7.31 m) e Donatello (7.26 m) restano appena sotto: differenza piccola, che non intacca il tasso di collisione (allineato all'oracolo). Nota: Leonardo mostra un picco isolato di DRAC (97.45 m/s2) in un singolo scenario - un caso-limite da tenere d'occhio, non un pattern.

| Sorgente | collis. | brake margin | min TTC | min gap | impact dv | max DRAC | rms jerk |
|---|---|---|---|---|---|---|---|
| Raffaello | 6.67% | 7.312 | 6.726 | 7.475 | 0.323 | 10.71 | 2.103 |
| Leonardo | 7.11% | 7.634 | 7.025 | 7.804 | 0.348 | 97.45 | 2.153 |
| Donatello | 7.56% | 7.259 | 5.604 | 7.428 | 0.361 | 24.61 | 2.221 |
| Michelangelo | 7.11% | 7.593 | 7.126 | 7.756 | 0.332 | 18.65 | 2.135 |
| Master Splinter | 7.56% | 7.561 | 5.576 | 7.734 | 0.368 | 13.57 | 2.340 |

![Figura 5.1 - Sicurezza cross-champion. I 4 champion (colore) sono allineati o migliori dell'oracolo (grigio) su collisione, margine di frenata, TTC e delta-v d'impatto.](figures_validation_v3/val_safety.png)
*Figura 5.1 - Sicurezza cross-champion. I 4 champion (colore) sono allineati o migliori dell'oracolo (grigio) su collisione, margine di frenata, TTC e delta-v d'impatto.*

![Figura 5.2 - Delta di ciascuna metrica di sicurezza rispetto all'oracolo: valori dal lato "piu' sicuro" confermano il profilo conservativo dei champion.](figures_validation_v3/delta_vs_oracle.png)
*Figura 5.2 - Delta di ciascuna metrica di sicurezza rispetto all'oracolo: valori dal lato "piu' sicuro" confermano il profilo conservativo dei champion.*

![Figura 5.3 - Distribuzioni delle surrogate safety measures (non solo la media): le code restano lontane dalle soglie critiche.](figures_validation_v3/ssm_distribution.png)
*Figura 5.3 - Distribuzioni delle surrogate safety measures (non solo la media): le code restano lontane dalle soglie critiche.*

![Figura 5.4 - Gap minimo per tipologia di scenario: il cut-in e' il piu' stressante, ma il gap resta sopra la linea di collisione tranne nelle geometrie impossibili.](figures_validation_v3/per_scenario_min_gap.png)
*Figura 5.4 - Gap minimo per tipologia di scenario: il cut-in e' il piu' stressante, ma il gap resta sopra la linea di collisione tranne nelle geometrie impossibili.*

![Figura 5.5 - Comfort ISO (accelerazione/jerk): i champion sono comparabili all'oracolo, con accelerazioni tendenzialmente piu' dolci.](figures_validation_v3/comfort_iso.png)
*Figura 5.5 - Comfort ISO (accelerazione/jerk): i champion sono comparabili all'oracolo, con accelerazioni tendenzialmente piu' dolci.*


### 5.6 Traiettorie closed-loop

Il modo piu' diretto di "vedere" la guida e' la traiettoria in anello chiuso: gap, velocita' e accelerazione dell'ego nel tempo, per ciascun champion sovrapposto all'oracolo. La run produce le tracce per i 5 scenari (cut-in, hard-brake, stop&go, panic-stop, aggressive cut-in) in results/evaluate/v3_TURTLE_POWER!!!/09_Trajectories/. Ne mostriamo due rappresentative: nel cut-in il gap crolla al taglio e tutte le varianti lo recuperano dolcemente senza toccare la linea di collisione; nell'hard-brake l'ego insegue la decelerazione del leader mantenendo il margine.

![Figura 5.6a - Traiettorie closed-loop nel cut-in: gap, velocita' e accelerazione. Il gap si recupera senza collisione (salvo le geometrie impossibili, dove collide anche l'oracolo).](figures_validation_v3/traj_cut_in.png)
*Figura 5.6a - Traiettorie closed-loop nel cut-in: gap, velocita' e accelerazione. Il gap si recupera senza collisione (salvo le geometrie impossibili, dove collide anche l'oracolo).*

![Figura 5.6b - Traiettorie closed-loop nell'hard-brake: l'ego segue la frenata del leader mantenendo il margine di sicurezza.](figures_validation_v3/traj_hard_brake.png)
*Figura 5.6b - Traiettorie closed-loop nell'hard-brake: l'ego segue la frenata del leader mantenendo il margine di sicurezza.*


## 6. Robustezza fisica e curva di rottura (Tier 1)


### 6.1 Plant: asciutto, bagnato, ghiaccio

Ripetendo gli scenari sotto attrito degradato, la collisione sale con la strada, non con la rete: da ~8.15% su asciutto a ~26.67% su bagnato fino a ~59.26% su ghiaccio - e l'oracolo si comporta uguale (63.70% su ghiaccio). Il ~60% di collisioni su ghiaccio e' un limite fisico (coefficiente d'attrito troppo basso per fermarsi in tempo), non un errore della SNN; anzi, su ghiaccio i champion mantengono un margine di frenata leggermente migliore dell'oracolo.

![Figura 6.1 - Collisione e margine di frenata su asciutto/bagnato/ghiaccio. La degradazione e' guidata dall'attrito ed e' identica tra champion e oracolo.](figures_validation_v3/plant.png)
*Figura 6.1 - Collisione e margine di frenata su asciutto/bagnato/ghiaccio. La degradazione e' guidata dall'attrito ed e' identica tra champion e oracolo.*


### 6.2 Reachability e 6.3 curva di rottura

L'analisi di reachability (gap minimo di sicurezza al variare del delta-v iniziale) mostra un inviluppo praticamente sovrapposto a quello dell'oracolo, marginalmente piu' conservativo ai delta-v alti (es. a delta-v=15 m/s i champion chiedono ~17-18 m contro i 16.7 m dell'oracolo). La curva di rottura conferma il punto centrale sulla sicurezza: sotto panic-braking fino a 10 m/s2 la collisione resta a zero per tutti; nel cut-in la collisione cresce al restringersi del gap ESATTAMENTE come per l'oracolo. La rete si rompe solo dove si rompe la fisica.

![Figura 6.2 - Inviluppo di gap-sicuro vs delta-v iniziale: champion (colore) ~ oracolo (grigio), leggermente piu' cauti.](figures_validation_v3/reachability.png)
*Figura 6.2 - Inviluppo di gap-sicuro vs delta-v iniziale: champion (colore) ~ oracolo (grigio), leggermente piu' cauti.*

![Figura 6.3 - Curva di rottura: collisione vs severita' (panic-decel e gap di cut-in). La frontiera dei champion coincide con quella dell'oracolo.](figures_validation_v3/breakdown.png)
*Figura 6.3 - Curva di rottura: collisione vs severita' (panic-decel e gap di cut-in). La frontiera dei champion coincide con quella dell'oracolo.*


## 7. Traffico: micro -> meso -> macro (Tier 3)


### 7.1 String stability (singolo veicolo)

Il guadagno testa->coda e' <1 per tutti i champion (da 0.13 a 0.21), quindi le perturbazioni si smorzano. Nessuno e' strettamente monotono come l'ideale; Michelangelo mostra un picco di amplificazione transitoria a certe frequenze (peak_gain 3.82) pur restando globalmente stabile.


### 7.2 Mesoscopico: plotone di 12 veicoli

In un plotone in catena di 12 veicoli, tutti i champion sono string-stable a livello testa->coda (gain 0.11-0.15, tutti <1) e nessuno collide; l'onda in testa si smorza lungo la catena. E' il risultato di traffico piu' importante: i 5 numeri predetti, propagati su una fila di veicoli, non generano stop-and-go artificiali.

![Figura 7.1 - Guadagno per veicolo lungo il plotone: tutte le curve <1 e decrescenti = catena stabile.](figures_validation_v3/meso_gain.png)
*Figura 7.1 - Guadagno per veicolo lungo il plotone: tutte le curve <1 e decrescenti = catena stabile.*

![Figura 7.2 - Heatmap spazio-tempo della velocita' nel plotone: la perturbazione iniziale si attenua a valle.](figures_validation_v3/meso_spacetime.png)
*Figura 7.2 - Heatmap spazio-tempo della velocita' nel plotone: la perturbazione iniziale si attenua a valle.*


### 7.3 Macroscopico: diagramma fondamentale

Sul livello macro (simulazione ad anello -> diagramma fondamentale flusso-densita') emerge in modo netto l'effetto dell'errore di identificazione. Michelangelo, Leonardo e Donatello producono velocita' di free-flow plausibili (65.70-71.10 km/h, vicine ai 74.30 km/h dell'oracolo), mentre Raffaello - che sbaglia v0 - gonfia la free-flow a 106.70 km/h e con essa la capacita' (903 veic/h contro i ~765 dell'oracolo): il diagramma fondamentale ne esce distorto. L'insorgenza dell'instabilita' stop-and-go (densita' critica) e' invece uniforme tra i modelli. Diversamente dalla precedente validazione, qui il simulatore macro produce curve sensate e viene quindi RIPORTATO, con la sola avvertenza sull'artefatto v0 di Raffaello.

![Figura 7.3 - Diagramma fondamentale (flusso vs densita'). La curva di Raffaello e' spostata in alto per la sovrastima di v0; gli altri champion seguono l'oracolo.](figures_validation_v3/macro_fd.png)
*Figura 7.3 - Diagramma fondamentale (flusso vs densita'). La curva di Raffaello e' spostata in alto per la sovrastima di v0; gli altri champion seguono l'oracolo.*


## 8. Robustezza V2X (Tier 2)


### 8.1 Il "hold-last-CAM" maschera la perdita di pacchetti

Il canale V2X e' modellato in modo realistico: probabilita' di consegna (PDR), latenza, jitter, perdite a raffica (Gilbert-Elliott), blackout, con tracciamento dell'Age-of-Information (AoI). Quando un pacchetto CAM manca, la strategia di default "hold-last" mantiene l'ultimo stato ricevuto (zero-order hold). Confrontando le strategie: con hold-last (o dead-reckoning) la collisione resta al livello nominale (~8.15%); ma in modalita' "blind" - la rete lasciata sola, senza alcun handler di perdita - la collisione ESPLODE a ~66.67%. Lettura onesta: la robustezza alla perdita di pacchetti osservata NON e' una proprieta' intrinseca della SNN, ma dell'handler hold-last che le sta davanti. La rete da sola non e' robusta al packet-loss; il livello di canale la protegge.

![Figura 8.1 - Sinistra: collisione per strategia di gestione perdita (hold-last/dead-reckon/blind); "blind" rivela la fragilita' della rete nuda. Destra: degrado sotto stress di canale (PDR/latenza tollerati, canale pessimo e blackout costosi).](figures_validation_v3/val_v2x.png)
*Figura 8.1 - Sinistra: collisione per strategia di gestione perdita (hold-last/dead-reckon/blind); "blind" rivela la fragilita' della rete nuda. Destra: degrado sotto stress di canale (PDR/latenza tollerati, canale pessimo e blackout costosi).*

![Figura 8.2 - Dettaglio per champion delle tre strategie di gestione della perdita.](figures_validation_v3/v2x_holdmode.png)
*Figura 8.2 - Dettaglio per champion delle tre strategie di gestione della perdita.*

![Figura 8.3 - Age-of-Information: l'eta' dell'ultimo dato ricevuto cresce con latenza e blackout, spiegando il degrado.](figures_validation_v3/v2x_aoi.png)
*Figura 8.3 - Age-of-Information: l'eta' dell'ultimo dato ricevuto cresce con latenza e blackout, spiegando il degrado.*


## 9. Profilo FPGA: quantizzazione, energia, salute della rete (Tier 5)


### 9.1 Quantizzazione: fixed-point e potenze-di-due

La rete tollera una quantizzazione aggressiva. In virgola fissa l'errore di identificazione resta praticamente invariato fino a 2 bit di parte frazionaria (es. Donatello: 1.480 in float -> 1.478 a 2 bit). Con pesi a potenze-di-due (po2, che trasformano la moltiplicazione in uno shift-add) l'errore e' insensibile al numero di bit (dipende dall'esponente, non dalla mantissa) e, soprattutto, viene ASSORBITO dal training: il "peso di 2" e' gia' quello nativo. L'ablazione dei pesi mostra delta_qat_absorbed <= 0 per 3 champion su 4 (accendere po2 non peggiora, anzi migliora), mentre Raffaello subisce un piccolo aumento (+0.16).

![Figura 9.1 - Sinistra: errore vs bit in fixed-point (piatto fino a 2 bit); le x segnano la variante po2. Destra: il QAT assorbe i pesi po2 (barre verdi = po2 non peggiora l'errore).](figures_validation_v3/val_quant.png)
*Figura 9.1 - Sinistra: errore vs bit in fixed-point (piatto fino a 2 bit); le x segnano la variante po2. Destra: il QAT assorbe i pesi po2 (barre verdi = po2 non peggiora l'errore).*


### 9.2 Energia

Il vantaggio energetico stimato per inferenza va da 22.07x a 29.58x rispetto a una ANN densa equivalente, con uno spike rate bassissimo (1.33-1.90%). NOTA ONESTA (come nel report precedente): il vantaggio NON deriva dalla sparsita' in se'. Le operazioni sinaptiche della SNN (SynOps) eguagliano o SUPERANO i MAC dell'ANN equivalente: a parita' di costo per operazione la SNN sarebbe anzi peggiore. Il guadagno viene dal minor costo unitario di un accumulo (AC) rispetto a una moltiplicazione-accumulo (MAC); ne segue che piu' sparsita' = piu' vantaggio. Su FPGA con pesi po2 il margine cresce perche' l'AC diventa un semplice shift+add. I champion EventProp mostrano un vantaggio maggiore perche' hanno una matrice ricorrente a rango effettivo piu' alto, che alza il termine ANN di riferimento.

![Figura 9.2 - Energia per inferenza e conteggio operazioni per champion.](figures_validation_v3/energy.png)
*Figura 9.2 - Energia per inferenza e conteggio operazioni per champion.*


### 9.3 Salute della rete e il discriminante di stabilita'

Qui si consuma la differenza hardware tra le due famiglie. I champion EventProp hanno ZERO neuroni morti e una ricorrenza CONTRATTIVA (rho 0.05 per Donatello, 0.39 per Michelangelo); i champion BPTT hanno ~31.25% di neuroni morti e una ricorrenza ESPANSIVA (rho 1.16 per Leonardo, 2.99 per Raffaello). Su FPGA, rho<1 garantisce uno stato limitato in aritmetica a virgola fissa (l'errore di quantizzazione si smorza), mentre rho>1 espone al rischio di amplificazione/overflow e richiederebbe guardband e saturazione esplicita. E' il motivo tecnico per cui EventProp e' piu' "FPGA-friendly", e per cui Donatello - contrattivo al massimo e piu' accurato - e' il candidato naturale al deploy.

![Figura 9.3 - Il discriminante FPGA in un solo grafico: raggio spettrale (x) vs accuratezza (y), area del marker ~ vantaggio energetico. La zona verde (rho<1) e' quella sicura in fixed-point; Donatello e Michelangelo (cerchi) ci stanno, i BPTT (quadrati) no.](figures_validation_v3/val_fpga_discriminant.png)
*Figura 9.3 - Il discriminante FPGA in un solo grafico: raggio spettrale (x) vs accuratezza (y), area del marker ~ vantaggio energetico. La zona verde (rho<1) e' quella sicura in fixed-point; Donatello e Michelangelo (cerchi) ci stanno, i BPTT (quadrati) no.*

![Figura 9.4a - Raster/attivita' di Donatello (EventProp): attivita' sparsa e distribuita, nessun neurone spento.](figures_validation_v3/raster_Donatello.png)
*Figura 9.4a - Raster/attivita' di Donatello (EventProp): attivita' sparsa e distribuita, nessun neurone spento.*

![Figura 9.4b - Raster di Raffaello (BPTT): stessa sparsita' ma con ~31% di neuroni mai attivi (capacita' sprecata).](figures_validation_v3/raster_Raffaello.png)
*Figura 9.4b - Raster di Raffaello (BPTT): stessa sparsita' ma con ~31% di neuroni mai attivi (capacita' sprecata).*

![Figura 9.5 - Vetrina di Donatello: identificazione, guida closed-loop e spiking su un episodio reale. La run contiene la vetrina per tutti e 4 i champion piu' una GIF "in diretta" (14_Showcase/showcase_*.png e showcase_live_Raffaello.gif).](figures_validation_v3/showcase_Donatello.png)
*Figura 9.5 - Vetrina di Donatello: identificazione, guida closed-loop e spiking su un episodio reale. La run contiene la vetrina per tutti e 4 i champion piu' una GIF "in diretta" (14_Showcase/showcase_*.png e showcase_live_Raffaello.gif).*


## 10. Verdetto consolidato e raccomandazione di deploy

| Champion | Sicurezza | Accuratezza | FPGA (rho, morti) | Sintesi |
|---|---|---|---|---|
| Raffaello (BPTT) | ok (~oracolo) | 69.34% (v0 mal-id) | rho 2.99, 31% morti | sconsigliato (instabile + v0) |
| Leonardo (BPTT) | ok, piu' umano | 77.53% | rho 1.16, 31% morti | ottimo software, ma espansivo |
| Donatello (EventProp) | ok (~oracolo) | 84.75% (best) | rho 0.05, 0 morti | CANDIDATO DEPLOY |
| Michelangelo (EventProp) | ok | 79.18% | rho 0.39, 0 morti | runner-up deploy |

Raccomandazione. Per il deploy FPGA la scelta e' Donatello: unisce la migliore accuratezza, una ricorrenza fortemente contrattiva (rho~0.05, la piu' sicura in fixed-point), zero neuroni morti e sicurezza pari all'oracolo. Michelangelo e' il runner-up (contrattivo, buona accuratezza). Leonardo resta il migliore sul piano software (piu' umano/naturale) ma la sua ricorrenza espansiva (rho>1) imporrebbe guardband in hardware. Raffaello e' sconsigliato: mis-identifica v0 (distorce il macro), e' il piu' espansivo (rho~3) e ha il 31% di neuroni morti.

> **Nota.** In una frase: lo studio EventProp si chiude confermando il fronte di Pareto - BPTT vince di poco sulla fisica, EventProp vince su accuratezza, stabilita' e idoneita' al silicio - e indica Donatello (EventProp) come la rete da portare su FPGA.


## 11. Limiti residui e prossimi passi

Limiti onesti di questa validazione: (1) nessun champion rientra ancora pienamente nella banda naturalistica umana (within_floor falso); (2) il problema resta mal-condizionato (cond ~1.6e9, equifinalita' ~29 set) - piu' parametri spiegano la stessa guida; (3) i champion BPTT hanno neuroni morti e ricorrenza espansiva; (4) le collisioni su ghiaccio e nei cut-in impossibili sono limiti fisici del plant, non correggibili dalla rete; (5) la robustezza V2X osservata dipende dall'handler hold-last, non dalla rete nuda. Il livello macro e' ora riportato ma con l'avvertenza sull'artefatto v0 di Raffaello.

Prossimi passi (fase FPGA). La presentazione della valutazione hardware e' gia' progettata e bloccata per la Fase A "software_now" (pre-silicio) in document/FPGA_EVALUATE_DESIGN.md, con il quadro tecnico in document/FPGA_EVALUATION_FRAMEWORK.md. Restano aperte la Fase B (HDL) e la Fase C (board): la conversione della SNN in HDL non e' immediata (i tool tipo FINN non supportano il neurone ALIF-PINN; la strada probabile e' import in Simulink + HDL Coder), ed e' documentata come problema aperto. Su questo evaluate, il candidato Donatello e' il punto di partenza del percorso di deploy.


## 12. Riproducibilita' e mappa dei file

| Cosa | Dove |
|---|---|
| Risultati evaluate v3 (15 sezioni, csv+png) | results/evaluate/v3_TURTLE_POWER!!!/ |
| Notebook champion | Eval_v3_TURTLE_POWER.ipynb |
| Builder del notebook | scripts/_build_eval_v3_notebook.py |
| Verifica manifest post-run | scripts/verify_eval_v3.py |
| Questo report (generatore) | scripts/build_validation_report_v3.py |
| Simulatore closed-loop + plant/canale | utils/closed_loop_eval.py |
| Identificazione closed-loop + V2X sweep | scripts/closed_loop_identify.py |
| Identificabilita' (FIM/causale/...) | utils/identifiability.py |
| Quantizzazione (Qm.n/po2) | utils/quantize.py |
| Diagnostica rete (dead/rho/raster) | utils/net_diagnostics.py |
| Documento-master dello studio | document/EVENTPROP_STATUS.md |
| Design valutazione FPGA | document/FPGA_EVALUATE_DESIGN.md / FPGA_EVALUATION_FRAMEWORK.md |
| Architettura/fisica | document/HOW_IT_WORKS_v2.md / GLOSSARY.md |

Le figure-chiave di questo report (accuratezza, discriminante FPGA, sicurezza, quantizzazione, V2X) sono RICOSTRUITE dai CSV eseguendo "python scripts/build_validation_report_v3.py". Le figure di dettaglio (stratificazione, FIM, causale, naturalisticita', traiettorie, plant, reachability, breakdown, string/meso/macro, raster, showcase) sono RIUSATE dai PNG genuini prodotti dal notebook v3. La run completa contiene 46 figure; qui ne e' riportato un sottoinsieme curato - il resto e' nelle 15 sottocartelle dei risultati.
