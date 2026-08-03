# T7b · Cosim AXI — il sistema completo riproduce il blocco

> Rigenerabile: `gen_axi_golden('C:/t7bw','C:/t7ver',1:99,true)` poi
> `bash hw/run_axi_cosim.sh C:/t7bw C:/t7hdlv/rtlgen_mdl hw/snniidm_axi_lite.v hw/tb_snniidm_axi.v 99 600 <0|1>`
> Run pulita del 2026-07-31, 12:42–13:58 (76 min, 198 simulazioni).

## Esito

| Configurazione | Perimetro | Disallineamenti |
|---|---|---|
| Clock gating **OFF** (riferimento) | 99 scenari · **58 522** confronti | **0** |
| Clock gating **ON** (deployment) | 99 scenari · **58 522** confronti | **0** |

**Identico nelle due configurazioni ⇒ la gestione del clock non altera un solo bit.**
Stesso risultato ottenuto da T6b sulla SNN sola (0/300 000).

## Che cosa aggiunge rispetto a T7a

T7a provava `RTL ≡ blocco` col testbench che pilotava il DUT **direttamente**.
Qui gli ingressi passano dall'**interfaccia AXI4-Lite** che il DUT userà su FPGA: il processore scrive i
4 registri, emette il **commit sincrono**, attende il `done` prodotto dal **contatore di latenza**
(`LAT_CLK=560`, su latenza misurata **555**) e legge l'accelerazione. È il pezzo che nessun altro cancello copre.

Il perimetro **58 522** coincide esattamente con quello di `T7-EXACT` in T7a: stessi scenari, stesse lunghezze.

## Sensibilità dei cancelli — provata, non asserita

| Cancello | Prova | Esito |
|---|---|---|
| Confronto con l'accel attesa | 1 LSB (Q4.8) alterato nel golden | **1** disallineamento, al passo giusto; ripristino → **0** |
| Dominio di `axi_len` | valore fuori da `[1,600]` | `TB-FATAL`, il banco si ferma |
| Completezza degli ingressi | `.mem` mancante | `COSIM-ABORT` **prima** di compilare |

## Difetto trovato e corretto in corso d'opera

La prima run completa dava **878 disallineamenti** per configurazione, **tutti e soli** sugli scenari
**9, 18, 27** — quelli che **collidono**, e quindi con serie **troncata** (N = 307, 308, 307).
Il banco eseguiva 600 control-step fissi e oltre N leggeva memoria non inizializzata: `600−307=293`,
`600−308=292`, somma **878**. I conti tornano all'unità ⇒ il difetto era nel **banco**, non nel DUT.

Corretto leggendo il numero di passi a **runtime** da `axi_len.mem`, con controllo di dominio.

**Perché è sfuggito al pre-flight:** la verifica c'era, ma il **caso di prova non era rappresentativo** —
scenario 1 e una sua copia, entrambi `N=600` senza collisione. Lo smoke di T7a usa `[1, 4, 9]` (normale,
cut-in, **collisione**) proprio perché il terzo tronca la serie.
⇒ **Il caso di prova dev'essere rappresentativo dei casi limite NOTI, non solo veloce.**

Il difetto è stato diagnosticabile perché il runner riporta i disallineamenti **per scenario** invece di
sommarli: sul solo totale, `878/59 400` sarebbe sembrato un problema diffuso del DUT.
