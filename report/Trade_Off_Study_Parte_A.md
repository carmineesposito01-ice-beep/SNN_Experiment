# CF_FSNN — Studio di trade-off, Parte A: caratterizzazione FPGA dei tier Donatello

> **Caratterizzazione dei tre tier del blocco Donatello (SLOW/BAL/FAST) sul Fmax reale io-timed e sul trade-off fra risorse e potenza, come base per la selezione del candidato al Blocco B su Zynq-7020 (scheda PYNQ-Z1).**

> Livello di fedeltà: stima Vivado post-implementazione con timing d'integrazione (io-timed) — non misura su silicio.  
> Fonte dei numeri: matlab/study_tradeoff/donatello/points_phase2.tsv (18 punti, dai report Vivado util/timing/power via sweep_phase2.sh).  
> Toolchain: Vivado 2026.1 · FPGA Xilinx Zynq-7000 xc7z020-clg400-1 (scheda PYNQ-Z1).  

---


## Sommario

| Sezione |
|---|
| 1. Sommario esecutivo |
| 2. Oggetto e vincoli |
| 3. Metodo — Fase 1: verifica del blocco |
| 3.1 La firma strutturale di identità |
| 4. Metodo — Fase 2: curve a clock vincolato (io-timed) |
| 4.1 Il metro: timing d'integrazione |
| 4.2 Le varianti nascono dal vincolo di clock |
| 5. Risultati |
| 5.1 Il Fmax reale io-timed |
| 5.2 Risorse, curve area–clock e potenza |
| 5.2.1 Curva del tier SLOW (R2 · decode fused) |
| 5.2.2 Curva del tier BAL (R5 · decode p3) |
| 5.2.3 Curva del tier FAST (R9 · decode p5) |
| 5.3 Timing di tenuta e determinismo |
| 6. Tempo d'inferenza e margine |
| Riferimenti |


## 1. Sommario esecutivo

Il blocco Donatello è la rete spiking che identifica i cinque parametri del controllore car-following a partire da quattro grandezze cinematiche. Lo studio ne caratterizza tre realizzazioni — i tier **SLOW**, **BAL** e **FAST** — ottenute accoppiando tre profondità di rete (round SNN R2, R5, R9) con tre profondità di decodifica (fusa, pipeline a tre stadi, pipeline a cinque stadi). Ogni tier è sintetizzato per lo Zynq-7020 e misurato sul **Fmax reale io-timed**: la frequenza disponibile quando gli ingressi del blocco sono registrati, come avviene in ogni integrazione, così che il cammino dalle porte d'ingresso fino all'inizio dell'inferenza sia temporizzato insieme al resto.

La frequenza massima raggiungibile cresce in modo monotòno con la profondità del tier: **29.8**, **58.4** e **73.8 MHz** per SLOW, BAL e FAST. Il valore di FAST coincide con il blocco deployabile già congelato (73.6 MHz), a conferma che il metro di misura e l'RTL descrivono lo stesso oggetto. Le risorse di logica e i registri crescono anch'essi con la profondità di pipeline, mentre la potenza è dominata dalla dispersione statica del dispositivo, costante, con una quota dinamica che scala con il clock.

Il risultato che orienta la lettura è che il **Fmax è margine, non requisito**. Il tempo di inferenza di ogni tier resta fra 5.5 e 16.7 µs, cioè fra circa **5980×** e **18180×** sotto il budget di un passo di controllo (0.1 s). Nessuna soglia di frequenza vincola il progetto; le grandezze che distinguono i tre tier in modo rilevante per il deployment sono perciò l'occupazione di risorse e la potenza. Il documento riporta la caratterizzazione completa su queste grandezze, come base per la selezione del candidato al Blocco B.

> **Nota.** Convenzione dei marcatori: ● grandezza misurata o verificata bit-esatta (correttezza funzionale, latenza in clock); ○ stima Vivado post-implementazione (Fmax, risorse, potenza) con timing d'integrazione io-timed, precedente alla misura su silicio.


## 2. Oggetto e vincoli

L'oggetto è il blocco Donatello: la rete spiking di car-following con la sua decodifica, esposta come singolo blocco con **interfaccia fissa a quattro ingressi e cinque uscite**. Gli ingressi sono la distanza dal veicolo di testa, la velocità propria, la velocità relativa e la velocità del veicolo di testa; le uscite sono i cinque parametri del controllore a inseguimento intelligente (velocità desiderata, tempo di via, distanza minima, accelerazione massima e decelerazione confortevole). L'interfaccia non cambia fra i tier: cambia solo l'implementazione interna.

