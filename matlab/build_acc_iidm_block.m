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
    'FUNZIONE: riceve i 5 parametri IDM (v0,T,s0,a,b) + lo stato (s,v,dv,v_l) e calcola l''accelerazione.'
    'NON contiene la SNN -> componibile con qualunque estimator (es. Donatello_Tier). E'' la chart di'
    'Donatello_ACC_IIDM_M SENZA la SNN, bit-exact vs acc_iidm_open (dmax=0, run_iidm_r17_func_gate).'
    ''
    'ARCHITETTURA R17 (hdl_iidm/RESULTS.txt): divisore e radice digit-recurrence SEQUENZIALI (hardware piu'''
    'piccolo del combinatorio), USE/FINAL/PREP a stadi. Fmax standalone 75,6 MHz OOC reg-reg (il controllore'
    'completo 77,9). nfrac=8 (precisione fissa R17); sweet spot confermato da Quantizzation_Study_IIDM.'
    ''
    'INGRESSI (9, fisici, fixed >=20 bit fraz. - interporre un Data Type Conversion):'
    '  s, v, dv (= v - v_l), v_l, v0, T, s0, a, b   ->   USCITA: accel [m/s^2].'
    ''
    'RATE: ~150 clock/inferenza (time-mux), edge-triggered (1 cambio ingressi = 1 inferenza, l''uscita tiene).'
    'Sull''FPGA irrilevante (control-step 0,1 s = 800.000 clock @8 MHz). Self-contained. Rigen.: build_acc_iidm_block.m.'
  };
  s = strjoin(L, newline);
end
