function dmax = run_block_traj_test(K, blockName, hold, trajIdx, nfrac)
%RUN_BLOCK_TRAJ_TEST  Prova dei blocchi HDL-ready sulla TRAIETTORIA REALE del dataset.
%  Verifica che il blocco, pilotato in streaming con la traiettoria (un control-step per periodo
%  d'inferenza), riproduca il riferimento — cioe' che lo **stato si porti correttamente** fra
%  inferenze successive, non solo sul primo campione.
%
%  1) misura il PERIODO d'inferenza del blocco free-running (non lo assume);
%  2) pilota il blocco con K control-step di `test_dataset.mat` (ognuno tenuto 1 periodo);
%  3) confronta la sequenza di params col riferimento = MEX (normalize float) + `snn_decode_hdl`.
%
%  Atteso: **dmax = 0** (bit-exact).
%  nfrac (opz., default 20): bit frazionari dell'ingresso. 20 = bit-exact; passare 13 forza il caso
%    NON bit-exact (CONTROLLO NEGATIVO: il gate DEVE far scattare l'assert dmax==0 -> prova che discrimina).
%  ⚠️ Gli ingressi sono pilotati a `fixdt(1,32,20)`: con >=20 bit frazionari il blocco e' bit-exact.
%     Con ingressi a Q?.13 l'arrotondamento di xn devia di 1 LSB ~1 volta su 25 step -> uno spike
%     flippa -> i params divergono (HDL_PHASE §3.1.3).
  if nargin < 1 || isempty(K), K = 20; end
  if nargin < 2 || isempty(blockName), blockName = 'Donatello_Champion'; end
  if nargin < 3 || isempty(hold), hold = 500; end     % >= latenza MAX (FAST splitpipe = 406); QUALUNQUE valore >= latenza
  if nargin < 4 || isempty(trajIdx), trajIdx = 1; end
  if nargin < 5 || isempty(nfrac), nfrac = 20; end    % bit frazionari ingresso; <20 (es.13) -> NON bit-exact
  here = fileparts(mfilename('fullpath'));
  ds = load(fullfile(here, 'test_dataset.mat')); tr = ds.trajectories;
  assert(trajIdx <= numel(tr), 'traiettoria %d inesistente (ne esistono %d)', trajIdx, numel(tr));
  tr = tr(trajIdx);                                   % traiettoria sotto test
  d  = load(fullfile(here, 'champions_export.mat')); champs = d.champions;
  if iscell(champs), champs = [champs{:}]; end
  c  = champs(find(arrayfun(@(x) strcmp(char(string(x.name)), 'Donatello'), champs), 1));
  W  = champ_weights(c); Tp = numerictype(1, 21, 13);
  val = double(tr{1}.val);

  % 1) LATENZA (ingresso costante). Il blocco e' edge-triggered sul cambio d'ingresso: con un
  %    ingresso costante deve fare UNA SOLA inferenza. (Col vecchio free-running ne faceva una ogni
  %    341 clock -> stato che evolve troppo in fretta: era il difetto.)
  P_log = drive(blockName, val(:,1) * ones(1,3), 700, 700, nfrac);
  chg = find(any(abs(diff(P_log,1,1)) > 0, 2));
  assert(~isempty(chg), 'nessun aggiornamento params: il blocco non produce (FSM ferma?)');
  lat = chg(1);
  assert(numel(chg) == 1, ['il blocco ri-esegue su ingresso COSTANTE (%d aggiornamenti): non e'' ' ...
         'edge-triggered -> lo stato evolve troppo in fretta'], numel(chg));
  fprintf('latenza inferenza = %d clock ; ingresso costante -> 1 sola inferenza (edge-triggered OK)\n', lat);
  assert(hold >= lat, 'hold=%d < latenza=%d: il time-mux non fa in tempo', hold, lat);

  % 2) riferimento: MEX (normalizza in float, come il PS) + il decode COERENTE col blocco
  %    (Champion -> snn_decode_hdl ; LUT{N} -> snn_decode_lut(.,N). Usare il decode sbagliato
  %     produce un falso mismatch pari all'errore d'approssimazione della LUT.)
  tokN = regexp(blockName, 'LUT(\d+)$', 'tokens', 'once');
  if isempty(tokN), Ndec = 64;                      % Donatello_Champion = decode LUT-64 (dal 2026-07-14)
  else,             Ndec = str2double(tokN{1}); end
  Rmex = double(snn_traj_fixed_r16_mex(tr{1}.val, W));
  p_ref = zeros(K,5);
  for k = 1:K
    p_ref(k,:) = double(snn_decode_lut(fi(Rmex(k,:).', Tp), Ndec)).';
  end

  % 3) blocco in streaming sulla traiettoria; campionamento DETERMINISTICO (non sui cambiamenti:
  %    due inferenze possono dare params identici e l'indicizzazione slitterebbe)
  P_all = drive(blockName, val(:,1:K), hold, K*hold + 20, nfrac);
  idx = hold * (0:K-1).' + lat + 1;
  idx = idx(idx <= size(P_all,1));
  p_blk = P_all(idx, :);
  n = min(size(p_blk,1), K);
  assert(n == K, 'attesi %d aggiornamenti, trovati %d', K, n);

  dmax = max(max(abs(p_blk - p_ref(1:n,:))));
  fprintf('%-22s traj=%-3d hold=%-5d su %d control-step: dmax vs riferimento = %.4g\n', ...
          blockName, trajIdx, hold, n, dmax);
  assert(dmax == 0, 'il blocco NON riproduce il riferimento in streaming (dmax=%.4g)', dmax);
  fprintf('=== TRAJ TEST PASSATO: %s bit-exact in streaming ===\n', blockName);
end

function P = drive(blockName, seq, hold, stopT, nfrac)
% pilota il blocco con la sequenza fisica seq (4 x K), ogni colonna tenuta `hold` clock
  K = size(seq, 2);
  ts = [(0:K-1).' * hold, seq.'];
  assignin('base', 'stimTS_bt', ts);
  mdl = 'blk_traj_mdl'; if bdIsLoaded(mdl), close_system(mdl, 0); end
  new_system(mdl); load_system(mdl);
  add_block(['snn_champions_lib/' blockName], [mdl '/DUT']);
  add_block('simulink/Sources/From Workspace', [mdl '/src'], 'VariableName', 'stimTS_bt', ...
            'SampleTime', '1', 'Interpolate', 'off', 'OutputAfterFinalValue', 'Holding final value');
  add_block('simulink/Signal Routing/Demux', [mdl '/dm'], 'Outputs', '4');
  add_line(mdl, 'src/1', 'dm/1');
  for j = 1:4
    add_block('simulink/Signal Attributes/Data Type Conversion', [mdl '/c' num2str(j)], ...
              'OutDataTypeStr', sprintf('fixdt(1,32,%d)', nfrac));  % >=20 frazionari=bit-exact; 13=ctrl negativo
    add_line(mdl, ['dm/' num2str(j)], ['c' num2str(j) '/1']);
    add_line(mdl, ['c' num2str(j) '/1'], ['DUT/' num2str(j)]);
  end
  add_block('simulink/Signal Routing/Mux', [mdl '/mx'], 'Inputs', '5');
  for j = 1:5, add_line(mdl, ['DUT/' num2str(j)], ['mx/' num2str(j)]); end
  add_block('simulink/Sinks/To Workspace', [mdl '/Pw'], 'VariableName', 'Pw', 'SaveFormat', 'Array');
  add_line(mdl, 'mx/1', 'Pw/1');
  set_param(mdl, 'Solver', 'FixedStepDiscrete', 'FixedStep', '1', ...
            'StopTime', num2str(stopT), 'SaveOutput', 'off');
  so = sim(mdl); P = double(so.get('Pw')); close_system(mdl, 0);
end
