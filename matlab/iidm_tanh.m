function th = iidm_tanh(st) %#codegen
%IIDM_TANH  [SP4-M-FSM · B2.0-2b] Stadio del tanh: th = tanh(st.dd), via LUT PIENA bit-exact.
%  Dopo lo Studio 2b (document/SP4_ACC_IIDM_FAST.md §Studio 2b): il `tanh` nativo di HDL Coder era il
%  collo combinatorio (198 livelli, 9,42 MHz standalone). `tanh_lut_full` lo MEMOIZZA (LUT 4096 su
%  [-8,8) + 2 costanti di saturazione) -> **dmax=0**, bit-identico al nativo (provato: probe_tanh_dmax
%  = 0 su 20000 control-step a livello accel), ma **8 livelli / 136 MHz standalone e 0 DSP**, ed e' piu'
%  PICCOLA del nativo (545 vs 2190 LUT). Nel controllore intero il tanh non e' piu' il collo (L2 ~10,58,
%  cappato da SNN->decode).
%
%  ⚠️ th resta sfix19_En17 (tipo nativo del tanh): NON castarlo a T.acc (En8) -> butterebbe i bit
%     frazionari prima del prodotto per bf in iidm_final (bug §2.1). La LUT emette gia' sfix19_En17.
%  Confronto delle 5 varianti (native/LUT/interp/poly/CORDIC): SP4_ACC_IIDM_FAST.md §Studio 2b.
%  `tanh_lut_full` e' inlinata nel chart da build_hdl_variants; la tabella la genera gen_tanh_lut().
  th = tanh_lut_full(st.dd);
end
