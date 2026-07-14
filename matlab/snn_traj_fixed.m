function Praw = snn_traj_fixed(val, W) %#codegen
%SNN_TRAJ_FIXED  Kernel COMPILABILE (codegen -> MEX): gira l'INTERA traiettoria in
%  fixed-point e ritorna le uscite RAW (LI) per step, N x 5 (double). Il decode (sigmoide,
%  nonlineare) resta FUORI, in double, nell'harness (leggero, per-step). Sposta il loop fi
%  -- il collo di bottiglia interpretato -- in codice nativo: ~100-1000x piu' veloce.
%    val : 4 x N  input fisici [s;v;dv;vl]
%    W   : struct pesi del champion (rank 8 o 16)
  T = snn_types('fixed', 13);
  N = size(val, 2);
  Praw = zeros(N, 5);
  snn_core(cast(zeros(4, 1), 'like', T.V), W, T, true);      % reset (flag logico, codegen-safe)
  for s = 1:N
    xn  = cast(snn_normalize(val(:, s), W.norm), 'like', T.V);
    raw = snn_core(xn, W, T, false);
    Praw(s, :) = double(raw(:)).';
  end
end
