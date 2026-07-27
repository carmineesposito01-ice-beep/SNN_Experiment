function build_tier_configurable(nf)
%BUILD_TIER_CONFIGURABLE  Aggiunge a snn_champions_lib.slx il blocco UNICO configurabile Donatello_Tier:
%  un Variant Subsystem con 3 varianti tier (SLOW/BALANCED/FAST, chart split splitpipe LUT-64) x 4 livelli
%  NFRAC (13/8/5/2) = 12 varianti "Base", PIU' 3 varianti "ADV" (Modalita' Avanzata, nfrac PER-CAMPO cotti a
%  `nf`). MASK con: TIER + NFRAC (menu Base) + checkbox ADV + 6 slider per-campo (nV..nw). HDL Coder genera
%  SOLO la variante selezionata. Riusa i mattoni condivisi (mount_split/snn_chart_code/dec_chart_code).
%
%  ADV (Modalita' Avanzata) = Approccio A ROBUSTO: la variante <tier>_ADV e' cotta CONCRETA a `nf` al build
%  (tipi qz_snn_types_mp per-campo, come le varianti Base cuociono snn_types). La checkbox ADV la SELEZIONA
%  (variant control -> ammesso sui link risolti); il callback tier_adv_cb fa SOLO visibilita' (niente
%  rigenerazione chart live: quella non funziona su un blocco linkato -> muro Simulink, verificato con sonda).
%  Per cambiare la config ADV: ri-esegui build_tier_configurable([nV nfat nacc naccw nraw nw]).
%
%  nf (opz., default [13 13 13 13 13 13] = piena precisione, bit-exact): config Modalita' Avanzata per-campo.
  if nargin < 1 || isempty(nf), nf = [13 13 13 13 13 13]; end
  nf = round(double(nf(:)).');
  assert(numel(nf)==6 && all(nf>=1 & nf<=13), 'nf: 6 interi in [1,13] [V fatigue acc accw raw w]');
  here = fileparts(mfilename('fullpath')); cd(here);
  gen_b2_rom('Donatello');
  srcRom   = fileread('b2_rom_active.m');
  srcTypes = fileread('snn_types.m');
  % Modalita' Avanzata: inietta ANCHE qz_snn_types_mp (tipi per-campo) nella chart ADV
  srcTypesMp = [srcTypes newline newline fileread(fullfile('Quantizzation_Study','qz_snn_types_mp.m'))];
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
  nfracs = [13 8 5 2];   % livelli canonici Base (13=piena precisione, bit-exact)
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
  % rimuovi OGNI sottosistema-scelta default del template (Subsystem/Subsystem1/...): altrimenti ne resta
  % uno inerte (VariantControl=false) che sporca il VS. (Prima si cancellava solo quello chiamato 'Subsystem'.)
  hVS = getSimulinkBlockHandle(vs);
  kids = find_system(vs,'SearchDepth',1,'MatchFilter',@Simulink.match.allVariants,'BlockType','SubSystem');
  for i=1:numel(kids), if getSimulinkBlockHandle(kids{i}) ~= hVS, delete_block(kids{i}); end; end
  for bt = {'Inport','Outport'}
    t = find_system(vs,'SearchDepth',1,'BlockType',bt{1});
    for i=1:numel(t), delete_block(t{i}); end
  end
  for j=1:4, add_block('built-in/Inport',  [vs '/' in_names{j}],  'Port', num2str(j)); end
  for j=1:5, add_block('built-in/Outport', [vs '/' out_names{j}], 'Port', num2str(j)); end
  for j=1:4, add_line(sub, [in_names{j} '/1'], ['VS/' num2str(j)], 'autorouting','on'); end
  for j=1:5, add_line(sub, ['VS/' num2str(j)], [out_names{j} '/1'], 'autorouting','on'); end

  % 3 tier x 4 livelli nfrac = 12 varianti BASE (snn_types cotto concreto) + 1 variante ADV per tier
  % (qz_snn_types_mp per-campo cotto a nf). VariantControl: Base = ADV==0 && TIER && NFRAC ; ADV = ADV==1 && TIER.
  % A nfrac=13 (Base) e a nf=[13x6] (ADV) la sostituzione e' NO-OP -> variante bit-exact storica.
  for ti=1:size(tiers,1)
    nm=tiers{ti,1}; srcFsm=fileread(fullfile(here,tiers{ti,2})); dec=tiers{ti,3};
    snnRef = snn_chart_code(srcRom,srcTypes,srcFsm,nrm,true);
    for ni=1:numel(nfracs)
      nlev = nfracs(ni);
      snnCode = regexprep(snnRef, "snn_types\(\s*'fixed'\s*,\s*13\s*\)", sprintf("snn_types('fixed', %d)", nlev));
      v=[vs '/' sprintf('%s_n%d', nm, nlev)]; add_block('built-in/Subsystem', v);
      mount_split(v, in_names, out_names, snnCode, dec_chart_code(srcLut,dec,64,'shared'));
      set_param(v, 'VariantControl', sprintf('ADV==0 && TIER==%d && NFRAC==%d', ti, ni));
    end
    % variante Modalita' Avanzata (per-campo): tipi qz_snn_types_mp cotti a nf ; attiva quando ADV==1
    snnRefMp   = snn_chart_code(srcRom,srcTypesMp,srcFsm,nrm,true);
    snnCodeAdv = regexprep(snnRefMp, "snn_types\(\s*'fixed'\s*,\s*13\s*\)", ...
                 sprintf("qz_snn_types_mp('fixed', [%d %d %d %d %d %d])", nf(1),nf(2),nf(3),nf(4),nf(5),nf(6)));
    va=[vs '/' sprintf('%s_ADV', nm)]; add_block('built-in/Subsystem', va);
    mount_split(va, in_names, out_names, snnCodeAdv, dec_chart_code(srcLut,dec,64,'shared'));
    set_param(va, 'VariantControl', sprintf('ADV==1 && TIER==%d', ti));
    fprintf('  tier %s montato x nfrac %s + ADV %s\n', nm, mat2str(nfracs), mat2str(nf));
  end
  set_param(vs, 'VariantControlMode','expression', 'VariantActivationTime','update diagram');

  % MASK: TIER + NFRAC (menu Base) + ADV (checkbox) + 6 slider per-campo. Evaluate='on' su tutti (indici/valori).
  m = Simulink.Mask.create(sub);
  m.addParameter('Name','TIER','Prompt','Tier (trade-off area/margine)', ...
                 'Type','popup','TypeOptions',{'SLOW','BALANCED','FAST'}, ...
                 'Evaluate','on','Value','BALANCED');
  m.addParameter('Name','NFRAC','Prompt','nfrac Base (13 pieno / 8 / 5 / 2)', ...
                 'Type','popup','TypeOptions',{'13','8','5','2'}, ...
                 'Evaluate','on','Value','13');
  % Modalita' Avanzata: checkbox ADV (seleziona le varianti ADV) + 6 slider (Range 1..13, step 1) che MOSTRANO
  % la config cotta. Il callback tier_adv_cb gestisce solo la visibilita' (sicuro su link).
  m.addParameter('Name','ADV','Prompt','Modalita'' Avanzata (nfrac per-campo)', ...
                 'Type','checkbox','Value','off','Evaluate','on','Callback','tier_adv_cb(gcb)');
  fld = {'nV','V (membrana)'; 'nfat','fatigue (soglia)'; 'nacc','acc (ingresso)'; ...
         'naccw','accw (wide)'; 'nraw','raw (readout)'; 'nw','w (pesi po2)'};
  for k=1:6
    ps = m.addParameter('Name',fld{k,1},'Prompt',['nfrac ' fld{k,2}], ...
                        'Type','slider','Value',num2str(nf(k)),'Evaluate','on','Visible','off', ...
                        'Callback','tier_nfrac_round_cb(gcb)');   % vincola a INTERO (StepSize non copre il digitato)
    ps.Range = [1 13]; ps.StepSize = 1;
  end
  m.Description = tier_configurable_description();
  set_param(sub, 'Description', tier_configurable_description());   % anche block-level (Block Properties)
  set_param(sub, 'MaskSelfModifiable','on');

  % LAYOUT: auto-arrangia i diagrammi prima di salvare, cosi' il blocco e' ordinato su disco
  % (ingressi a sinistra -> VS -> uscite a destra, allineati; niente blocchi sparsi). Solo grafica.
  try, Simulink.BlockDiagram.arrangeSystem(sub); catch ME, warning('arrange %s: %s', sub, ME.message); end
  try, Simulink.BlockDiagram.arrangeSystem(vs);  catch ME, warning('arrange %s: %s', vs, ME.message); end

  set_param(lib, 'EnableLBRepository','on');
  save_system(lib, libfile); close_system(lib,0);
  fprintf('OK: Donatello_Tier (Base 12 var + ADV nf=%s) aggiunto a %s.slx\n', mat2str(nf), lib);
end

function s = tier_configurable_description()
  L = {
    'Donatello_Tier - SNN car-following (champion Donatello), tier di trade-off CONFIGURABILE.'
    ''
    'FUNZIONE: stima i 5 parametri IDM (v0, T, s0, a, b) dallo stato di car-following (s, v, dv, v_l).'
    ''
    'MENU BASE: TIER (SLOW/BALANCED/FAST = area minima / compromesso / margine massimo) + NFRAC (bit'
    'frazionari del core: 13 = piena precisione bit-exact / 8 / 5 / 2 safety-only). La selezione attiva la'
    'variante (Variant Subsystem); HDL Coder genera SOLO quella, coi tipi fixed-point gia'' cotti.'
    ''
    'MODALITA'' AVANZATA (checkbox ADV): 6 nfrac per-campo [V fatigue acc accw raw w]; gli slider mostrano la'
    'config cotta. Solo acc/w scendono a 4 bit bit-exact (pesi po2, min 2^-4); area-ottimale [13 13 4 13 13 4].'
    'Per cambiarla: build_tier_configurable([...]) (la mask NON ri-cuoce da sola su un blocco linkato).'
    ''
    'I/O fisico fixed >=20 bit fraz.: s,v,dv,v_l -> v0,T,s0,a,b. Edge-triggered. Self-contained (la mask'
    'Avanzata richiede matlab/ sul path, callback tier_adv_cb). Rigenerazione: build_tier_configurable.m.'
  };
  s = strjoin(L, newline);
end