![Figura 2.1 — Il blocco Donatello e la sua interfaccia fissa. Le quattro grandezze cinematiche sono normalizzate in virgola fissa, elaborate dal core spiking a multiplazione temporale (macchina a stati con memoria su blocchi RAM, dieci tick interni per passo) e decodificate in cinque parametri tramite una tabella a 64 punti. Il registro sugli operandi del normalize (op_reg, architettura splitpipe) appartiene a tutti e tre i tier.](figures_blocco_a/block.png)
*Figura 2.1 — Il blocco Donatello e la sua interfaccia fissa. Le quattro grandezze cinematiche sono normalizzate in virgola fissa, elaborate dal core spiking a multiplazione temporale (macchina a stati con memoria su blocchi RAM, dieci tick interni per passo) e decodificate in cinque parametri tramite una tabella a 64 punti. Il registro sugli operandi del normalize (op_reg, architettura splitpipe) appartiene a tutti e tre i tier.*

Ogni tier è il blocco **completo e autonomo**: il VHDL è generato dal solo modello Simulink, senza cablaggi manuali, e la rete è realizzata a multiplazione temporale, riusando una sola via di calcolo con lo stato tenuto in memoria a doppia porta. I tre tier differiscono per due assi ortogonali — la profondità della rete spiking (round R2, R5, R9) e la profondità della pipeline di decodifica (fusa, tre stadi, cinque stadi) — accoppiati come SLOW = R2 con decodifica fusa, BAL = R5 con pipeline a tre stadi, FAST = R9 con pipeline a cinque stadi.

Il vincolo di deployment è la scheda PYNQ-Z1, che porta uno Zynq-7020 (xc7z020-clg400-1). Il fine dello studio non è massimizzare una singola metrica, ma **caratterizzare i tre tier** sulle grandezze rilevanti per il deployment — frequenza, risorse, potenza, timing — così che la selezione del candidato per il Blocco B, dove la rete sarà chiusa in anello con il controllore a inseguimento intelligente, poggi su dati solidi. Sullo stesso dispositivo è previsto un secondo blocco per la comunicazione veicolo-infrastruttura: la logica lasciata libera è una risorsa di progetto, e la caratterizzazione delle risorse ha perciò rilievo diretto per il seguito.


## 3. Metodo — Fase 1: verifica del blocco

Prima di caratterizzare le prestazioni va stabilito che ciascun tier sia davvero il blocco che dichiara di essere, e che calcoli i parametri corretti. La verifica agisce sull'artefatto che si sta per misurare, non su quello appena costruito, così da non lasciar passare VHDL riciclato da una configurazione precedente. Due garanzie indipendenti la compongono: la correttezza funzionale in streaming e la firma strutturale di identità.

La correttezza è la **parità bit-esatta** con il modello in virgola fissa di riferimento, verificata facendo scorrere una traiettoria reale nel blocco un campione alla volta: lo scarto massimo sui cinque parametri è nullo (dmax = 0). La macchina a stati è edge-triggered sul cambiamento d'ingresso, per cui un campione produce esattamente una inferenza, con qualunque tempo di mantenimento superiore alla latenza.


### 3.1 La firma strutturale di identità

Un blocco può passare il test funzionale pur avendo la metà sbagliata: due configurazioni diverse possono dare gli stessi parametri a valle se la differenza è combinatoria. Per questo la verifica legge nel VHDL la **firma di entrambe le metà**. La profondità della decodifica si riconosce dai registri di fase; il round della rete spiking si riconosce dagli stadi di pipeline, che nascono a round noti e ne fissano l'identità.

| Tier | Round · decode | Firma round (nel VHDL) | Verifica |  |
|---|---|---|---|---|
| SLOW | R2 · fused | pCa assente, pCm assente, pCx assente | dmax = 0 in streaming | ● |
| BAL | R5 · p3 | pCa presente, pCm assente, pCx assente | dmax = 0 in streaming | ● |
| FAST | R9 · p5 | pCa, pCm, pCx tutti presenti | dmax = 0 in streaming | ● |

