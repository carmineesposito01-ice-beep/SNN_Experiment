function qz_mp_combine()
%QZ_MP_COMBINE  [Quantizzation_Study] Fase B: dai floor di mp_sens.tsv compone l'aggressiva (tutti-ai-floor),
%  la verifica in CONGIUNTA; se rompe il cancello, risale di 1 bit sul campo che piu' contribuisce a max|Δgap|
%  (misurato risalendo un campo per volta), finche' passa. Scrive mp_finalists.tsv col cruscotto.
  here = fileparts(mfilename('fullpath'));
  Ssens = readtable(fullfile(here,'mp_sens.tsv'),'FileType','text','Delimiter','\t');
  fields = {'V','fatigue','acc','accw','raw','w'};
  floors = zeros(1,6);
  for k = 1:6
    sub = Ssens(strcmp(Ssens.field, fields{k}) & Ssens.pass==1, :);
    floors(k) = min(sub.nfrac);   % floor = minimo nfrac che passa isolato
  end
  fid = fopen(fullfile(here,'mp_finalists.tsv'),'w');
  fprintf(fid, 'config\tnV\tnfat\tnacc\tnaccw\tnraw\tnw\tmaxdgap\tcoll_extra\tpass\tNRMSE_mean\n');
  wrow = @(name, nf, o) fprintf(fid, '%s\t%d\t%d\t%d\t%d\t%d\t%d\t%.4f\t%d\t%d\t%.6g\n', ...
        name, nf(1),nf(2),nf(3),nf(4),nf(5),nf(6), o.maxdgap, o.coll_extra, o.pass, mean(o.nrmse));

  nf = floors; o = qz_mp_gate(nf, 1:99); wrow('aggressiva', nf, o);
  fprintf('aggressiva %s: pass=%d max|dgap|=%.3f\n', mat2str(nf), o.pass, o.maxdgap);
  guard = 0;
  while ~o.pass && guard < 12
    guard = guard + 1;
    % risali di 1 bit il campo che, risalito da solo, riduce di piu' max|Δgap|
    best = 0; bestk = 0;
    for k = 1:6
      if nf(k) >= 13, continue; end
      tf = nf; tf(k) = tf(k) + 1; ot = qz_mp_gate(tf, 1:99);
      gain = o.maxdgap - ot.maxdgap;
      if gain > best, best = gain; bestk = k; end
    end
    assert(bestk > 0, 'nessun campo migliora: la combinazione non converge');
    nf(bestk) = nf(bestk) + 1; o = qz_mp_gate(nf, 1:99);
    wrow(sprintf('backoff+%s', fields{bestk}), nf, o);
    fprintf('back-off +%s -> %s: pass=%d max|dgap|=%.3f\n', fields{bestk}, mat2str(nf), o.pass, o.maxdgap);
  end
  fclose(fid);
  assert(o.pass, 'nessuna combinazione passa il cancello');
  fprintf('\nCONFIG FINALE (area-ottimale accettata): %s\n', mat2str(nf));
  fprintf('scritto %s\n', fullfile(here,'mp_finalists.tsv'));
end
