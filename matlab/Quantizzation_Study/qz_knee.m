function qz_knee()
%QZ_KNEE  [Quantizzation_Study] Incrocia le curve vs nfrac — accuratezza open-loop (acc_sweep), car-following
%  (cl_sweep: coll_extra + NRMSE), risorse+potenza (res_sweep) — e propone i livelli candidati per il menu
%  quantizzazione. Integra il verdetto di sicurezza gia' ottenuto (0 collisioni extra fino a nfrac=2).
  here = fileparts(mfilename('fullpath'));
  A = readtable(fullfile(here,'acc_sweep.tsv'),'FileType','text','Delimiter','\t');   % champion nfrac maxd
  C = readtable(fullfile(here,'cl_sweep.tsv'), 'FileType','text','Delimiter','\t');    % nfrac coll_* ... NRMSE_mean
  R = readtable(fullfile(here,'res_sweep.tsv'),'FileType','text','Delimiter','\t');    % nfrac WNS ... LUT FF DSP BRAM Ptot ...
  fr = sort(unique(C.nfrac));
  lut13 = R.LUT(R.nfrac==13); if isempty(lut13), lut13 = NaN; end
  pt13  = R.Ptot_W(R.nfrac==13); if isempty(pt13), pt13 = NaN; end
  fprintf('\n=== TAVOLA INCROCIATA vs nfrac ===\n');
  fprintf('nfrac | max|d| | coll_extra | NRMSE | LUT   FF   DSP | Ptot_W | dLUT%% dPwr%% (vs n13)\n');
  fprintf('%s\n', repmat('-',1,86));
  for i = 1:numel(fr)
    f = fr(i);
    md = A.maxd(A.nfrac==f); if isempty(md), md = NaN; end
    ce = C.coll_extra(C.nfrac==f); nr = C.NRMSE_mean(C.nfrac==f);
    rr = R(R.nfrac==f,:);
    if isempty(rr)
      fprintf('%5d | %5.2f | %10d | %5.3f |  (sintesi mancante)\n', f, md, ce, nr); continue;
    end
    dl = 100*(rr.LUT - lut13)/lut13; dp = 100*(rr.Ptot_W - pt13)/pt13;
    fprintf('%5d | %5.2f | %10d | %5.3f | %4d %4d %3d | %6.3f | %+5.1f %+5.1f\n', ...
            f, md, ce, nr, rr.LUT, rr.FF, rr.DSP, rr.Ptot_W, dl, dp);
  end
  fprintf('\n=== LIVELLI CANDIDATI per il menu quantizzazione ===\n');
  fprintf('  SICUREZZA: invariante fino a nfrac=2 (0 collisioni extra su 99 scenari con cut-in) -> floor = 2\n');
  fprintf('  FEDELTA'' PARAMETRI (NRMSE): ginocchio ~nfrac=4 (sopra piatta ~0.09; sotto raddoppia: 0.20@n3, 0.33@n2)\n');
  fprintf('  RISORSE/POTENZA: dalla tavola sopra (dLUT%%/dPwr%% vs n13) -> il risparmio d''area per bit\n');
  fprintf('  -> proposta: 13 (rif) · ~8 (params quasi-fedeli) · 4 (ginocchio params) · 2 (min area, safety-OK)\n');
  fprintf('  La scelta finale del menu incrocia il risparmio d''area (res_sweep) con la fedelta'' voluta.\n');
end
