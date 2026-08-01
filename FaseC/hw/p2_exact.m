function R = p2_exact(workdir, nscen, nveh, hold, outjson)
%P2_EXACT  Cancello sull'anello chiuso del plotone RTL.
%
%  Per OGNI veicolo di OGNI scenario: si ripilota il BLOCCO COMPOSTO sugli ingressi che quel
%  DUT ha EFFETTIVAMENTE ricevuto (registrati dal testbench) e si confronta l'accel bit per bit.
%
%  ⚠️ Il riferimento e' il BLOCCO, non P1. In P1 l'accelerazione e' float32 CONTINUA, nell'RTL
%     e' quantizzata a sfix13_En8: misurato, le accel di P1 non sono multipli di 1/256 e distano
%     in mediana il 25%% di un LSB. I due non calcolano la stessa grandezza, quindi confrontarli
%     bit per bit non e' possibile -- e non e' un difetto, e' come sono fatti.
%
%  NON e' circolare, per la stessa ragione di T7-EXACT: questo cancello non usa il plant (gli
%  ingressi sono quelli registrati) e PLATOON-PAR non usa il DUT. Plant corretto + DUT corretto
%  => anello corretto.
%
%  Cio' che questo cancello aggiunge rispetto a T7-EXACT (gia' 0 su 58 522, un veicolo solo):
%  che QUATTRO istanze parallele, ciascuna col proprio stato ricorrente, non si disturbano.
%
%  workdir : la work-dir di run_p2.sh (contiene ser_loop/)
%  nscen   : quanti scenari
%  nveh    : veicoli per scenario
%  hold    : clock per control-step usati dal testbench (deve superare la latenza, 555)
%  outjson : percorso dell'artefatto (opzionale)

  if nargin < 4 || isempty(hold), hold = 700; end
  if nargin < 5, outjson = ''; end
  FM = fimath('RoundingMethod','Floor','OverflowAction','Saturate');

  nExact = 0; nTot = 0; first = struct('scen',[],'veh',[],'k',[],'rtl',[],'blk',[]);
  perScen = zeros(nscen, 1);

  for i = 1:nscen
    f = fullfile(workdir, 'ser_loop', sprintf('ser_%d.txt', i));
    assert(exist(f,'file')==2, 'P2-ABORT: serie mancante %s', f);
    S = p2_read_series(f, nveh);

    for j = 1:nveh
      % Gli ingressi che il DUT j ha ricevuto, quantizzati come li ha quantizzati il testbench.
      X = double(fi([S.gap(:,j).'; S.v(:,j).'; S.dv(:,j).'; S.vl(:,j).'], 1, 32, 20, FM));
      A = t7_block_replay(X, hold);

      bad = find(A(:) ~= S.a(:,j));
      nTot = nTot + numel(A);
      nExact = nExact + numel(A) - numel(bad);
      perScen(i) = perScen(i) + numel(bad);
      if ~isempty(bad) && isempty(first.scen)
        k = bad(1);
        first = struct('scen', i, 'veh', j, 'k', k, 'rtl', S.a(k,j), 'blk', A(k));
      end
    end
    fprintf('P2EX scen %d/%d  disallineati finora: %d\n', i, nscen, nTot - nExact);
  end

  R = struct('n_confronti', nTot, 'n_esatti', nExact, 'n_disallineati', nTot - nExact, ...
             'bit_esatto', nTot == nExact, 'n_scenari', nscen, 'n_vehicles', nveh, ...
             'scenari_rossi', find(perScen > 0).', 'primo_scarto', first);

  fprintf('\nP2-EXACT: %d/%d bit-esatti su %d scenari x %d veicoli\n', ...
          nExact, nTot, nscen, nveh);
  if ~R.bit_esatto
    fprintf('  primo scarto: scenario %d veicolo %d passo %d  rtl=%d blocco=%d\n', ...
            first.scen, first.veh, first.k, first.rtl, first.blk);
  end

  if ~isempty(outjson)
    p2_write_json(outjson, R);
    fprintf('  artefatto: %s\n', outjson);
  end
end
