function finalize_descriptions()
%FINALIZE_DESCRIPTIONS  Applica al .slx riordinato le descrizioni concise (single-source):
%  - Tier + ACC-IIDM: rigenerati dai loro builder (build_tier_configurable / build_acc_iidm_block), che
%    prendono la Description dalle funzioni *_description concise. Tier e' ricostruito con la SUA config
%    ADV corrente (letta dagli slider) per non resettarla.
%  - 4 Campioni: set_param via champ_description (build_library ricrea la libreria da zero -> non
%    eseguibile sul .slx riordinato).
%  LUT e ACC_IIDM_M hanno gia' la descrizione concisa (Run A / set_param precedente).
  here=fileparts(mfilename('fullpath')); cd(here);
  lib='snn_champions_lib'; if bdIsLoaded(lib), close_system(lib,0); end
  load_system(lib);
  mo=Simulink.Mask.get([lib '/Donatello_Tier']);
  fld={'nV','nfat','nacc','naccw','nraw','nw'}; nf=zeros(1,6);
  for k=1:6, nf(k)=round(str2double(mo.getParameter(fld{k}).Value)); end
  fprintf('Tier ADV nf corrente = %s (preservata nel rebuild)\n', mat2str(nf));
  close_system(lib,0);
  build_tier_configurable(nf);   % Tier: desc concisa + ADV preservata
  build_acc_iidm_block();        % ACC-IIDM: desc concisa
  load_system(lib); set_param(lib,'Lock','off');
  for nm={'Donatello','Leonardo','Michelangelo','Raffaello'}
    set_param([lib '/' nm{1}],'Description',champ_description(nm{1}));
  end
  set_param(lib,'EnableLBRepository','on'); save_system(lib); close_system(lib,0);
  fprintf('OK: descrizioni finalizzate (Tier+ACC-IIDM single-source; 4 Campioni via champ_description)\n');
end