Gli stadi pCa, pCm e pCx compaiono rispettivamente ai round R4, R6 e R9 della rete: la loro presenza o assenza discrimina R2, R5 e R9 senza ambiguità. La firma della decodifica e quella della rete, lette insieme sull'artefatto, chiudono la porta agli scambi silenziosi di mezzo blocco.

Il cancello bit-esatto è provato anche **in negativo**, perché una verifica che non può fallire non verifica nulla. Degradando la precisione dell'ingresso sotto la soglia richiesta per la parità — da almeno venti bit frazionari (dove il blocco resta bit-esatto fino a Q?.13) a Q?.10 — la normalizzazione arrotonda diversamente, un solo bit meno significativo ribalta uno spike, lo stato diverge e i parametri a valle si scostano fino a circa **0.23** entro venti passi di controllo. La stessa prova che a piena precisione dà dmax = 0 respinge dunque il caso falso: il cancello discrimina.


## 4. Metodo — Fase 2: curve a clock vincolato (io-timed)

La seconda fase misura le prestazioni al variare del vincolo di clock imposto alla sintesi. Due scelte di metodo ne determinano la validità: come si temporizza il blocco e come nascono le sue varianti.


### 4.1 Il metro: timing d'integrazione

Il blocco si deploya con gli ingressi registrati da uno stadio a monte, quindi il cammino che parte dalle porte d'ingresso, attraversa la normalizzazione e arriva all'inizio dell'inferenza è un percorso temporizzato a tutti gli effetti. La misura lo include imponendo un ritardo di riferimento nullo su ingressi e uscite (timing d'integrazione, o io-timed): il **Fmax io-timed** è così la frequenza su cui il blocco si integra davvero. Una sintesi out-of-context che lasci le porte non temporizzate valuterebbe soltanto i percorsi fra registri interni e lascerebbe quel cammino fuori dal conto; per questo la caratterizzazione adotta il metro io-timed.

Perché il cammino d'ingresso non sia il collo di bottiglia, gli operandi del normalize sono registrati fra il clamp e la moltiplicazione (architettura splitpipe) e l'edge-trigger confronta gli operandi registrati. Lo stadio aggiunto mantiene il blocco bit-esatto e costa un solo clock di latenza. Il percorso critico che resta è la moltiplicazione a 34 bit della normalizzazione, intrinseca alla precisione richiesta e mappata su due DSP in cascata.


### 4.2 Le varianti nascono dal vincolo di clock

Le varianti di ciascun tier non sono realizzazioni RTL diverse, ma lo **stesso blocco** sintetizzato sotto vincoli di clock diversi. Il periodo di clock chiesto alla sintesi è una leva di progetto: un periodo più corto costringe lo strumento a lavorare di più sul percorso critico, e lo ottiene spendendo area — replica logica, sceglie celle più veloci, alza il Fmax a costo di più LUT; un periodo più lungo produce l'opposto, meno area alla frequenza, più bassa ma sufficiente, che il vincolo lasco richiede.

Un solo sweep del vincolo mappa così l'intero trade-off. Il periodo target percorre una griglia di multipli del ritardo io misurato al punto d'ancoraggio — x0.90, x1.00, x1.40, x2.00, x3.00 — più il periodo lasco di riferimento per il deploy (125 ns). L'etichetta **x0.90** è quindi il vincolo più stretto (il 90% del ritardo d'ancoraggio) e definisce il **tetto di Fmax**, con l'area più alta; l'etichetta **deploy** è il vincolo lasco e definisce l'**area minima**, alla frequenza operativa. I due estremi non sono realizzazioni in concorrenza: sono i due capi della stessa curva. Quale portare al silicio dipende da quanta frequenza serve, e poiché il Fmax è margine abbondante (§6) il punto operativo ragionevole è quello ad area minima — che non paga logica per una velocità non richiesta — mentre il tetto di Fmax resta la misura di quanto il blocco potrebbe correre.

> **Nota.** Come leggere le tabelle di §5.2. Ogni riga è un punto dello sweep. **Vincolo**: il periodo di clock imposto alla sintesi, come multiplo del ritardo d'ancoraggio (deploy = 125 ns). **Ritardo**: il ritardo del percorso critico io-timed raggiunto, da cui Fmax = 1/ritardo. **LUT, FF, DSP, BRAM**: le risorse occupate. **Ptot**: la potenza totale su chip (stima vectorless). **Hold int.**: il margine di tenuta interno reg-reg peggiore — positivo significa chiuso. Riproducibilità: thread di Vivado e seme fissati, VHDL byte-identico fra i punti, versione dello strumento registrata (Vivado 2026.1).


