function nStale = run_block_sync_check()
%RUN_BLOCK_SYNC_CHECK  I blocchi self-contained di `snn_champions_lib.slx` INLINANO i sorgenti veri
%  (letti da `build_hdl_variants` a build-time). Questo è ciò che li rende autosufficienti — ma crea
%  un rischio: se qualcuno modifica un sorgente e **non** rilancia `build_hdl_variants`, i blocchi
%  restano indietro **in silenzio** e continuano a girare col codice vecchio.
%
%  Questo cancello confronta il codice REALMENTE dentro ogni chart con i sorgenti attuali sul disco.
%  Atteso: **0 blocchi stale**. Se fallisce: `build_hdl_variants()`.
%
%  Contesto: il bug §2.1 (`snn_b2_fsm` non bit-exact) è vissuto mesi perché i cancelli non vedevano.
%  Un blocco stale sarebbe la stessa trappola in versione libreria.
  here = fileparts(mfilename('fullpath'));
  srcs   = {'snn_b2_fsm.m', 'snn_types.m', 'b2_rom_active.m'};  % inlinati in TUTTI i blocchi generati
  srcSp2 = {'acc_iidm_open.m'};                                 % in piu': solo in Donatello_ACC_IIDM (SP2)
  if ~isfile(fullfile(here, 'b2_rom_active.m'))
    gen_b2_rom('Donatello');            % la ROM e' generata: senza, il confronto non ha senso
  end
  nrm = @(s) regexprep(s, '\r\n?', newline);                   % fine-riga irrilevanti
  txt = containers.Map();
  allSrcs = [srcs, srcSp2];
  for i = 1:numel(allSrcs)
    txt(allSrcs{i}) = nrm(fileread(fullfile(here, allSrcs{i})));
  end

  lib = 'snn_champions_lib';
  if bdIsLoaded(lib), close_system(lib, 0); end
  load_system(fullfile(here, [lib '.slx']));
  blocks = find_system(lib, 'SearchDepth', 1, 'BlockType', 'SubSystem');
  % La chart NON si chiama sempre 'SNN' (in Donatello_ACC_IIDM e' 'SNN_ACC'): va cercata per PREFISSO
  % del path, non per nome. Cercandola per nome, find torna [] e il cancello esplode con un oscuro
  % "Dot indexing is not supported for variables of type double" invece di controllare il blocco.
  charts = sfroot().find('-isa', 'Stateflow.EMChart');
  cpath  = arrayfun(@(c) string(c.Path), charts);
  nStale = 0; nChecked = 0;
  for i = 1:numel(blocks)
    nm = strrep(blocks{i}, [lib '/'], '');
    k = find(startsWith(cpath, blocks{i} + "/"), 1);
    if isempty(k), continue; end                               % subsystem senza chart: non generato
    s = nrm(charts(k).Script);
    if ~contains(s, 'snn_b2_fsm(xn, start)'), continue; end     % i 4 base sono double: non inlinano
    nChecked = nChecked + 1;
    stale = {};
    for k = 1:numel(srcs)
      if ~contains(s, txt(srcs{k})), stale{end+1} = srcs{k}; end %#ok<AGROW>
    end
    if contains(s, 'acc_iidm_open(')                            % il blocco SP2 inlina anche l'IIDM
      for k = 1:numel(srcSp2)
        if ~contains(s, txt(srcSp2{k})), stale{end+1} = srcSp2{k}; end %#ok<AGROW>
      end
    end
    if isempty(stale)
      fprintf('  %-22s allineato\n', nm);
    else
      nStale = nStale + 1;
      fprintf('  %-22s **STALE** rispetto a: %s\n', nm, strjoin(stale, ', '));
    end
  end
  close_system(lib, 0);
  fprintf('blocchi self-contained controllati: %d — stale: %d\n', nChecked, nStale);
  assert(nChecked > 0, 'nessun blocco self-contained trovato in %s: eseguire build_hdl_variants', lib);
  assert(nStale == 0, ['%d blocchi inlinano codice VECCHIO rispetto ai sorgenti: eseguire ' ...
         'build_hdl_variants()'], nStale);
  fprintf('=== BLOCCHI SINCRONIZZATI COI SORGENTI ===\n');
end
