function dmax = run_block_closed_loop_test(trajIdx, K, hold, dvMode)
%RUN_BLOCK_CLOSED_LOOP_TEST  [SP2] Il blocco Donatello_ACC_IIDM in ANELLO CHIUSO su Simulink.
%  Dato il leader (posizione x_l e velocita' v_l), l'anello calcola gap e dv, li passa al blocco,
%  e integra l'ego con l'accelerazione che ne esce. Confronto con l'anello di riferimento in
%  MATLAB (snn_cl_step_mex). Atteso: **dmax = 0**.
%
%  Perche' dmax=0 e' un criterio forte QUI: in anello chiuso l'errore si retroaziona, quindi una
%  differenza di 1 LSB al passo k diverge nei passi successivi. O e' 0, o si vede.
%
%  DISCRETIZZAZIONE (scelta per riprodurre la struttura del dataset, misurata su 60k campioni):
%    x_l(k) = x_l(k-1) + v_l(k)*DT     leader integrato con la v_l NUOVA
%    x_e(k) = x_e(k-1) + v(k-1)*DT     ego balistico con la v VECCHIA (come generator.py)
%    v(k)   = clip(v(k-1) + accel*DT, 0, 1.2*v0)
%    s(k)   = clip(x_l(k) - x_e(k), 0.5*s0, 150)   clip come generator.py
%  Con dvMode='train' l'anello soddisfa per costruzione le due relazioni del dataset:
%    dv(k) = v(k-1) - v_l(k)   e   s(k)-s(k-1) = -dv(k)*DT
%
%  dvMode: 'train' -> dv(k) = v(k-1) - v_l(k)  (la convenzione su cui la rete e' stata addestrata)
%          'inst'  -> dv(k) = v(k)   - v_l(k)  (fisica istantanea, quella realizzabile su strada)
%
%  ⚠️ NON e' un test di recupero dei parametri: in anello chiuso l'ego e' guidato dai parametri
%     STIMATI dalla rete stessa -> il sistema e' auto-consistente e i gt_params del dataset non
%     sono il bersaglio. Qui si verifica l'IMPLEMENTAZIONE (dmax=0) e il COMPORTAMENTO (segue il
%     leader, gap limitato). Vedi document/SP2_ACC_IIDM.md §Anello chiuso.
  if nargin < 1 || isempty(trajIdx), trajIdx = 1; end
  if nargin < 2 || isempty(K), K = 60; end
  if nargin < 3 || isempty(hold), hold = 400; end       % qualunque valore >= latenza (~341)
  if nargin < 4 || isempty(dvMode), dvMode = 'train'; end
  assert(any(strcmp(dvMode, {'train','inst'})), 'dvMode: ''train'' o ''inst''');
  here = fileparts(mfilename('fullpath'));

  [C, lead] = cl_setup(here, trajIdx, K);
  ref = cl_matlab(C, lead, K, dvMode);                  % riferimento SW
  sim_ = cl_simulink(here, C, lead, K, hold, dvMode);   % anello Simulink

  d = struct('s', max(abs(sim_.s - ref.s)), 'v', max(abs(sim_.v - ref.v)), ...
             'dv', max(abs(sim_.dv - ref.dv)), 'accel', max(abs(sim_.accel - ref.accel)));
  dmax = max([d.s d.v d.dv d.accel]);
  fprintf(['ANELLO CHIUSO traj=%-3d K=%-4d hold=%-5d dv=%-6s : dmax = %.4g ' ...
           '(s=%.3g v=%.3g dv=%.3g accel=%.3g)\n'], trajIdx, K, hold, dvMode, dmax, ...
           d.s, d.v, d.dv, d.accel);
  fprintf('   comportamento: gap=[%.2f %.2f] m  v_ego=[%.2f %.2f]  v_lead=[%.2f %.2f] m/s\n', ...
          min(ref.s), max(ref.s), min(ref.v), max(ref.v), min(lead.vl), max(lead.vl));
  assert(all(isfinite(ref.s)) && all(isfinite(ref.v)), 'anello divergente: stato non finito');
  if dmax > 0
    % A che PASSO divergono, e come? In anello chiuso il primo passo sbagliato spiega tutti gli
    % altri: guardare la coda e' inutile, serve il primo scarto.
    k1 = find(abs(sim_.s - ref.s) + abs(sim_.v - ref.v) + abs(sim_.accel - ref.accel) > 0, 1);
    fprintf('\n   PRIMO passo divergente: k = %d\n', k1);
    fprintf('   %-4s | %-21s | %-21s | %-21s\n', 'k', 's  (rif / sim)', 'v  (rif / sim)', 'accel (rif / sim)');
    for k = max(1,k1-1):min(numel(ref.s), k1+4)
      fprintf('   %-4d | %9.5f / %9.5f | %9.5f / %9.5f | %9.5f / %9.5f\n', ...
              k, ref.s(k), sim_.s(k), ref.v(k), sim_.v(k), ref.accel(k), sim_.accel(k));
    end
    fprintf('\n');
  end
  assert(dmax == 0, ['il blocco in anello chiuso NON riproduce il riferimento (dmax=%.4g). ' ...
         'NON allargare la tolleranza: in anello chiuso 1 LSB diverge, quindi dmax>0 = differenza reale.'], dmax);
  fprintf('=== ANELLO CHIUSO PASSATO: blocco == riferimento, bit-exact ===\n');
end


function [C, lead] = cl_setup(here, trajIdx, K)
% costanti dell'anello + profilo del leader (posizione integrata dalla v_l del dataset)
  ds = load(fullfile(here, 'test_dataset.mat')); tr = ds.trajectories;
  assert(trajIdx <= numel(tr), 'traiettoria %d inesistente (ne esistono %d)', trajIdx, numel(tr));
  t = tr{trajIdx}; val = double(t.val); gt = double(t.gt_params);
  assert(K <= size(val,2), 'K=%d > lunghezza traiettoria (%d)', K, size(val,2));
  d = load(fullfile(here, 'champions_export.mat')); ch = d.champions;
  if iscell(ch), ch = [ch{:}]; end
  c = ch(find(arrayfun(@(x) strcmp(char(string(x.name)), 'Donatello'), ch), 1));

  C.W = champ_weights(c);
  C.DT = 0.1; C.S_MAX = 150;
  C.s_lo = 0.5 * gt(3);          % clip inferiore = 0.5*s0, come generator.py
  C.v_cap = 1.2 * gt(1);         % clip superiore della velocita', come generator.py
  C.xe0 = -val(1,1);             % origine del leader = 0 -> x_e(1) = -s(1)
  C.ve0 = val(2,1);

  lead.vl = val(4, 1:K).';
  lead.xl = zeros(K,1);          % x_l(k) = x_l(k-1) + v_l(k)*DT  (v_l NUOVA: e' cio' che rende
  for k = 2:K                    %  s(k)-s(k-1) == -dv(k)*DT, la relazione del dataset)
    lead.xl(k) = lead.xl(k-1) + lead.vl(k)*C.DT;
  end
end


function o = cl_matlab(C, lead, K, dvMode)
% anello di riferimento in MATLAB: identico per costruzione a quello che fa la chart EGO
  q = @(x) floor(x * 2^20) / 2^20;   % = Data Type Conversion a fixdt(1,32,20), RndMeth 'Floor'
  xe = C.xe0; ve = C.ve0; ve_prev = C.ve0;
  clear snn_cl_step_mex                                  % azzera core + filtro OU
  o.s = zeros(K,1); o.v = zeros(K,1); o.dv = zeros(K,1); o.accel = zeros(K,1); o.p = zeros(K,5);
  for k = 1:K
    s = min(max(lead.xl(k) - xe, C.s_lo), C.S_MAX);
    if strcmp(dvMode, 'train'), dvk = ve_prev - lead.vl(k); else, dvk = ve - lead.vl(k); end
    xq = [q(s); q(ve); q(dvk); q(lead.vl(k))];
    [p, acc] = snn_cl_step_mex(xq, C.W, k == 1);
    o.s(k)=xq(1); o.v(k)=xq(2); o.dv(k)=xq(3); o.accel(k)=acc; o.p(k,:)=p(:).';
    xe_new  = xe + ve*C.DT;                              % balistico: v VECCHIA
    ve_new  = min(max(ve + acc*C.DT, 0), C.v_cap);
    ve_prev = ve; xe = xe_new; ve = ve_new;
  end
end


function o = cl_simulink(here, C, lead, K, hold, dvMode)
% anello chiuso in Simulink: EGO (plant) <-> DUT (Donatello_ACC_IIDM), retroazione su accel
  assignin('base', 'cl_lead', [(0:K-1).'*hold, lead.xl, lead.vl]);
  mdl = 'cl_mdl'; if bdIsLoaded(mdl), close_system(mdl, 0); end
  new_system(mdl); load_system(mdl);

  add_block('simulink/Sources/From Workspace', [mdl '/lead'], 'VariableName', 'cl_lead', ...
            'SampleTime', '1', 'Interpolate', 'off', 'OutputAfterFinalValue', 'Holding final value');
  add_block('simulink/Signal Routing/Demux', [mdl '/dmL'], 'Outputs', '2');
  add_line(mdl, 'lead/1', 'dmL/1');

  add_block('simulink/User-Defined Functions/MATLAB Function', [mdl '/EGO']);
  chart = sfroot().find('-isa', 'Stateflow.EMChart', 'Path', [mdl '/EGO']);
  chart.Script = ego_code(C, hold, dvMode);
  add_line(mdl, 'dmL/1', 'EGO/2');            % x_l
  add_line(mdl, 'dmL/2', 'EGO/3');            % v_l

  add_block([lib_path(here) '/Donatello_ACC_IIDM'], [mdl '/DUT']);
  add_block('simulink/Signal Routing/Demux', [mdl '/dmE'], 'Outputs', '4');
  add_line(mdl, 'EGO/1', 'dmE/1');
  for j = 1:4
    add_block('simulink/Signal Attributes/Data Type Conversion', [mdl '/c' num2str(j)], ...
              'OutDataTypeStr', 'fixdt(1,32,20)', 'RndMeth', 'Floor');   % Floor: deterministico,
    add_line(mdl, ['dmE/' num2str(j)], ['c' num2str(j) '/1']);           % nessun pareggio da indovinare
    add_line(mdl, ['c' num2str(j) '/1'], ['DUT/' num2str(j)]);
  end
  % ROTTURA DELL'ANELLO ALGEBRICO: la chart e' direct-feedthrough (accel dipende dagli ingressi nello
  % stesso passo). 1 clock di ritardo e' innocuo: l'accel serve al control-step dopo (>= 400 clock).
  add_block('simulink/Discrete/Unit Delay', [mdl '/z'], 'InitialCondition', '0', 'SampleTime', '1');
  add_line(mdl, 'DUT/1', 'z/1');
  add_line(mdl, 'z/1', 'EGO/1');

  % Si registrano i segnali DOPO la Data Type Conversion: sono quelli che il blocco vede davvero.
  % (Registrando l'uscita di EGO si confronterebbe un double non quantizzato col riferimento
  %  quantizzato -> scarto spurio di 1 LSB = 2^-20, che non e' una differenza del blocco.)
  add_block('simulink/Signal Routing/Mux', [mdl '/mxq'], 'Inputs', '4');
  for j = 1:4, add_line(mdl, ['c' num2str(j) '/1'], ['mxq/' num2str(j)]); end
  add_block('simulink/Sinks/To Workspace', [mdl '/Wq'], 'VariableName', 'Wq', 'SaveFormat', 'Array');
  add_line(mdl, 'mxq/1', 'Wq/1');
  add_block('simulink/Sinks/To Workspace', [mdl '/Wa'], 'VariableName', 'Wa', 'SaveFormat', 'Array');
  add_line(mdl, 'z/1', 'Wa/1');

  set_param(mdl, 'Solver', 'FixedStepDiscrete', 'FixedStep', '1', ...
            'StopTime', num2str(K*hold + 10), 'SaveOutput', 'off');
  so = sim(mdl); close_system(mdl, 0);

  % ⚠️ La forma che To Workspace restituisce DIPENDE dal segnale: da un Mux di SCALARI esce un
  % vettore -> [T x larghezza]; da un segnale MATRICIALE (es. l'uscita [4x1] di EGO) esce un array
  % 3-D [larghezza x 1 x T]. Qui il Mux e' di scalari => [T x 4]. Asserito, non assunto: la forma
  % sbagliata fa leggere righe a caso, e una guardia tipo `min(idx, size(.,1))` lo rende MUTO.
  Wq = double(so.get('Wq'));
  assert(ismatrix(Wq) && size(Wq,2) == 4, ...
         'forma inattesa da To Workspace: %s (atteso [T 4])', mat2str(size(Wq)));
  Q = Wq.';                                    % [4 x T] : righe = [s; v; dv; v_l], post-conversione
  A = double(so.get('Wa')); A = A(:);          % accel (scalare) -> [T x 1]

  % campionamento DETERMINISTICO all'ULTIMO clock di ogni control-step (li' dentro lo stato e' fermo).
  % colonna c <-> istante t = c-1  =>  t = k*hold - 1  =>  c = k*hold
  idx = hold * (1:K).';
  assert(max(idx) <= size(Q,2) && max(idx) <= numel(A), ...
         'simulazione troppo corta: servono %d campioni, ce ne sono %d (alzare StopTime)', ...
         max(idx), min(size(Q,2), numel(A)));
  o.s = Q(1,idx).'; o.v = Q(2,idx).'; o.dv = Q(3,idx).'; o.accel = A(idx);
end


function p = lib_path(here)
  lib = 'snn_champions_lib';
  if ~bdIsLoaded(lib), load_system(fullfile(here, [lib '.slx'])); end
  p = lib;
end


function code = ego_code(C, hold, dvMode)
%EGO_CODE  Chart del plant ego: integra l'ego una volta per control-step (ogni `hold` clock).
%  Il modello gira al rate di CLOCK (il time-mux della SNN vuole ~341 clock per inferenza), ma la
%  fisica avanza al rate di CONTROL-STEP: senza il contatore l'ego integrerebbe l'accelerazione a
%  ogni clock, cioe' ~400 volte troppo in fretta. E' il punto delicato dell'anello.
  M = @(x) sprintf('%.17g', x);
  if strcmp(dvMode, 'train')
    dvLine = '  dv = ve_prev - vl;              % convenzione del dataset: v PRIMA dell''update';
  else
    dvLine = '  dv = ve - vl;                   % fisica istantanea';
  end
  L = {
    'function out = EGO(accel, xl, vl)'
    '%#codegen'
    '% Plant ego dell''anello chiuso. out = [s; v; dv; v_l] (fisici, double).'
    '  persistent xe ve ve_prev cnt'
    '  if isempty(cnt)                  % isempty(<persistent>): l''unica forma che il codegen'
    ['    cnt = 0; xe = ' M(C.xe0) '; ve = ' M(C.ve0) '; ve_prev = ve;']
    '  else                             % riconosce come prova di definizione (vedi SP2_ACC_IIDM.md)'
    '    cnt = cnt + 1;'
    ['    if mod(cnt, ' num2str(hold) ') == 0     % UN control-step ogni `hold` clock']
    ['      xe_new  = xe + ve*' M(C.DT) ';        % balistico: usa la v VECCHIA']
    ['      ve_new  = min(max(ve + accel*' M(C.DT) ', 0), ' M(C.v_cap) ');']
    '      ve_prev = ve; xe = xe_new; ve = ve_new;'
    '    end'
    '  end'
    ['  s  = min(max(xl - xe, ' M(C.s_lo) '), ' M(C.S_MAX) ');   % clip come generator.py']
    dvLine
    '  out = [s; ve; dv; vl];'
    'end'
  };
  code = strjoin(L, newline);
end
