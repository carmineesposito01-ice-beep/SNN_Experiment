function build_snn_iidm_block()
%BUILD_SNN_IIDM_BLOCK  Aggiunge a snn_champions_lib.slx il blocco COMPOSTO Donatello_SNN_IIDM:
%  Donatello_Tier@BALANCED (SNN estimatrice) + allineamento a ritardo-appaiato + ACC-IIDM (IIDM R17).
%  s,v,dv,v_l -> accel. Sostituisce il monolite Donatello_ACC_IIDM_M (deprecato); qui i due blocchi
%  standalone VERIFICATI sono composti (tracciabile).
%
%  ALLINEAMENTO (align): tiene i 4 fisici finche' i 5 params non cambiano (= la SNN time-mux ha finito,
%  ~406 clk), poi li rilascia INSIEME ai params -> i 9 ingressi dell'ACC-IIDM cambiano allo STESSO clock
%  -> 1 inferenza/control-step, il filtro OU aggiorna una volta. Senza allineamento i 4 fisici cambierebbero
%  a inizio control-step e i params ~406 clk dopo -> DOPPIO edge -> OU aggiornato due volte (bug silenzioso).
%  Robusto: si aggancia all'EVENTO "params nuovi", non a una latenza cablata.
  here=fileparts(mfilename('fullpath')); cd(here);
  lib='snn_champions_lib'; libfile=fullfile(here,[lib '.slx']);
  assert(isfile(libfile), '%s inesistente', libfile);
  if bdIsLoaded(lib), close_system(lib,0); end
  load_system(libfile); set_param(lib,'Lock','off');

  sub=[lib '/Donatello_SNN_IIDM'];
  if getSimulinkBlockHandle(sub)>0, delete_block(sub); end
  add_block('built-in/Subsystem', sub, 'Position',[300,650,560,780], 'Description', snn_iidm_description());
  in={'s','v','dv','v_l'};
  for j=1:4, add_block('built-in/Inport',[sub '/' in{j}],'Port',num2str(j)); end
  add_block('built-in/Outport',[sub '/accel'],'Port','1');

  % --- SNN: Donatello_Tier @ BALANCED / nfrac 13 ---
  add_block([lib '/Donatello_Tier'],[sub '/Tier']);
  set_param([sub '/Tier'],'TIER','BALANCED','NFRAC','13');
  for j=1:4, add_line(sub,[in{j} '/1'],['Tier/' num2str(j)],'autorouting','on'); end

  % --- allineamento: align(9 in) -> 4 fisici appaiati ---
  add_block('simulink/User-Defined Functions/MATLAB Function',[sub '/align']);
  ch=sfroot().find('-isa','Stateflow.EMChart','Path',[sub '/align']); ch.Script=align_code();
  for j=1:4, add_line(sub,[in{j} '/1'],['align/' num2str(j)],'autorouting','on'); end        % fisici -> align 1-4
  for j=1:5, add_line(sub,['Tier/' num2str(j)],['align/' num2str(j+4)],'autorouting','on'); end % params -> align 5-9

  % --- controllore: ACC-IIDM (9 in: fisici appaiati 1-4 + params 5-9) ---
  add_block([lib '/ACC-IIDM'],[sub '/ACC']);
  for j=1:4, add_line(sub,['align/' num2str(j)],['ACC/' num2str(j)],'autorouting','on'); end   % appaiati -> ACC 1-4
  for j=1:5, add_line(sub,['Tier/' num2str(j)],['ACC/' num2str(j+4)],'autorouting','on'); end   % params  -> ACC 5-9
  add_line(sub,'ACC/1','accel/1','autorouting','on');

  % CANCELLO: il blocco deve avere le porte di clock. Senza questa asserzione il costruttore stampa
  % "OK" anche quando produce un GUSCIO combinatorio con l'uscita a massa -- successo dichiarato su un
  % artefatto vuoto. (Successo davvero verificato: 2026-07-30, dopo che era accaduto.)
  set_param(lib,'EnableLBRepository','on'); save_system(lib,libfile);
  p = get_param(sub,'Ports');
  assert(p(1) == 4 && p(2) == 1, 'porte del composto errate: in=%d out=%d (attese 4/1)', p(1), p(2));
  lines = find_system(sub,'SearchDepth',1,'LookUnderMasks','all','FollowLinks','on','FindAll','on','Type','line');
  assert(numel(lines) >= 18, 'collegamenti insufficienti nel composto: %d (attesi >=18)', numel(lines));

  try, Simulink.BlockDiagram.arrangeSystem(sub); catch ME, warning('arrange: %s', ME.message); end
  set_param(lib,'EnableLBRepository','on'); save_system(lib,libfile); close_system(lib,0);
  fprintf('OK: Donatello_SNN_IIDM (Tier@BALANCED + align + ACC-IIDM) aggiunto a %s.slx\n', lib);
end

function code=align_code()
  L={ 'function [sa,va,dva,vla] = align(s,v,dv,vl, v0,T,s0,a,b)'
      '%#codegen'
      '% Ritardo-appaiato: tiene i 4 fisici finche'' i params (dalla SNN) non cambiano, poi li rilascia'
      '% INSIEME ai params -> i 9 ingressi ACC-IIDM cambiano sincroni (1 inferenza/control-step, OU una volta).'
      '  persistent sh vh dh vlh v0p Tp s0p ap bp started'
      '  if isempty(started)'
      '    sh=s; vh=v; dh=dv; vlh=vl; v0p=v0; Tp=T; s0p=s0; ap=a; bp=b; started=true;'
      '  end'
      '  if v0~=v0p || T~=Tp || s0~=s0p || a~=ap || b~=bp   % params nuovi -> SNN ha finito -> rilascia appaiato'
      '    sh=s; vh=v; dh=dv; vlh=vl;'
      '  end'
      '  v0p=v0; Tp=T; s0p=s0; ap=a; bp=b;'
      '  sa=sh; va=vh; dva=dh; vla=vlh;'
      'end' };
  code=strjoin(L,newline);
end

function d=snn_iidm_description()
  L={ 'Donatello_SNN_IIDM - controllore car-following COMPLETO, COMPOSTO: Donatello_Tier@BALANCED (SNN) + ACC-IIDM (IIDM R17).'
      ''
      'FUNZIONE: s,v,dv,v_l -> accel. La SNN (Tier@BALANCED) stima i 5 parametri IDM; l''ACC-IIDM li usa per'
      'l''accelerazione. Composizione dei DUE blocchi standalone gia'' verificati (tracciabile) -> sostituisce il'
      'monolite Donatello_ACC_IIDM_M (deprecato).'
      ''
      'ALLINEAMENTO (ritardo-appaiato): i 4 ingressi fisici sono tenuti finche'' i 5 params non cambiano (= la SNN'
      'time-mux ha finito, ~406 clk), poi rilasciati INSIEME ai params -> i 9 ingressi dell''ACC-IIDM cambiano'
      'sincroni -> 1 inferenza/control-step, il filtro OU aggiorna una volta. Senza allineamento: doppio edge.'
      ''
      'I/O fisico (fixed >=20 bit frazionari): s,v,dv,v_l -> accel. Edge-triggered. Rigen.: build_snn_iidm_block.m.'
      'Blocco di riferimento per la Fase B2.0 (harness SNN+IIDM).' };
  d=strjoin(L,newline);
end
