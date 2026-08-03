function Praw = snn_traj_b2(val, norm) %#codegen
%SNN_TRAJ_B2  Forward **B2 serializzato** (snn_b2_fsm) su una traiettoria intera -> raw per control-step.
%  Gemello di `snn_traj_fixed` (che usa `snn_core`), ma col datapath **time-multiplexato**: serve a
%  confrontare la parita' FSM-vs-core sull'INTERO dataset, non su una sola sequenza.
%  Da compilare in MEX: interpretato sarebbe ~341 chiamate/control-step (inutilizzabile su 60 traiettorie).
%
%  val  : 4 x N  ingressi FISICI [s; v; dv; v_l]
%  norm : 4 x 1  costanti di normalizzazione [S V DV VL] del champion
%  Praw : N x 5  uscita LI (raw) per control-step
%
%  ⚠️ Lo stato dell'FSM e' `persistent`: per una nuova traiettoria fare `clear snn_traj_b2_mex`.
  T = snn_types('fixed', 13);
  N = size(val, 2);
  Praw = zeros(N, 5);
  for s = 1:N
    xn = cast(snn_normalize(val(:, s), norm), 'like', T.V);   % stesso xn del riferimento
    [raw, valid] = snn_b2_fsm(xn, true);                      % avvia la control-step
    g = 0;
    while ~valid && g < 2000                                  % cicla fino a valid (~341 clock)
      [raw, valid] = snn_b2_fsm(cast(zeros(4, 1), 'like', T.V), false);
      g = g + 1;
    end
    Praw(s, :) = double(raw(:)).';
  end
end
