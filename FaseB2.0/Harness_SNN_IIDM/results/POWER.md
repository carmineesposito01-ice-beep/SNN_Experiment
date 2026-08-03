# T7b · Energia — misurata al duty REALE, non composta

> Rigenerabile: `bash hw/run_power.sh 40 12.5 <stadio>` (idle | active | duty | report | all);
> questa tabella: `python hw/gen_power_report.py`, che **parsa** i `power_*.rpt` in `results/`.

Flusso: SAIF da simulazione della **netlist post-place&route** (funcsim), poi `report_power` in una
sola sessione Vivado con `reset_switching_activity` fra un SAIF e il successivo.

## Copertura e configurazione — dentro il numero, non in nota

| Grandezza | Valore |
|---|---|
| Copertura SAIF (`Design Nets Matched`) | **12506 / 19951 net = 62.7 %** |
| `Confidence Level` | **High** |
| Gating | **ON** (configurazione di deployment) per attiva e duty; idle misurata in entrambi |
| Frequenza | 40 MHz (punto deployabile) |

Sul **37 %** dei net l'attivita' NON viene dal SAIF ma dal modello vectorless del tool: e' una
proprieta' della misura, e va letta insieme ai watt.

## Idle: stazionaria — provato sui TOGGLE, non solo sui watt

| Finestra | Totale [W] | Dinamica [W] | Commutazioni (TC) | **TC / clock** |
|---|---|---|---|---|
| 200 cicli | 0.114 | 0.011 | 5200 | **26.0** |
| 1000 cicli | 0.114 | 0.011 | 26000 | **26.0** |
| 5000 cicli | 0.114 | 0.011 | 130000 | **26.0** |

I watt coincidono, **ma la prova sta nella colonna dei toggle**: il rapporto TC/clock e' **identico**
sulle tre finestre (26.0), cioe' la commutazione cresce ESATTAMENTE in proporzione alla durata.
L'idle e' quindi **stazionario** e la finestra da 200 cicli basta.

La distinzione non e' pedanteria: tre valori di potenza uguali a 3 decimali potrebbero esserlo anche
per insensibilita' dello strumento. Un TC/clock costante su un fattore 25 di durata non puo'.

Il controllo verifica anche la PREMESSA — che il circuito sia davvero fermo quando non calcola: se
avesse avuto FSM o contatori attivi il rapporto non sarebbe stato costante. Non era garantito, ed e'
la condizione perche' il clock gating abbia qualcosa da spegnere.

## Clock gating: FUNZIONA — misurato nell'artefatto, invisibile nei watt

| Configurazione | Totale [W] | Dinamica [W] | TC su 200 cicli | **TC / clock** |
|---|---|---|---|---|
| idle **non** gatata (`gate_mode`=0) | 0.114 | 0.011 | 5200 | 26.0 |
| idle **gatata** (`gate_mode`=1) | 0.114 | 0.011 | **400** | **2.0** |

Il gating **riduce la commutazione di 13×** (26.0 → 2.0 toggle per clock): e' una MISURA, letta
dentro il SAIF.
Nel sommario dei watt, invece, **non si vede nulla** (0.011 W in entrambi i casi).

⚠️ Non e' una contraddizione ma un **limite dello strumento**, gia' accertato in T6b anche in negativo:
`report_power` deriva la potenza dei net di clock dal **VINCOLO di frequenza**, non dall'attivita' del
SAIF — imporre `set_switching_activity -toggle_rate 0` sui net di clock non cambiava il risultato.
Qui il finding e' **riprodotto in modo indipendente su un design diverso**.

