function P = snn_traj_champion(val, hold) %#codegen
%SNN_TRAJ_CHAMPION  Golden FEDELE al blocco Donatello_Champion: guida l'algoritmo ESATTO della chart
%  (snn_champion_algo, estratto verbatim dal blocco) clock-per-clock, tenendo gli ingressi fisici
%  `hold` clock per control-step -- ESATTAMENTE come il blocco in Simulink/HDL. Cattura i 5 param a
%  fine control-step. Per questo == blocco (stessa aritmetica, stesso pilotaggio a ingresso tenuto),
%  a differenza di snn_traj_b2 che pilota il forward con zeri durante l'inferenza.
%
%  val  : 4 x N  ingressi FISICI [s; v; dv; v_l]   (quantizzati a fixdt(1,32,20), come il blocco)
%  hold : clock per control-step (>= latenza ~341; usare lo stesso HOLD del testbench RTL)
%  P    : N x 5  params [v0 T s0 a b] per control-step
%
%  ⚠️ Stato ricorrente `persistent` dentro snn_champion_algo: `clear snn_traj_champion_mex` a inizio
%     traiettoria. Il 1o control-step va presentato dal primo clock (niente fase a ingresso 0, che
%     farebbe scattare la logica "prima inferenza" su un ingresso nullo -> stato desincronizzato).
  N = size(val, 2);
  P = zeros(N, 5);
  for k = 1:N
    sk = fi(val(1,k), 1, 32, 20); vk = fi(val(2,k), 1, 32, 20);
    dk = fi(val(3,k), 1, 32, 20); lk = fi(val(4,k), 1, 32, 20);
    v0 = fi(0,1,21,13); T = v0; s0 = v0; a = v0; b = v0;
    for cc = 1:hold
      [v0, T, s0, a, b] = snn_champion_algo(sk, vk, dk, lk);
    end
    P(k,:) = [double(v0), double(T), double(s0), double(a), double(b)];
  end
end
