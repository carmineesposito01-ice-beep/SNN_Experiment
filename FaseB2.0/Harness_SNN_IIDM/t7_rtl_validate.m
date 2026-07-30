function V = t7_rtl_validate(workdir, idx, hold)
%T7_RTL_VALIDATE  Cancelli sull'anello chiuso RTL. Il riferimento del DUT e' il BLOCCO COMPOSTO,
%  ripilotato sugli ingressi che l'RTL ha EFFETTIVAMENTE ricevuto (t7_block_replay).
%
%   T7-EXACT    accel dell'RTL == accel del BLOCCO sugli stessi ingressi, BIT-ESATTO
%   PARAM-RANGE i 5 parametri letti dall'RTL stanno nei limiti del decode
%   NO-REPEAT   i 5 parametri non si ripetono mai: se si ripetessero, `align` non rilascerebbe i nuovi
%               ingressi fisici e l'ACC calcolerebbe su uno stato stantio (spec §9.3)
%
%  ⚠️ La correttezza del PLANT che genera quegli ingressi e' provata SEPARATAMENTE da PLANT-PAR, che
%     gira senza DUT (t7_plant_par). Le due prove insieme coprono l'anello: plant corretto + DUT
%     corretto => traiettoria corretta. Non e' circolare, perche' PLANT-PAR non usa il DUT e T7-EXACT
%     non usa il plant: confronta due risposte allo STESSO ingresso.
%
%  Cosa questi cancelli NON possono scoprire: un difetto di progetto del BLOCCO. Li' il riferimento
%  sbaglierebbe allo stesso modo. Per quello serve il confronto delle metriche con l'ORACOLO.
  if nargin < 3 || isempty(hold), hold = 700; end
  LO = [8 0.5 1 0.3 0.5]; HI = [45 2.5 5 2.5 3];   % limiti del decode (acciidm_m_algo, commento riga 649)
  FM = fimath('RoundingMethod','Floor','OverflowAction','Saturate');
  nExact = 0; nTot = 0; nRange = 0; nRep = 0; repScen = []; rangeScen = [];
  first = struct('scen',[],'k',[],'rtl',[],'blk',[]);

  for i = 1:numel(idx)
    R = t7_read_series(fullfile(workdir, sprintf('ser_%d.txt', i)));
    N = R.N;
    % gli ingressi che il DUT ha ricevuto: stato fisico registrato dal TB, quantizzato come dal TB
    X = double(fi([R.s(1:N).'; R.v(1:N).'; R.dv(1:N).'; R.vl(1:N).'], 1, 32, 20, FM));
    A = t7_block_replay(X, hold);

    bad = find(A(:) ~= R.a(1:N));
    nExact = nExact + numel(bad); nTot = nTot + N;
    if ~isempty(bad) && isempty(first.scen)
      first.scen = idx(i); first.k = bad(1);
      first.rtl = R.a(bad(1)); first.blk = A(bad(1));
    end

    P = R.params(1:N,:);
    nr = sum(any(P < LO | P > HI, 2));
    nRange = nRange + nr;
    if nr > 0, rangeScen(end+1) = idx(i); end %#ok<AGROW>

    rep = sum(all(P(2:end,:) == P(1:end-1,:), 2));
    nRep = nRep + rep;
    if rep > 0, repScen(end+1) = idx(i); end %#ok<AGROW>

    fprintf('  scen %2d: N=%3d  T7-EXACT %d/%d  fuori-dominio %d  params ripetuti %d\n', ...
            idx(i), N, numel(bad), N, nr, rep);
  end

  V = struct('nExact',nExact,'nTot',nTot,'nRange',nRange,'rangeScen',rangeScen, ...
             'nRep',nRep,'repScen',repScen,'first',first,'hold',hold);

  fprintf('T7-EXACT     : %d / %d disallineamenti su accel (RTL vs BLOCCO)\n', nExact, nTot);
  fprintf('PARAM-RANGE  : %d control-step con parametri fuori dai limiti del decode', nRange);
  if nRange > 0, fprintf('  (scenari: %s)', mat2str(rangeScen)); end
  fprintf('\n');
  fprintf('NO-REPEAT    : %d control-step con i 5 parametri ripetuti', nRep);
  if nRep > 0, fprintf('  (scenari: %s)', mat2str(repScen)); end
  fprintf('\n');
  if nExact > 0
    fprintf('  primo disallineamento: scenario %d, control-step %d: RTL=%.17g blocco=%.17g\n', ...
            first.scen, first.k, first.rtl, first.blk);
  end
end