## 5. Risultati


### 5.1 Il Fmax reale io-timed

La frequenza massima raggiungibile cresce in modo monotòno con la profondità del tier, da SLOW a FAST. Che il valore di FAST (73.8 MHz) coincida con il blocco deployabile congelato (73.6 MHz) conferma che il metro e l'RTL misurano lo stesso oggetto, senza deriva fra caratterizzazione e artefatto.

![Figura 5.1 — Fmax reale io-timed per tier, ai due capi della curva del vincolo: il clock lasco di deploy (area minima) e il vincolo più stretto (tetto di Fmax). La progressione SLOW < BAL < FAST è netta a entrambi gli estremi. Fonte: points_phase2.tsv (punti x0.90 e deploy-ref).](figures_blocco_a/fmax.png)
*Figura 5.1 — Fmax reale io-timed per tier, ai due capi della curva del vincolo: il clock lasco di deploy (area minima) e il vincolo più stretto (tetto di Fmax). La progressione SLOW < BAL < FAST è netta a entrambi gli estremi. Fonte: points_phase2.tsv (punti x0.90 e deploy-ref).*


### 5.2 Risorse, curve area–clock e potenza

L'occupazione del dispositivo è modesta su tutti i tier e cresce con la profondità di pipeline. La risorsa più sollecitata sono i DSP — 52 blocchi, costanti su tutti i tier e su tutti i vincoli, pari a circa il 24% dei 220 presenti sullo Zynq-7020 — mentre LUT, registri e blocchi RAM restano in cifra singola percentuale. La tabella riporta l'occupazione completa: l'intervallo di LUT copre la curva del vincolo, gli altri tre valori non dipendono dal clock.

| Tier | LUT (min–max) | FF | DSP | BRAM |
|---|---|---|---|---|
| SLOW | 3446–3857 (6.5–7.2%) | 1998 (1.9%) | 52 (23.6%) | 1 (0.7%) |
| BAL | 3977–4217 (7.5–7.9%) | 2354 (2.2%) | 52 (23.6%) | 1 (0.7%) |
| FAST | 4625–4677 (8.7–8.8%) | 3474 (3.3%) | 52 (23.6%) | 1 (0.7%) |

Al variare del vincolo si muovono soltanto le LUT e la quota dinamica di potenza; registri, DSP e blocchi RAM sono fissati dall'RTL. La curva area–clock che ne risulta è monotòna: al crescere della frequenza richiesta cresce l'occupazione di LUT, fino al pavimento raggiunto al clock lasco. Le curve dei tre tier restano separate perché quel pavimento è fissato dalla profondità di pipeline, non dal vincolo.

![Figura 5.2 — A sinistra: LUT contro Fmax reale; ogni punto è un vincolo di clock, dal più stretto (stella, tetto di Fmax) al lasco (cerchio vuoto, area minima). A destra: potenza totale contro Fmax; la dispersione statica (linea tratteggiata) è costante, la quota dinamica cresce con il clock. Fonte: points_phase2.tsv.](figures_blocco_a/curves.png)
*Figura 5.2 — A sinistra: LUT contro Fmax reale; ogni punto è un vincolo di clock, dal più stretto (stella, tetto di Fmax) al lasco (cerchio vuoto, area minima). A destra: potenza totale contro Fmax; la dispersione statica (linea tratteggiata) è costante, la quota dinamica cresce con il clock. Fonte: points_phase2.tsv.*

La potenza segue la stessa fisica dal lato energetico. La componente statica del dispositivo è costante intorno a 104 mW e non dipende dal progetto; la componente dinamica cresce con il clock. La quota statica supera il novanta per cento del totale al clock di deploy e resta la maggioranza anche al punto più aggressivo, variando fra circa il **53%** al vincolo più stretto e circa il **95%** al clock di deploy. La stima di potenza è vectorless: l'attività di commutazione è calcolata dallo strumento anziché estratta da una simulazione della traiettoria; poiché la quota dinamica — l'unica che una stima d'attività correggerebbe — è minoritaria ai punti di deploy, il suo peso sul totale è contenuto.


#### 5.2.1 Curva del tier SLOW (R2 · decode fused)

