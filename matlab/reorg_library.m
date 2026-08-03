function reorg_library()
%REORG_LIBRARY  Riordina snn_champions_lib al set-milestone di 8 blocchi.
%  TIENE:   Donatello / Leonardo / Michelangelo / Raffaello (4 Campioni comportamentali, double),
%           Donatello_LUT (combinato, popup NLUT), Donatello_Tier (configurabile),
%           ACC-IIDM (controllore IIDM R17 standalone), Donatello_ACC_IIDM_M (controllore R17 completo
%           SNN+IIDM, deployato).
%  RIMUOVE: Donatello_Champion (assorbito nel LUT combinato, default N=64), Donatello_LUT{16..512}
%           (assorbiti nel combinato), Donatello_SLOW/BALANCED/FAST (assorbiti in Donatello_Tier),
%           Donatello_ACC_IIDM (SP3 nativo, superato da ACC-IIDM + ACC_IIDM_M).
%  DIFENSIVO: verifica che TUTTI gli 8 keeper esistano PRIMA di rimuovere qualcosa; controlla che il set
%             finale sia ESATTAMENTE gli 8 keeper. Se qualcosa non torna -> errore, niente save.
  here=fileparts(mfilename('fullpath')); cd(here);
  lib='snn_champions_lib'; libfile=fullfile(here,[lib '.slx']);
  keep={'Donatello','Leonardo','Michelangelo','Raffaello', ...
        'Donatello_LUT','Donatello_Tier','ACC-IIDM','Donatello_ACC_IIDM_M'};
  remove={'Donatello_Champion','Donatello_LUT16','Donatello_LUT32','Donatello_LUT64', ...
          'Donatello_LUT128','Donatello_LUT256','Donatello_LUT512', ...
          'Donatello_SLOW','Donatello_BALANCED','Donatello_FAST','Donatello_ACC_IIDM'};
  assert(isfile(libfile), '%s inesistente', libfile);
  if bdIsLoaded(lib), close_system(lib,0); end
  load_system(libfile); set_param(lib,'Lock','off');

  % GUARDIA: tutti i keeper devono esistere PRIMA di toccare qualcosa
  for i=1:numel(keep)
    assert(getSimulinkBlockHandle([lib '/' keep{i}])>0, 'KEEPER assente: %s -- ABORT (niente rimozione)', keep{i});
  end

  for i=1:numel(remove)
    b=[lib '/' remove{i}];
    if getSimulinkBlockHandle(b)>0, delete_block(b); fprintf('  rimosso  %s\n', remove{i});
    else, fprintf('  (assente) %s\n', remove{i}); end
  end

  % VERIFICA set finale = esattamente i keeper
  blks=find_system(lib,'SearchDepth',1,'BlockType','SubSystem');
  names=sort(cellfun(@(b) get_param(b,'Name'), blks, 'uni',0));
  expected=sort(keep);
  assert(isequal(names(:), expected(:)), ...
         'set finale != atteso.\n  trovato:  {%s}\n  atteso:   {%s}', strjoin(names,', '), strjoin(expected,', '));

  set_param(lib,'EnableLBRepository','on');
  save_system(lib,libfile); close_system(lib,0);
  fprintf('OK: libreria riordinata a %d blocchi: %s\n', numel(names), strjoin(names,', '));
end
