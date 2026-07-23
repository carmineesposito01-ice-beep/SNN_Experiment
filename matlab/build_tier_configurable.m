function build_tier_configurable()
%BUILD_TIER_CONFIGURABLE  Aggiunge a snn_champions_lib.slx il blocco UNICO configurabile Donatello_Tier:
%  un Variant Subsystem con 3 varianti tier (SLOW/BALANCED/FAST, chart split splitpipe LUT-64) + una
%  MASK con menu a tendina TIER. HDL Coder genera SOLO la variante selezionata (VariantActivationTime=
%  'update diagram'): equivalente al blocco separato corrispondente (provato: 0 diff logiche).
%  Riusa i mattoni condivisi (mount_split/snn_chart_code/dec_chart_code). NON tocca gli altri blocchi.
  here = fileparts(mfilename('fullpath')); cd(here);
  gen_b2_rom('Donatello');
  srcRom   = fileread('b2_rom_active.m');
  srcTypes = fileread('snn_types.m');
  srcLut   = [fileread('snn_decode_lut.m') newline newline ...
              fileread('decode_a.m')  newline newline fileread('decode_a1.m') newline newline ...
              fileread('decode_a2.m') newline newline fileread('decode_b.m')  newline newline ...
              fileread('decode_b1.m') newline newline fileread('decode_b2.m') newline newline ...
              fileread('decode_c.m')  newline newline fileread('decode_c1.m') newline newline ...
              fileread('decode_c2.m')];
  d = load('champions_export.mat'); champs = d.champions;
  if iscell(champs), champs = [champs{:}]; end
  c = champs(find(arrayfun(@(x) strcmp(char(string(x.name)),'Donatello'), champs),1));
  nrm = double(c.norm(:));

  tiers = {'SLOW','snn_variants/snn_b2_fsm_R2.m','fused'
           'BALANCED','snn_variants/snn_b2_fsm_R5.m','p3'
           'FAST','snn_variants/snn_b2_fsm_R9.m','p5'};
  in_names={'s','v','dv','v_l'}; out_names={'v0','T','s0','a','b'};

  lib='snn_champions_lib'; libfile=fullfile(here,[lib '.slx']);
  assert(isfile(libfile), '%s inesistente', libfile);
  if bdIsLoaded(lib), close_system(lib,0); end
  load_system(libfile); set_param(lib,'Lock','off');

  sub=[lib '/Donatello_Tier'];
  if getSimulinkBlockHandle(sub)>0, delete_block(sub); end
  add_block('built-in/Subsystem', sub, 'Position', [300,300,520,380]);
  for j=1:4, add_block('built-in/Inport',  [sub '/' in_names{j}],  'Port', num2str(j)); end
  for j=1:5, add_block('built-in/Outport', [sub '/' out_names{j}], 'Port', num2str(j)); end

  vs=[sub '/VS']; add_block('simulink/Ports & Subsystems/Variant Subsystem', vs);
  if getSimulinkBlockHandle([vs '/Subsystem'])>0, delete_block([vs '/Subsystem']); end
  for bt = {'Inport','Outport'}
    t = find_system(vs,'SearchDepth',1,'BlockType',bt{1});
    for i=1:numel(t), delete_block(t{i}); end
  end
  for j=1:4, add_block('built-in/Inport',  [vs '/' in_names{j}],  'Port', num2str(j)); end
  for j=1:5, add_block('built-in/Outport', [vs '/' out_names{j}], 'Port', num2str(j)); end
  for j=1:4, add_line(sub, [in_names{j} '/1'], ['VS/' num2str(j)], 'autorouting','on'); end
  for j=1:5, add_line(sub, ['VS/' num2str(j)], [out_names{j} '/1'], 'autorouting','on'); end

  for i=1:size(tiers,1)
    nm=tiers{i,1}; srcFsm=fileread(fullfile(here,tiers{i,2})); dec=tiers{i,3};
    v=[vs '/' nm]; add_block('built-in/Subsystem', v);
    mount_split(v, in_names, out_names, ...
      snn_chart_code(srcRom,srcTypes,srcFsm,nrm,true), ...
      dec_chart_code(srcLut,dec,64,'shared'));
    set_param(v, 'VariantControl', sprintf('TIER==%d', i));   % TIER numerico (indice del popup); le
    fprintf('  variante %s montata (VariantControl TIER==%d)\n', nm, i);   % condizioni variant NON accettano funzioni (es. strcmp)
  end
  set_param(vs, 'VariantControlMode','expression', 'VariantActivationTime','update diagram');

  % MASK con menu a tendina TIER (la parte "cliccabile"). Evaluate off -> TIER e' la stringa scelta,
  % usata dai VariantControl strcmp(TIER,'SLOW'|'BALANCED'|'FAST').
  m = Simulink.Mask.create(sub);
  % Evaluate='on': il popup restituisce l'INDICE 1-based (1=SLOW,2=BALANCED,3=FAST), usato dai
  % VariantControl TIER==1/2/3. (Con 'off' TIER sarebbe la stringa e servirebbe strcmp, non ammesso.)
  m.addParameter('Name','TIER','Prompt','Tier (trade-off area/margine)', ...
                 'Type','popup','TypeOptions',{'SLOW','BALANCED','FAST'}, ...
                 'Evaluate','on','Value','SLOW');
  m.Description = tier_configurable_description();
  set_param(sub, 'MaskSelfModifiable','on');

  set_param(lib, 'EnableLBRepository','on');
  save_system(lib, libfile); close_system(lib,0);
  fprintf('OK: Donatello_Tier (configurabile, 3 varianti + mask TIER) aggiunto a %s.slx\n', lib);
end

function s = tier_configurable_description()
  L = {
    'Donatello_Tier - SNN car-following (champion Donatello) CONFIGURABILE.'
    'Un solo blocco, un menu TIER: SLOW / BALANCED / FAST. La scelta seleziona la variante attiva'
    '(Variant Subsystem, VariantActivationTime=update diagram): HDL Coder genera SOLO il tier scelto,'
    'identico al blocco separato Donatello_<TIER> (provato bit-exact modulo nomi).'
    ''
    'TIER: SLOW = R2/fused (area minima, ~30 MHz io-timed, 342 clk) · BALANCED = R5/p3 (~58 MHz, 364) ·'
    '      FAST = R9/p5 (margine massimo, ~74 MHz, 406). Stessi 5 parametri, diverso profilo risorse/Fmax.'
    ''
    'I/O fisico (fixed >=20 bit frazionari): s,v,dv,v_l -> v0,T,s0,a,b. Edge-triggered, niente start/done.'
    'Self-contained. Rigenerazione: build_tier_configurable.m (NON modificare a mano).'
  };
  s = strjoin(L, newline);
end