| Vincolo | Ritardo [ns] | Fmax [MHz] | LUT | FF | DSP | BRAM | Ptot [mW] | Hold int. [ns] |
|---|---|---|---|---|---|---|---|---|
| x0.90 | 33.58 | 29.78 | 3857 | 1998 | 52 | 1 | 127 | +0.100 |
| x1.00 | 35.17 | 28.43 | 3596 | 1998 | 52 | 1 | 124 | +0.121 |
| x1.40 | 39.93 | 25.05 | 3446 | 1998 | 52 | 1 | 118 | +0.098 |
| x2.00 | 44.29 | 22.58 | 3450 | 1998 | 52 | 1 | 113 | +0.101 |
| x3.00 | 48.17 | 20.76 | 3450 | 1998 | 52 | 1 | 110 | +0.098 |
| deploy | 48.90 | 20.45 | 3446 | 1998 | 52 | 1 | 108 | +0.098 |


#### 5.2.2 Curva del tier BAL (R5 · decode p3)

| Vincolo | Ritardo [ns] | Fmax [MHz] | LUT | FF | DSP | BRAM | Ptot [mW] | Hold int. [ns] |
|---|---|---|---|---|---|---|---|---|
| x0.90 | 17.13 | 58.37 | 4217 | 2354 | 52 | 1 | 197 | +0.111 |
| x1.00 | 17.90 | 55.86 | 4028 | 2354 | 52 | 1 | 189 | +0.121 |
| x1.40 | 20.88 | 47.89 | 3979 | 2354 | 52 | 1 | 163 | +0.098 |
| x2.00 | 21.62 | 46.26 | 3977 | 2354 | 52 | 1 | 144 | +0.100 |
| x3.00 | 23.06 | 43.36 | 3980 | 2354 | 52 | 1 | 130 | +0.121 |
| deploy | 24.18 | 41.35 | 3980 | 2354 | 52 | 1 | 114 | +0.098 |


#### 5.2.3 Curva del tier FAST (R9 · decode p5)

| Vincolo | Ritardo [ns] | Fmax [MHz] | LUT | FF | DSP | BRAM | Ptot [mW] | Hold int. [ns] |
|---|---|---|---|---|---|---|---|---|
| x0.90 | 13.55 | 73.81 | 4677 | 3474 | 52 | 1 | 188 | +0.098 |
| x1.00 | 14.02 | 71.34 | 4649 | 3474 | 52 | 1 | 180 | +0.098 |
| x1.40 | 16.05 | 62.33 | 4625 | 3474 | 52 | 1 | 157 | +0.098 |
| x2.00 | 16.79 | 59.56 | 4625 | 3474 | 52 | 1 | 141 | +0.098 |
| x3.00 | 19.63 | 50.95 | 4626 | 3474 | 52 | 1 | 128 | +0.096 |
| deploy | 19.31 | 51.78 | 4628 | 3474 | 52 | 1 | 111 | +0.101 |


### 5.3 Timing di tenuta e determinismo

Il tempo di tenuta interno reg-reg è **positivo in ogni punto** (fra +0.096 e +0.121 ns): il blocco è chiuso sul fronte di tenuta. Il tempo di tenuta misurato sulle porte risulta invece negativo (circa −0.50 ns), ma è un **artefatto del modello io-timed** che azzera i ritardi di porta (set_input/output_delay a zero) sulle interfacce fisiche: il tempo di tenuta reale del blocco è quello interno reg-reg, positivo. Nel deployment le porte hanno ritardi non nulli e il margine negativo apparente scompare.

La proprietà qualitativamente più forte non è un margine ma il **determinismo**: la struttura di calcolo non ha diramazioni dipendenti dai dati, per cui il numero di cicli per inferenza è costante e il tempo di esecuzione nel caso peggiore coincide con quello nel caso migliore. Il jitter di calcolo è nullo per costruzione, un requisito hard-real-time garantito dall'architettura anziché conquistato a fatica.


## 6. Tempo d'inferenza e margine

La latenza di un'inferenza è costante e nota per ciascun tier: 342, 364 e 406 cicli per SLOW, BAL e FAST (il conteggio in clock è indipendente dal metro di frequenza; lo stadio splitpipe ne aggiunge uno). Il tempo di inferenza è la latenza divisa per la frequenza operativa, e il margine è il rapporto fra il budget di un passo di controllo e quel tempo.

