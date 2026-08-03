function qz_mp_selftest0()
%QZ_MP_SELFTEST0  Il forward mp a nf=[13...] coincide bit per bit col forward unico a nfrac=13.
%  ATTENZIONE: snn_core ha STATO PERSISTENTE condiviso (V, fatigue, ...). I due forward NON vanno
%  interlacciati nello stesso tick: si sovrascriverebbero lo stato a vicenda (double-step) e darebbero
%  un dmax spurio. Si esegue mp per l'INTERA traiettoria (reset a k==1), poi unico per l'intera
%  traiettoria (reset a k==1), infine si confrontano le serie.
%  La prova VERA e' il Gate tipi @13 (numerictype identici a snn_types(13) => forward bit-identico per
%  costruzione); questo loop e' conferma empirica su input reali diversi. Determinismo: dmax==0 qui => ovunque.
%  Campione ridotto (6 profili leader x 20 tick): il forward INTERPRETATO (niente MEX in Task 0) costa
%  ~1 s/chiamata, quindi 10x200 sarebbe ~1 ora.
  here = fileparts(mfilename('fullpath')); mroot = fileparts(here); addpath(mroot); addpath(here);
  dd = load(fullfile(mroot,'champions_export.mat')); ch = dd.champions; if iscell(ch), ch=[ch{:}]; end
  c = ch(find(arrayfun(@(x) strcmp(char(string(x.name)),'Donatello'), ch),1)); W = champ_weights(c);
  ds = load(fullfile(here,'test_dataset_exhaustive.mat')); tr = ds.trajectories;
  nf13 = [13 13 13 13 13 13];
  dmax = 0;
  for i = 1:6
    t = tr{i}; s = max(t.s_init, 0.5); v = t.v_init;
    vl = t.v_leader(:).'; N = min(20, numel(vl));
    % input fisici deterministici (s, v costanti; dv, vl variano col profilo leader)
    X = zeros(4, N);
    for k = 1:N, X(:,k) = [s; v; v - vl(k); vl(k)]; end
    % 1) forward mp per l'INTERA traiettoria (stato pulito: reset a k==1)
    Pmp = zeros(N, 5);
    for k = 1:N, [p, ~] = qz_snn_cl_step_mp(X(:,k), W, k==1, nf13); Pmp(k,:) = p(:).'; end
    % 2) forward unico per l'INTERA traiettoria (stato pulito: reset a k==1)
    Pu = zeros(N, 5);
    for k = 1:N, [p, ~] = qz_snn_cl_step(X(:,k), W, k==1, 13); Pu(k,:) = p(:).'; end
    dmax = max(dmax, max(abs(Pmp(:) - Pu(:))));
  end
  fprintf('dmax forward mp@13 vs unico@13 = %.4g\n', dmax);
  assert(dmax == 0, 'forward mp @13 NON bit-exact al forward unico @13');
  disp('GATE forward mp @13: BIT-EXACT');
end
