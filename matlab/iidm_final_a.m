function bl = iidm_final_a(st, th) %#codegen
%IIDM_FINAL_A  [R6] Prima meta' della fase finale: il termine CAH + il prodotto col tanh.
%  bl = a_cah + bf*th, a LARGHEZZA PIENA: e' il valore che attraversa il registro fra le due fasi, e
%  stringerlo qui cambierebbe la matematica (bug §2.1). Il tipo NON si dichiara: lo si lascia dedurre
%  dall'espressione, e la chart lo cattura inizializzando il suo stato con questa stessa funzione.
  bl = st.a_cah + st.bf * th;
end
