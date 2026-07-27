function build_lut_configurable()
%BUILD_LUT_CONFIGURABLE  Aggiunge a snn_champions_lib.slx il blocco UNICO configurabile Donatello_LUT:
%  un Variant Subsystem con 6 varianti = il forward campione deployato (snn_b2_fsm) con decode a LUT di
%  N punti, N in {16,32,64,128,256,512}. Architettura SPLITPIPE (SNN col registro operandi | DEC) + decode
%  a 5 fasi (p5) = l'architettura ATTUALE, la stessa di Donatello_Tier (veloce: toglie il muro d'ingresso
%  ingresso->normalize->go). Gli studi LUT storici usavano 'split' (per la PRECISIONE, non la velocita');
%  qui si adotta la corrente. Ogni variante e' funzionalmente BIT-EXACT al riferimento (MEX+snn_decode_lut
%  (.,N)) - provato sul dataset da run_lut_ref_gate. MASK: un popup NLUT; HDL Coder genera SOLO la scelta.
%
%  SOSTITUISCE i 6 blocchi Donatello_LUT{N} + Donatello_Champion (il default N=64 E' il champion deployato:
%  stesso decode del top snn_top_b2, vedi DECODE_LUT_SWEEP.md). Il forward e' identico in tutte le varianti;
%  cambia solo la dimensione della LUT di decode -> asse di studio dimensione-LUT / accuratezza / area.
%
%  Riusa i mattoni condivisi (snn_chart_code / dec_chart_code / mount_split): single-source, niente copie a
%  mano. Self-contained (le chart inlinano i sorgenti VERI a build-time -> gira/genera VHDL senza .m esterni).
%  Rigenerazione: build_lut_configurable.m (NON modificare le chart a mano).
  here = fileparts(mfilename('fullpath')); cd(here);
  gen_b2_rom('Donatello');                       % ROM attiva = Donatello -> b2_rom_active.m
  srcRom   = fileread('b2_rom_active.m');
  srcTypes = fileread('snn_types.m');
  srcFsm   = fileread('snn_b2_fsm.m');           % forward campione deployato (lo stato corrente)
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

  Ns = [16 32 64 128 256 512];   % dimensioni LUT (indice 1..6 -> variant control NLUT)
  decVariant = 'p5';             % decode a 5 fasi (massima pipeline, come il tier FAST): l'asse di studio
                                 % e' la DIMENSIONE N della LUT, la profondita' del decode resta fissa.
  in_names={'s','v','dv','v_l'}; out_names={'v0','T','s0','a','b'};

  lib='snn_champions_lib'; libfile=fullfile(here,[lib '.slx']);
  assert(isfile(libfile), '%s inesistente', libfile);
  if bdIsLoaded(lib), close_system(lib,0); end
  load_system(libfile); set_param(lib,'Lock','off');

  sub=[lib '/Donatello_LUT'];
  if getSimulinkBlockHandle(sub)>0, delete_block(sub); end
  add_block('built-in/Subsystem', sub, 'Position', [300,300,520,380]);
  for j=1:4, add_block('built-in/Inport',  [sub '/' in_names{j}],  'Port', num2str(j)); end
  for j=1:5, add_block('built-in/Outport', [sub '/' out_names{j}], 'Port', num2str(j)); end

  vs=[sub '/VS']; add_block('simulink/Ports & Subsystems/Variant Subsystem', vs);
  % rimuovi OGNI sottosistema-scelta default del template (Subsystem/Subsystem1/...): altrimenti ne resta
  % uno inerte (VariantControl=false) che sporca il VS.
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

  % 6 varianti = stesso forward (snn_chart_code splitpipe) x decode LUT-N (dec_chart_code, N variabile).
  % VariantControl NLUT==indice: il popup con Evaluate='on' valuta al 1-based INDEX dell'opzione scelta.
  snnRef = snn_chart_code(srcRom,srcTypes,srcFsm,nrm,true);   % splitpipe (registro operandi): architettura attuale
  for ni=1:numel(Ns)
    N = Ns(ni);
    v=[vs '/' sprintf('LUT%d', N)]; add_block('built-in/Subsystem', v);
    mount_split(v, in_names, out_names, snnRef, dec_chart_code(srcLut, decVariant, N, 'shared'));
    set_param(v, 'VariantControl', sprintf('NLUT==%d', ni));
    fprintf('  variante LUT-%d montata (NLUT==%d)\n', N, ni);
  end
  set_param(vs, 'VariantControlMode','expression', 'VariantActivationTime','update diagram');

  % MASK: un solo popup NLUT (16/32/64/128/256/512), default 64 (il champion deployato). Evaluate='on' ->
  % il valore e' l'INDICE dell'opzione (usato dai variant control). Nessun callback: variante pura.
  m = Simulink.Mask.create(sub);
  m.addParameter('Name','NLUT','Prompt','Punti LUT decode (dimensione/accuratezza/area)', ...
                 'Type','popup','TypeOptions',{'16','32','64','128','256','512'}, ...
                 'Evaluate','on','Value','64');
  m.Description = lut_configurable_description();
  set_param(sub, 'Description', lut_configurable_description());   % anche block-level (Block Properties)

  try, Simulink.BlockDiagram.arrangeSystem(sub); catch ME, warning('arrange %s: %s', sub, ME.message); end
  try, Simulink.BlockDiagram.arrangeSystem(vs);  catch ME, warning('arrange %s: %s', vs, ME.message); end

  set_param(lib, 'EnableLBRepository','on');
  save_system(lib, libfile); close_system(lib,0);
  fprintf('OK: Donatello_LUT (6 varianti N=%s, default 64) aggiunto a %s.slx\n', mat2str(Ns), lib);
end

function s = lut_configurable_description()
  L = {
    'Donatello_LUT - SNN car-following (champion Donatello), decode a LUT CONFIGURABILE.'
    ''
    'FUNZIONE: stima i 5 parametri IDM (v0, T, s0, a, b) dallo stato di car-following (s, v, dv, v_l).'
    ''
    'MENU: popup NLUT = punti della LUT di decode della sigmoide (16/32/64/128/256/512). La selezione'
    'attiva la variante (Variant Subsystem); HDL Coder genera SOLO quella. DEFAULT 64 = il decode deployato'
    '(snn_top_b2): la LUT piu'' piccola sotto l''errore di quantizzazione gia'' accettato (DECODE_LUT_SWEEP.md).'
    ''
    'STUDIO dimensione-LUT: il forward e'' identico fra le varianti; l''accuratezza resta ~84% su N=16..512'
    'mentre l''area di sintesi cresce (~520->1732 LUT). Asse ortogonale a Donatello_Tier (tier/nfrac).'
    ''
    'ARCHITETTURA attuale: forward B2 time-mux (splitpipe) + decode a 5 fasi. Ingressi fisici fixed >=20 bit'
    'frazionari. Edge-triggered (1 campione = 1 inferenza), niente start/done. Self-contained (zero .m esterni).'
  };
  s = strjoin(L, newline);
end
