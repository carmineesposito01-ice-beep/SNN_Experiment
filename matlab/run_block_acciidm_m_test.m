function dmax = run_block_acciidm_m_test(K, trajIdx, hold)
%RUN_BLOCK_ACCIIDM_M_TEST  [SP4-M-FSM G3+G4] Il blocco Donatello_ACC_IIDM_M (5 divisioni sequenziate su
%  UN blocco Divide HDL) riproduce il model acc_iidm_fsm E il riferimento SP3 acc_iidm_open?
%
%  G4  latenza + edge-trigger MISURATI, non assunti: M costa la SNN time-mux (~341 clk) PIU' le 5
%      divisioni sequenziali (~510 clk in totale), non ~341 come SP3 -> il vincolo di rate del blocco M
%      e' DIVERSO e va misurato. Copre anche il free-running (§3.1.4): su ingresso costante il blocco
%      deve fare UNA sola inferenza, altrimenti lo stato (filtro OU) evolve troppo in fretta, in silenzio.
%  G3  blocco reale == model (isola l'integrazione Simulink/handshake col Divide) E == SP3 (end-to-end).
%      Con G1 (Divide==divide(), 300k coppie) e G2 (model==SP3, 60000 control-step) la catena si chiude
%      per transitivita'.
%
%  Streaming: per forza su K control-step (non sul dataset intero): il blocco gira a rate di CLOCK e
%  60x1000x510 clock sarebbero ~30 M passi Simulink = ore (il muro di Donatello). La copertura sul
%  dataset intero ce l'hanno G1 e G2, che girano MEXati. Nessun campionamento silenzioso: e' dichiarato.
  if nargin < 1 || isempty(K),       K = 12;       end
  if nargin < 2 || isempty(trajIdx), trajIdx = 1;  end
  if nargin < 3 || isempty(hold),    hold = 700;   end     % >= latenza misurata (~510)
  here = fileparts(mfilename('fullpath'));
  assert(~isempty(which('fsm_step_mex')) && ~isempty(which('collect_step_mex')), ...
         'MEX mancanti: esegui build_acc_iidm_fsm_mex');
  ds = load(fullfile(here,'test_dataset.mat')); tr = ds.trajectories;
  assert(trajIdx <= numel(tr), 'traiettoria %d inesistente (ne esistono %d)', trajIdx, numel(tr));
  d  = load(fullfile(here,'champions_export.mat')); champs = d.champions;
  if iscell(champs), champs = [champs{:}]; end
  c  = champs(find(arrayfun(@(x) strcmp(char(string(x.name)),'Donatello'), champs),1));
  W  = champ_weights(c); Tp = numerictype(1,21,13);

  % Ingressi PRE-QUANTIZZATI a fixdt(1,32,20): la Data Type Conversion dell'harness diventa un no-op e il
  % riferimento vede ESATTAMENTE i numeri del blocco (in accel 1 LSB si vedrebbe -> dmax=0 sarebbe
  % irraggiungibile e il test misurerebbe l'arrotondamento dell'harness).
  val = double(fi(double(tr{trajIdx}.val), 1, 32, 20));

  % --- G4: latenza + edge-trigger MISURATI ---
  A_log = drive_acciidm_m(val(:,1)*ones(1,3), 900, 900);
  chg = find(abs(diff(A_log)) > 0);
  assert(~isempty(chg), ['accel non cambia mai: il blocco non produce -- FSM ferma o handshake col ' ...
         'blocco Divide rotto (vin/vout mai alti?)']);
  lat = chg(1);
  assert(numel(chg) == 1, ['il blocco ri-esegue su ingresso COSTANTE (%d aggiornamenti di accel): non ' ...
         'e'' edge-triggered -> lo stato evolve troppo in fretta'], numel(chg));
  fprintf('G4: latenza = %d clock ; ingresso costante -> 1 sola inferenza (edge-triggered OK)\n', lat);
  assert(hold >= lat, 'hold=%d < latenza=%d: SNN time-mux + 5 divisioni non fanno in tempo', hold, lat);

  % --- riferimenti (entrambi MEX): model FSM e SP3 ---
  Rmex = double(snn_traj_fixed_r16_mex(tr{trajIdx}.val, W));
  clear fsm_step_mex collect_step_mex;          % stato OU pulito
  a_mod = zeros(K,1); a_sp3 = zeros(K,1);
  for k = 1:K
    p = double(snn_decode_lut(fi(Rmex(k,:).', Tp), 64));
    a_mod(k) = double(fsm_step_mex(    val(1,k), val(2,k), val(3,k), val(4,k), p, k == 1));
    a_sp3(k) = double(collect_step_mex(val(1,k), val(2,k), val(3,k), val(4,k), p, k == 1));
  end

  % --- G3: blocco in streaming; campionamento DETERMINISTICO (non sui cambiamenti: due control-step
  %     possono dare lo stesso accel e l'indicizzazione slitterebbe -> falso mismatch) ---
  A_all = drive_acciidm_m(val(:,1:K), hold, K*hold + 40);
  idx = hold*(0:K-1).' + lat + 1;
  idx = idx(idx <= numel(A_all));
  a_blk = A_all(idx);
  n = min(numel(a_blk), K);
  assert(n == K, 'attesi %d aggiornamenti di accel, trovati %d', K, n);

  dmax_mod = max(abs(a_blk(1:n) - a_mod(1:n)));
  dmax_sp3 = max(abs(a_blk(1:n) - a_sp3(1:n)));
  dmax = max(dmax_mod, dmax_sp3);
  fprintf('G3 Donatello_ACC_IIDM_M traj=%-3d hold=%-5d su %d control-step: dmax vs model=%.4g | vs SP3=%.4g\n', ...
          trajIdx, hold, n, dmax_mod, dmax_sp3);
  assert(dmax_mod == 0, ['il blocco M NON riproduce il model acc_iidm_fsm (dmax=%.4g): integrazione/' ...
         'handshake col Divide, non la matematica (quella la copre G2)'], dmax_mod);
  assert(dmax_sp3 == 0, 'il blocco M NON e'' bit-identico al riferimento SP3 (dmax=%.4g)', dmax_sp3);
  fprintf('=== G3/G4 PASSATI: blocco M bit-identico a model e SP3 su %d/%d control-step ===\n', n, K);
end


function A = drive_acciidm_m(seq, hold, stopT)
%DRIVE_ACCIIDM_M  pilota Donatello_ACC_IIDM_M con la sequenza fisica seq (4 x K), ogni colonna tenuta
%  `hold` clock (>= latenza del blocco: SNN time-mux + 5 divisioni sequenziali).
  K = size(seq, 2);
  assignin('base', 'stim_m', [(0:K-1).' * hold, seq.']);
  mdl = 'sp4m_mdl'; if bdIsLoaded(mdl), close_system(mdl, 0); end
  new_system(mdl); load_system(mdl);
  add_block('snn_champions_lib/Donatello_ACC_IIDM_M', [mdl '/DUT']);
  add_block('simulink/Sources/From Workspace', [mdl '/src'], 'VariableName', 'stim_m', ...
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