![Equazione 6.1 — t_inf = tempo di inferenza (s); N_clk = cicli per inferenza (SLOW 342, BAL 364, FAST 406); f_clk = frequenza operativa (Hz); M = margine (adimensionale); t_step = budget del passo di controllo (0.1 s). Ogni simbolo è definito qui, non nell'immagine.](figures_blocco_a/eq_tinf.png)
*Equazione 6.1 — t_inf = tempo di inferenza (s); N_clk = cicli per inferenza (SLOW 342, BAL 364, FAST 406); f_clk = frequenza operativa (Hz); M = margine (adimensionale); t_step = budget del passo di controllo (0.1 s). Ogni simbolo è definito qui, non nell'immagine.*

Ai due estremi della curva — alla frequenza massima e al clock di deploy — il tempo di inferenza resta nell'ordine dei microsecondi, contro un budget di cento millisecondi. Il margine più stretto dell'intero dataset, SLOW al clock di deploy, è comunque intorno a **5980×**; il più largo, FAST alla frequenza massima, intorno a **18180×**.

| Tier | Latenza [clk] | t_inf @ max-Fmax [µs] | t_inf @ deploy [µs] | Margine @ deploy |
|---|---|---|---|---|
| SLOW | 342 | 11.49 | 16.72 | ~5980× |
| BAL | 364 | 6.24 | 8.80 | ~11359× |
| FAST | 406 | 5.50 | 7.84 | ~12755× |

![Figura 6.1 — Tempo di inferenza per tier ai due estremi della curva, contro il budget del passo di controllo (linea tratteggiata, 100 ms; scala logaritmica). Ogni tier è oltre tre ordini di grandezza sotto la deadline. Fonte: points_phase2.tsv e latenze in clock (RESULTS.md §12).](figures_blocco_a/tinf.png)
*Figura 6.1 — Tempo di inferenza per tier ai due estremi della curva, contro il budget del passo di controllo (linea tratteggiata, 100 ms; scala logaritmica). Ogni tier è oltre tre ordini di grandezza sotto la deadline. Fonte: points_phase2.tsv e latenze in clock (RESULTS.md §12).*

La lettura è univoca: nessuna soglia di frequenza vincola il progetto. L'Fmax è un margine abbondante, non un requisito, e ogni frazione di velocità in più è priva di valore pratico. Le grandezze su cui i tre tier si distinguono in modo rilevante per il deployment sono perciò quelle riportate in §5 — l'occupazione di risorse e la potenza — su cui questa caratterizzazione offre la base per la selezione del candidato al Blocco B.

> **Nota.** Fedeltà. Tutte le grandezze di frequenza, risorse e potenza sono stime Vivado post-implementazione con timing d'integrazione io-timed (marcatore ○), non misure su silicio: sono il metro corretto per confrontare i tier fra loro, mentre la verità di riferimento richiede la sintesi nel contenitore di sistema completo e, per la potenza, la misura sulla scheda fisica.


## Riferimenti

| Riferimento | Tema |
|---|---|
| CF_FSNN, matlab/study_tradeoff/donatello/points_phase2.tsv — dataset delle curve io-timed (18 punti). | Dati (§5-§6) |
| CF_FSNN, matlab/study_tradeoff/donatello/RESULTS.md §15 — Fmax reale io-timed e fix splitpipe. | Metodo (§4) |
| CF_FSNN, matlab/study_tradeoff/donatello/RESULTS.md §12-§13 — latenze in clock e curva area-vs-clock. | Latenza, curve (§5-§6) |
| CF_FSNN, document/HDL_PHASE.md §3.1.3-§3.1.5 — precisione di normalizzazione, edge-trigger, splitpipe. | Verifica (§3-§4) |
| CF_FSNN, matlab/study_tradeoff/common/run_block_a_matrix.sh — cancello strutturale (firma decode + round). | Verifica (§3) |
| CF_FSNN, matlab/study_tradeoff/common/sweep_phase2.sh — driver dello sweep io-timed a clock vincolato. | Riproducibilità (§4) |
| AMD/Xilinx. Vivado Design Suite 2026.1; Zynq-7000 SoC Data Sheet (DS187). | Toolchain e dispositivo |
| Digilent. PYNQ-Z1 Reference Manual (board xc7z020-clg400-1). | Scheda di deploy |
