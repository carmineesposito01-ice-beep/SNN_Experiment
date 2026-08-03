function A = acc_sweep_kernel(val, R, recipN) %#codegen
%ACC_SWEEP_KERNEL  [SP4-L] Kernel MEXabile dello sweep: una traiettoria -> array di accel.
%  Sposta il loop `fi` interpretato -- il collo di bottiglia di run_acc_recip_sweep -- in codice
%  nativo (~100x). Stesso ruolo di snn_traj_fixed_r16_mex per la rete.
%    val    : 4 x n   ingressi fisici [s;v;dv;v_l]
%    R      : n x 5   raw della rete (da snn_traj_fixed_r16_mex, gia' veloce)
%    recipN : coder.const -- 0 = divide() (SP3, riferimento) ; >0 = reciproco-LUT a recipN punti (L).
%             Deve essere COSTANTE al codegen: la tabella di acc_recip_lut e' coder.const. Per questo
%             build_acc_sweep_mex genera un MEX separato per ogni recipN.
%  La matematica NON e' duplicata: chiama la stessa `acc_iidm_open` (single source), col decode.
  T  = acc_types('fixed', 8, recipN);
  Tp = numerictype(1, 21, 13);
  n  = size(val, 2);
  A  = zeros(n, 1);
  for k = 1:n
    p = double(snn_decode_lut(fi(R(k, :).', Tp), 64));           % 64 = decode del campione
    A(k) = double(acc_iidm_open(val(1, k), val(2, k), val(3, k), val(4, k), p, k == 1, T));
  end
end