**Conclusione onesta: il gating e' implementato e agisce; il suo guadagno in watt NON e' misurabile
con questo flusso.** Serve un flusso diverso (misura su board in Fase C, o un modello che accetti
attivita' per-net sui clock). Nessuna stima viene qui spacciata per misura.

## Fase attiva: 8 carichi REALI

Uno per combinazione **regime × cut-in** del dataset dei 99 — sono **otto**, enumerate
(18+9+18+9+12+6+18+9 = 99). Stimoli e golden sono quelli gia' validati in T7a: ogni run di potenza vale
anche come conferma funzionale.

| Carico | Combinazione | Totale [W] | Dinamica [W] | **Commutazioni (TC)** | Clocks | Logic | Signals | BRAM | DSP |
|---|---|---|---|---|---|---|---|---|---|
| wl1 | `highway / no-cut-in` | 0.129 | 0.026 | **44252587** | 0.011 | 0.006 | 0.006 | 0.002 | 0.002 |
| wl4 | `highway / cut-in` | 0.129 | 0.026 | **43954392** | 0.011 | 0.006 | 0.006 | 0.002 | 0.002 |
| wl28 | `urban / no-cut-in` | 0.129 | 0.026 | **43017937** | 0.011 | 0.006 | 0.006 | 0.002 | 0.002 |
| wl31 | `urban / cut-in` | 0.129 | 0.026 | **42973956** | 0.011 | 0.006 | 0.006 | 0.002 | 0.002 |
| wl55 | `truck / no-cut-in` | 0.129 | 0.026 | **44189478** | 0.011 | 0.006 | 0.006 | 0.002 | 0.002 |
| wl58 | `truck / cut-in` | 0.129 | 0.026 | **43916965** | 0.011 | 0.006 | 0.006 | 0.002 | 0.002 |
| wl73 | `mixed / no-cut-in` | 0.129 | 0.026 | **43492426** | 0.011 | 0.006 | 0.006 | 0.002 | 0.002 |
| wl76 | `mixed / cut-in` | 0.129 | 0.026 | **43201080** | 0.011 | 0.006 | 0.006 | 0.002 | 0.002 |

**Massimo OSSERVATO fra i carichi reali: 0.026 W** (dinamica) · minimo 0.026 W.

⚠️ **I watt sono identici a 3 decimali su tutti e 8 i carichi, ma la dispersione NON e' nulla.**
Nei SAIF la commutazione va da **42973956 a 44252587 toggle** = **2.9 %** di dispersione (massimo: wl1).
Su 0.026 W quel 2.9 % vale circa **0.0008 W**, cioe' **sotto la terza cifra** che `report_power` stampa.

Va detto cosi': *«identici nel sommario, 2.9 % di dispersione nella commutazione»*. Riportare
«dispersione nulla» sarebbe scambiare un limite di precisione per una proprieta' del circuito — ed e'
esattamente il tipo di conclusione che un numero arrotondato induce se non si guarda l'artefatto.

⚠️ E' comunque un **massimo osservato**, non un limite superiore. Il worst-case sintetico **non e' stato
prodotto**: in T6b risulto' il **piu' basso di tutti** (0,041 W contro 0,045 del massimo reale), quindi
come bound e' stato smentito su misura. Trovare il regime peggiore richiederebbe uno studio a se'.

Ogni run di potenza ha dato anche **`nMismatch = 0 / 50`**: la misura energetica vale come conferma
funzionale sullo stesso perimetro.

## Duty REALE: misurato, non composto

| Grandezza | Valore | Natura |
|---|---|---|
| Finestra attiva | **582 clock** | **misurata** dal banco (555 di latenza + 27 di protocollo AXI) |
| Control-step | 4000000 clock a 40 MHz | definizione |
| **Duty** | **0.0146 %** | derivata dalle due sopra |
| **Potenza al duty reale** | **0.114 W** totale · **0.011 W** dinamica | **MISURATA** su un control-step intero |
| Energia per control-step | **11.40 mJ** | `P × 0.1 s` |

⚠️ **Perche' misurata e non composta.** In T6b/M3.4 la composizione lineare `P_att·δ + P_idle·(1−δ)`
fu **invalidata** dal suo stesso cross-check (0,0094 W composto contro 0,015 W misurato: sottostima 1,6×),
con lo scarto localizzato sui DSP. Qui i DSP sono **69** invece di 52.

A titolo di confronto, la composizione darebbe **0.0110 W** contro i **0.0110 W** misurati.
⚠️ Attenzione a leggerci troppo: a un duty dello **0.0146 %** il valore e' dominato dall'idle per
costruzione, quindi qui il confronto **non discrimina** —
diversamente da T6b, dove il cross-check girava a duty **3,85 %** e la differenza si vedeva.
Il valore di questa misura non e' smentire la composizione: e' **non doverla usare**.

## Controllo di coerenza sulla finestra del duty (sui toggle, non sui watt)

La finestra del duty deve contenere `(3999418 clock di idle × 2.0) + (582 clock attivi × 1521)` = **8883888 toggle**;
nel SAIF ce ne sono **8747480**. Scarto **1.5 %**.

Il conto torna: la finestra SAIF del duty copre davvero **un control-step intero** — la fase attiva e'
dentro, l'idle e' della lunghezza giusta. E' un controllo che nei watt sarebbe stato **invisibile**
(a questo duty il valore e' dominato dall'idle comunque), quindi una finestra sbagliata avrebbe dato
un numero credibile.

