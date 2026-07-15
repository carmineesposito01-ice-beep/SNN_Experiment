function [best, tab, bud] = run_acc_fixed_sweep(fracs, nTraj)
%RUN_ACC_FIXED_SWEEP  [SP3] Quanti bit frazionari servono all'ACC-IIDM in fixed?
%
%  IL BUDGET NON E' UN NUMERO MAGICO. La spec SP2 parla di 0.028, ma quello e' un errore su **v0
%  [m/s]**, non su **accel [m/s^2]**: applicarlo alla lettera sarebbe misurare la cosa sbagliata.
%  Criterio DERIVATO (stesso spirito di DECODE_LUT_SWEEP §5bis - l'approssimazione non deve diventare
%  la fonte d'errore DOMINANTE):
%     E_snn  = |accel(IIDM double, params dalla rete FIXED) - accel(IIDM double, params dalla rete DOUBLE)|
%              cioe' l'errore in accel che il progetto ha GIA' accettato a monte;
%     E_iidm = |accel(IIDM FIXED) - accel(IIDM double)|, a parita' di parametri.
%  Si passa se E_iidm < E_snn su p99 E max. Si sceglie il MINIMO nfrac che passa.
%
%  ⚠️ LENTO PER COSTRUZIONE: gira in `fi` INTERPRETATO (snn_decode_lut + acc_iidm_open fixed), ~10 ms
%     a chiamata. Il dataset intero (60 traj x 1000 step) costa ~10 min per configurazione, quindi
%     ~1 h per uno sweep di 6 valori. NON ridurre il campione per farlo stare in un timeout: o si
%     lancia in background, o si MEXa il kernel (una MEX per nfrac: il tipo e' compile-time).
%     `nTraj` esiste solo per un dry-run di validazione del cancello, e l'esito lo dichiara.
  if nargin < 1 || isempty(fracs), fracs = 8:2:18; end
  if nargin < 2 || isempty(nTraj), nTraj = 60; end
  here = fileparts(mfilename('fullpath'));
  ds = load(fullfile(here, 'test_dataset.mat')); tr = ds.trajectories;
  d  = load(fullfile(here, 'champions_export.mat')); ch = d.champions;
  if iscell(ch), ch = [ch{:}]; end
  c = ch(find(arrayfun(@(x) strcmp(char(string(x.name)), 'Donatello'), ch), 1));
  W = champ_weights(c); Tp = numerictype(1, 21, 13); Td = acc_types('double');
  nTraj = min(nTraj, numel(tr));
  if nTraj < numel(tr)
    fprintf(['*** DRY-RUN: %d traiettorie su %d. NON e'' la misura del cancello (regola: dataset ' ...
             'intero). ***\n'], nTraj, numel(tr));
  end

  % ---- BUDGET: il footprint in accel della quantizzazione GIA' accettata della rete ----
  Esnn = [];
  Tdb = snn_types('double');
  for i = 1:nTraj
    val = double(tr{i}.val);
    Rfx = double(snn_traj_fixed_r16_mex(val, W));              % rete FIXED (MEX)
    snn_core(zeros(4,1), W, Tdb, true);                        % rete DOUBLE: reset
    clear acc_iidm_open; aF = zeros(size(val,2),1); aD = zeros(size(val,2),1);
    for k = 1:size(val,2)
      pF = double(snn_decode_lut(fi(Rfx(k,:).', Tp), 64));
      aF(k) = acc_iidm_open(val(1,k), val(2,k), val(3,k), val(4,k), pF, k == 1, Td);
    end
    clear acc_iidm_open;
    for k = 1:size(val,2)
      raw = snn_core(snn_normalize(val(:,k), W.norm), W, Tdb, false);
      pD  = snn_decode(double(raw), c.param_lo, c.param_hi, c.decode_offset, c.logit_tau);
      aD(k) = acc_iidm_open(val(1,k), val(2,k), val(3,k), val(4,k), pD, k == 1, Td);
    end
    Esnn = [Esnn; abs(aF - aD)]; %#ok<AGROW>
  end
  bud = struct('p99', prctile(Esnn, 99), 'max', max(Esnn), 'n', numel(Esnn));
  fprintf('\nBUDGET derivato su %d campioni (%d traj): p99 = %.6g   max = %.6g  [m/s^2]\n\n', ...
          bud.n, nTraj, bud.p99, bud.max);

  % ---- E_iidm(nfrac): errore AGGIUNTO dal fixed, a parita' di parametri ----
  tab = zeros(numel(fracs), 3);
  fprintf('%-6s %13s %13s %8s\n', 'nfrac', 'E_iidm p99', 'E_iidm max', 'passa');
  for j = 1:numel(fracs)
    Tf = acc_types('fixed', fracs(j)); E = [];
    for i = 1:nTraj
      val = double(tr{i}.val);
      R = double(snn_traj_fixed_r16_mex(val, W));
      P = zeros(size(val,2), 5);
      for k = 1:size(val,2), P(k,:) = double(snn_decode_lut(fi(R(k,:).', Tp), 64)).'; end
      clear acc_iidm_open; a1 = zeros(size(val,2),1);
      for k = 1:size(val,2)
        a1(k) = acc_iidm_open(val(1,k), val(2,k), val(3,k), val(4,k), P(k,:).', k == 1, Td);
      end
      clear acc_iidm_open; a2 = zeros(size(val,2),1);
      for k = 1:size(val,2)
        a2(k) = double(acc_iidm_open(val(1,k), val(2,k), val(3,k), val(4,k), P(k,:).', k == 1, Tf));
      end
      E = [E; abs(a2 - a1)]; %#ok<AGROW>
    end
    tab(j,:) = [fracs(j), prctile(E,99), max(E)];
    fprintf('%-6d %13.6g %13.6g %8s\n', fracs(j), tab(j,2), tab(j,3), ...
            string(tab(j,2) < bud.p99 && tab(j,3) < bud.max));
  end

  k = find(tab(:,2) < bud.p99 & tab(:,3) < bud.max, 1);
  assert(~isempty(k), ['nessun nfrac in [%s] rispetta il budget derivato (p99 < %.4g e max < %.4g): ' ...
         'l''IIDM in fixed sarebbe la fonte d''errore DOMINANTE. NON allargare il budget: se non passa ' ...
         'nemmeno col nfrac piu' ' alto, il problema sono i BIT INTERI (saturazione) o l''ordine delle ' ...
         'operazioni, non la risoluzione.'], mat2str(fracs), bud.p99, bud.max);
  best = tab(k,1);
  fprintf('\n>>> MINIMO nfrac che rispetta il budget: %d <<<\n', best);
end
