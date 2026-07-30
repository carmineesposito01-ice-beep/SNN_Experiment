function missing = check_synth_coverage(verbose)
%CHECK_SYNTH_COVERAGE  Cancello: ogni blocco DICHIARATO PRESCELTO ha una sintesi PROPRIA?
%
%  L'idoneità HDL NON si eredita dai componenti. `Donatello_SNN_IIDM` fu dichiarato il controllore
%  prescelto il 2026-07-28 e non venne sintetizzato per due fasi: il suo cammino critico attraversava il
%  confine non registrato fra Tier e ACC (36,4 MHz contro i ~50 e ~78 dei componenti presi da soli).
%  Nessuna verifica funzionale poteva vederlo — un cammino combinatorio lungo non altera un solo bit —
%  e infatti T7a era verde su 58 522 confronti bit-esatti. La sintesi e' l'UNICO livello che lo vede.
%
%  Questo controllo elenca i blocchi prescelti per cui NON risulta una sintesi registrata, cosi' che
%  "prescelto" significhi "caratterizzato" e non "assemblato da pezzi caratterizzati".
%
%  missing : cellstr dei blocchi senza sintesi propria (vuoto = tutto coperto)
  if nargin < 1, verbose = true; end
  here = fileparts(mfilename('fullpath'));
  root = fileparts(here);

  % I blocchi PRESCELTI e il file che ne registra la sintesi. Aggiungere qui ogni nuovo prescelto:
  % se non ha una riga, il cancello lo segnala.
  chosen = { ...
    'Donatello_Tier',      fullfile(root,'FaseB2.0','Harness_SNN','results','RESULTS_HW.md'); ...
    'Donatello_SNN_IIDM',  fullfile(root,'FaseB2.0','Harness_SNN_IIDM','results','RESULTS_HW.md'); ...
  };

  missing = {};
  for i = 1:size(chosen,1)
    blk = chosen{i,1}; rec = chosen{i,2};
    ok = isfile(rec);
    if ok
      txt = fileread(rec);
      ok = contains(txt, 'MHz');          % la scheda deve riportare una frequenza, non solo esistere
    end
    if verbose
      fprintf('  %-22s %s\n', blk, ternary(ok, 'sintesi registrata', '*** SENZA SINTESI PROPRIA ***'));
    end
    if ~ok, missing{end+1} = blk; end %#ok<AGROW>
  end

  if isempty(missing)
    fprintf('check_synth_coverage: OK — tutti i %d blocchi prescelti hanno una sintesi propria\n', size(chosen,1));
  else
    fprintf(['check_synth_coverage: %d blocchi prescelti SENZA sintesi propria: %s\n' ...
             '  L''idoneita'' HDL non si eredita dai componenti (HDL_PHASE §9).\n'], ...
            numel(missing), strjoin(missing, ', '));
  end
end

function o = ternary(c, a, b)
  if c, o = a; else, o = b; end
end
