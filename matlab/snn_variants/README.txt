# Stati storici CONGELATI di snn_b2_fsm.m, uno per round SNN usato dallo studio di trade-off.
# Sono SNAPSHOT IMMUTABILI: non si modificano mai, quindi duplicarli non crea deriva.
# Servono a comporre le configurazioni SENZA mutare il file condiviso matlab/snn_b2_fsm.m
# (lo scambio in-place ha gia' prodotto artefatti con meta' configurazione sbagliata).
#
# file                    commit     firma attesa nel VHDL
# snn_b2_fsm_R2 .m       bb50f9f0   pCa=0 pCm=0 pCx=0
# snn_b2_fsm_R5 .m       8b4843dc   pCa=12 pCm=0 pCx=0
# snn_b2_fsm_R9 .m       c9846f40   pCa=12 pCm=12 pCx=12
