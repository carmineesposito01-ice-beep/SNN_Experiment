function build_acc_iidm_block()
%BUILD_ACC_IIDM_BLOCK  Aggiunge a snn_champions_lib.slx il blocco standalone 'ACC-IIDM' = il controllore
%  IIDM **R17** (77,936 MHz, +397% vs R0) SENZA la SNN. 9 ingressi (s,v,dv,v_l,v0,T,s0,a,b) -> accel.
%    Architettura R17 completa: divisore+radice digit-recurrence sequenziali, decode-non-serve (params in),
%    USE a 4 fasi, FINAL/PREP/OU a stadi. nfrac=8 (l'architettura R17 e' nfrac=8-specifica).
%  Chart = iidm_r17_chart_code (la chart M di Donatello_ACC_IIDM_M meno SNN+decode+normalize). Le fasi IIDM
%  sono le STESSE, provate bit-exact (run_iidm_r17_func_gate: dmax=0 vs acc_iidm_open@8).
%  Distinto da Donatello_ACC_IIDM_M (che ha la SNN dentro): questo e' il controllore da solo, componibile.
  here=fileparts(mfilename('fullpath')); cd(here);
  code = iidm_r17_chart_code();
  in_names={'s','v','dv','v_l','v0','T','s0','a','b'};
  lib='snn_champions_lib'; libfile=fullfile(here,[lib '.slx']);
  assert(isfile(libfile), '%s inesistente', libfile);
  if bdIsLoaded(lib), close_system(lib,0); end
  load_system(libfile); set_param(lib,'Lock','off');

  sub=[lib '/ACC-IIDM'];
  if getSimulinkBlockHandle(sub)>0, delete_block(sub); end
  add_block('built-in/Subsystem', sub, 'Position', [300,450,520,600], ...
            'Description', acc_iidm_r17_description());
  add_block('simulink/User-Defined Functions/MATLAB Function', [sub '/IIDM']);
  chart=sfroot().find('-isa','Stateflow.EMChart','Path',[sub '/IIDM']);
  chart.Script = code;
  for j=1:9, add_block('built-in/Inport', [sub '/' in_names{j}], 'Port', num2str(j)); end
  add_block('built-in/Outport', [sub '/accel'], 'Port','1');
  for j=1:9, add_line(sub, [in_names{j} '/1'], ['IIDM/' num2str(j)], 'autorouting','on'); end
  add_line(sub, 'IIDM/1', 'accel/1', 'autorouting','on');

  try, Simulink.BlockDiagram.arrangeSystem(sub); catch ME, warning('arrange: %s', ME.message); end
  set_param(lib,'EnableLBRepository','on');
  save_system(lib,libfile); close_system(lib,0);
  fprintf('OK: ACC-IIDM (standalone R17, 9 in -> accel, nfrac=8) aggiunto a %s.slx\n', lib);
end

function s = acc_iidm_r17_description()
  L = {
    'ACC-IIDM - controllore IIDM standalone (car-following), architettura R17, HDL-ready.'
    ''
    'COS''E'''
    '  Il modello ACC-IIDM da solo: riceve i 5 parametri IDM (v0,T,s0,a,b) IN INGRESSO e calcola'
    '  l''accelerazione. NON contiene la SNN -> componibile con qualunque estimator (es. Donatello_Tier).'
    '  E'' la chart di Donatello_ACC_IIDM_M (architettura R17) SENZA la SNN: stesse fasi IIDM, provate'
    '  bit-exact (dmax=0 vs acc_iidm_open, run_iidm_r17_func_gate).'
    ''
    'ARCHITETTURA R17 (campagna hdl_iidm/RESULTS.txt: 17 round di pipelining a stadi, +397%, bit-exact)'
    '  Divisore e radice digit-recurrence sequenziali (1-2 bit/ciclo, hardware PIU'' PICCOLO del combinatorio),'
    '  USE su 4 fasi, FINAL/PREP/OU a stadi. E'' la variante piu'' veloce dell''IIDM.'
    '  Fmax STANDALONE = 75,63 MHz OOC, al collo inerente di R17 (st_a_iidm); il controllore R17 (con la SNN)'
    '  faceva 77,936 allo STESSO collo -- la differenza di 1 liv e'' il contesto standalone (i 5 params'
    '  arrivano dagli ingressi invece che dal decode pipelinato). Ri-ottimizzato per lo standalone in 3 passi'
    '  (pv-latch, edge-detect da fermo, no-snapshot): 61,7 -> 75,63 MHz, dmax=0 ad ogni passo.'
    '  ⚠️ 75,63 MHz e'' MARGINE, non clock: il control-step e'' 0,1 s = 800.000 clock a 8 MHz vs ~150 dell''IIDM.'
    '  nfrac=8: l''architettura R17 e'' a precisione fissa (divisore/radice a larghezza cablata). Lo studio'
    '  Quantizzation_Study_IIDM conferma nfrac=8 come sweet spot (budget E_iidm; a nfrac=2 il c-f rompe).'
    ''
    'INGRESSI (fisici, fixed con >=20 bit frazionari - interporre un Data Type Conversion)'
    '  s [m] · v [m/s] · dv [m/s] (= v - v_l) · v_l [m/s] · v0 [m/s] · T [s] · s0 [m] · a [m/s^2] · b [m/s^2]'
    'USCITA'
    '  accel [m/s^2]'
    ''
    '⚠️ VINCOLO DI RATE'
    '  Una inferenza costa ~150 clock (time-mux: 1 op/ciclo, 5 divisioni + 1 radice sequenziali). Ogni'
    '  ingresso va tenuto per >= quel numero di campioni. Sull''FPGA irrilevante: un control-step da 0,1 s'
    '  dura 800.000 clock a 8 MHz. Edge-triggered: 1 cambio d''ingresso = 1 inferenza; l''uscita tiene.'
    ''
    'RIGENERAZIONE: build_acc_iidm_block.m -> iidm_r17_chart_code.m (NON modificare la chart a mano).'
  };
  s = strjoin(L, newline);
end
