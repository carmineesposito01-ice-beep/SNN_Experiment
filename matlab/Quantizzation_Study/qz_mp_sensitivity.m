function qz_mp_sensitivity(levels)
%QZ_MP_SENSITIVITY  [Quantizzation_Study] Fase A: per ciascun campo, fissa gli altri 5 a 13 e abbassa il suo
%  nfrac; misura il cruscotto completo (max|Δgap| cancello + coll_extra + SSM + NRMSE) sull'intero dataset.
%  Scrive mp_sens.tsv (field, nfrac, ...). Trova il floor per campo. Un MEX per config (build-if-missing).
%  I MEX sono cachati su disco -> un rilancio dopo un crash riusa quelli gia' costruiti (niente 2h perse).
  if nargin < 1 || isempty(levels), levels = 13:-1:1; end   % da 13 giu' fino a 1 (lo 0 e' estensione a parte)
  here = fileparts(mfilename('fullpath'));
  fields = {'V','fatigue','acc','accw','raw','w'};
  fid = fopen(fullfile(here,'mp_sens.tsv'),'w');
  fprintf(fid, 'field\tnfrac\tmaxdgap\tcoll_extra\tpass\tmin_gap\tbrake_margin\tmax_DRAC\tmin_TTC\tNRMSE_mean\timpact_max\n');
  floors = struct();
  for fi_ = 1:6
    lastPass = 13;
    for L = levels
      nf = [13 13 13 13 13 13]; nf(fi_) = L;
      o = qz_mp_gate(nf, 1:99);
      fprintf(fid, '%s\t%d\t%.4f\t%d\t%d\t%.4f\t%.4f\t%.4f\t%.4f\t%.6g\t%.4f\n', ...
              fields{fi_}, L, o.maxdgap, o.coll_extra, o.pass, o.min_gap, o.brake_margin, ...
              o.max_DRAC, o.min_TTC, mean(o.nrmse), o.impact_max);
      fprintf('  %-8s nfrac=%2d: max|dgap|=%.3f coll_extra=%d pass=%d\n', fields{fi_}, L, o.maxdgap, o.coll_extra, o.pass);
      if o.pass, lastPass = L; end
    end
    floors.(fields{fi_}) = lastPass;   % floor = ultimo livello che passa scendendo
  end
  fclose(fid);
  fprintf('\nFLOOR per campo: '); disp(floors);
  fprintf('scritto %s\n', fullfile(here,'mp_sens.tsv'));
end
