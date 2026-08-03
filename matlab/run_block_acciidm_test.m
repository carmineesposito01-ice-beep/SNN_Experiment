function dmax = run_block_acciidm_test(K, trajIdx, hold)
%RUN_BLOCK_ACCIIDM_TEST  [SP2] Il blocco Donatello_ACC_IIDM riproduce la catena di riferimento?
%  Riferimento: MEX (normalize float + snn_core) -> snn_decode_lut(.,64) -> acc_iidm_open.
%  Blocco: la stessa catena dentro Simulink. Atteso: **dmax = 0** su ogni control-step.
%
%  Copre il GATING dell'IIDM (spec §5): se l'IIDM girasse a ogni clock invece che una volta per
%  control-step, il filtro OU vedrebbe Δv_l = 0 per 340 campioni su 341 -> a_l ~ 0 -> accel sbagliata
%  **in silenzio**. Che questo test lo becchi davvero non e' un'opinione: e' stato verificato
%  costruendo la variante mis-gated. Vedi document/SP2_ACC_IIDM.md §Verifiche.
  if nargin < 1 || isempty(K), K = 12; end
  if nargin < 2 || isempty(trajIdx), trajIdx = 1; end
  if nargin < 3 || isempty(hold), hold = 400; end      % QUALUNQUE valore >= latenza (~341) va bene
  here = fileparts(mfilename('fullpath'));
  ds = load(fullfile(here, 'test_dataset.mat')); tr = ds.trajectories;
  assert(trajIdx <= numel(tr), 'traiettoria %d inesistente (ne esistono %d)', trajIdx, numel(tr));
  d  = load(fullfile(here, 'champions_export.mat')); champs = d.champions;
  if iscell(champs), champs = [champs{:}]; end
  c  = champs(find(arrayfun(@(x) strcmp(char(string(x.name)), 'Donatello'), champs), 1));
  W  = champ_weights(c); Tp = numerictype(1, 21, 13);

  % Ingressi PRE-QUANTIZZATI a fixdt(1,32,20): cosi' la Data Type Conversion dell'harness e' un no-op
  % (valori gia' rappresentabili) e il riferimento vede ESATTAMENTE i numeri che vede il blocco.
  % Serve perche' l'IIDM e' sensibile all'ingresso in modo DIRETTO: la SNN no (la normalize assorbe le
  % differenze sotto 2^-20, HDL_PHASE §3.1.3), ma in accel 1 LSB si vedrebbe e dmax=0 sarebbe
  % irraggiungibile -> il test misurerebbe l'arrotondamento dell'harness, non il blocco.
  val = double(fi(double(tr{trajIdx}.val), 1, 32, 20));

  % 1) LATENZA + edge-trigger: MISURATI, non assunti. La chart SNN_ACC e' diversa da quella dei
  %    blocchi HDL-ready, quindi il suo edge-trigger va verificato per conto proprio.
  A_log = drive_acciidm(val(:,1) * ones(1,3), 700, 700);
  chg = find(abs(diff(A_log)) > 0);
  assert(~isempty(chg), 'accel non cambia mai: il blocco non produce (FSM ferma?)');
  lat = chg(1);
  assert(numel(chg) == 1, ['il blocco ri-esegue su ingresso COSTANTE (%d aggiornamenti di accel): ' ...
         'non e'' edge-triggered -> lo stato evolve troppo in fretta'], numel(chg));
  fprintf('latenza = %d clock ; ingresso costante -> 1 sola inferenza (edge-triggered OK)\n', lat);
  assert(hold >= lat, 'hold=%d < latenza=%d: il time-mux non fa in tempo', hold, lat);

  % 2) riferimento: la STESSA catena, in MATLAB. `clear` obbligatorio: acc_iidm_open ha lo stato
  %    persistente del filtro OU, che un run precedente lascerebbe sporco.
  Rmex = double(snn_traj_fixed_r16_mex(tr{trajIdx}.val, W));
  clear acc_iidm_open;
  a_ref = zeros(K,1);
  for k = 1:K
    p = double(snn_decode_lut(fi(Rmex(k,:).', Tp), 64));      % 64 = decode del campione
    % IIDM in FIXED: il blocco dal 2026-07-16 (SP3) e' fixed, quindi confrontarlo col double
    % renderebbe dmax=0 irraggiungibile. La distanza fixed-vs-double e' `run_acc_fixed_sweep`.
    a_ref(k) = double(acc_iidm_open(val(1,k), val(2,k), val(3,k), val(4,k), p, k == 1, acc_types('fixed')));
  end

  % 3) blocco in streaming; campionamento DETERMINISTICO (non sui cambiamenti: due control-step
  %    possono dare lo stesso accel e l'indicizzazione slitterebbe -> falso mismatch)
  A_all = drive_acciidm(val(:,1:K), hold, K*hold + 20);
  idx = hold * (0:K-1).' + lat + 1;
  idx = idx(idx <= numel(A_all));
  a_blk = A_all(idx);
  n = min(numel(a_blk), K);
  assert(n == K, 'attesi %d aggiornamenti di accel, trovati %d', K, n);

  dmax = max(abs(a_blk(1:n) - a_ref(1:n)));
  fprintf('Donatello_ACC_IIDM traj=%-3d hold=%-5d su %d control-step: dmax(accel) = %.4g\n', ...
          trajIdx, hold, n, dmax);
  assert(dmax == 0, 'il blocco NON riproduce la catena di riferimento (dmax=%.4g)', dmax);
  fprintf('=== SP2 TEST PASSATO: catena bit-exact ===\n');
end


function A = drive_acciidm(seq, hold, stopT)
% pilota Donatello_ACC_IIDM con la sequenza fisica seq (4 x K), ogni colonna tenuta `hold` clock
  K = size(seq, 2);
  assignin('base', 'stim_sp2', [(0:K-1).' * hold, seq.']);
  mdl = 'sp2_mdl'; if bdIsLoaded(mdl), close_system(mdl, 0); end
  new_system(mdl); load_system(mdl);
  add_block('snn_champions_lib/Donatello_ACC_IIDM', [mdl '/DUT']);
  add_block('simulink/Sources/From Workspace', [mdl '/src'], 'VariableName', 'stim_sp2', ...
            'SampleTime', '1', 'Interpolate', 'off', 'OutputAfterFinalValue', 'Holding final value');
  add_block('simulink/Signal Routing/Demux', [mdl '/dm'], 'Outputs', '4');
  add_line(mdl, 'src/1', 'dm/1');
  for j = 1:4
    add_block('simulink/Signal Attributes/Data Type Conversion', [mdl '/c' num2str(j)], ...
              'OutDataTypeStr', 'fixdt(1,32,20)');      % >=20 bit frazionari (HDL_PHASE §3.1.3)
    add_line(mdl, ['dm/' num2str(j)], ['c' num2str(j) '/1']);
    add_line(mdl, ['c' num2str(j) '/1'], ['DUT/' num2str(j)]);
  end
  add_block('simulink/Sinks/To Workspace', [mdl '/Aw'], 'VariableName', 'Aw', 'SaveFormat', 'Array');
  add_line(mdl, 'DUT/1', 'Aw/1');
  set_param(mdl, 'Solver', 'FixedStepDiscrete', 'FixedStep', '1', ...
            'StopTime', num2str(stopT), 'SaveOutput', 'off');
  so = sim(mdl); A = double(so.get('Aw')); close_system(mdl, 0);
end
