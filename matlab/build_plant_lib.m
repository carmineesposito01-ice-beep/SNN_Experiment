function build_plant_lib()
%BUILD_PLANT_LIB  Genera cf_plant_lib.slx: libreria dei plant car-following (estendibile).
%  Oggi contiene il blocco ACC_IIDM (self-contained); in futuro IDM/Gipps/OVM... affianco.
%  ACC_IIDM: 6 ingressi scalari (v_l, v0, T, s0, a, b) -> 3 uscite (s, v, accel).
%  Porta acc_iidm_accel (core/network.py) + stima a_l (OU) + integrazione balistica,
%  stato persistent DEL BLOCCO. Deterministico (nessun rumore di percezione).
  here = fileparts(mfilename('fullpath'));
  lib = 'cf_plant_lib';
  if bdIsLoaded(lib), close_system(lib, 0); end
  if isfile(fullfile(here, [lib '.slx'])), delete(fullfile(here, [lib '.slx'])); end
  new_system(lib, 'Library');
  add_acc_iidm(lib);
  set_param(lib, 'EnableLBRepository', 'on');
  save_system(lib, fullfile(here, [lib '.slx']));
  close_system(lib, 0);
  fprintf('Built %s.slx (blocco ACC_IIDM)\n', lib);
end


function add_acc_iidm(lib)
  sub = [lib '/ACC_IIDM'];
  in_names  = {'v_l', 'v0', 'T', 's0', 'a', 'b'};
  out_names = {'s', 'v', 'accel'};
  add_block('built-in/Subsystem', sub);
  add_block('simulink/User-Defined Functions/MATLAB Function', [sub '/PLANT']);
  chart = sfroot().find('-isa', 'Stateflow.EMChart', 'Path', [sub '/PLANT']);
  chart.Script = plant_code();
  add_block('simulink/Signal Routing/Mux',   [sub '/mux'],   'Inputs', '6');
  add_block('simulink/Signal Routing/Demux', [sub '/demux'], 'Outputs', '3');
  for j = 1:6
    add_block('built-in/Inport', [sub '/' in_names{j}], 'Port', num2str(j));
    add_line(sub, [in_names{j} '/1'], ['mux/' num2str(j)]);
  end
  add_line(sub, 'mux/1', 'PLANT/1'); add_line(sub, 'PLANT/1', 'demux/1');
  for j = 1:3
    add_block('built-in/Outport', [sub '/' out_names{j}], 'Port', num2str(j));
    add_line(sub, ['demux/' num2str(j)], [out_names{j} '/1']);
  end
end


function code = plant_code()
%PLANT_CODE  Testo della MATLAB Function ACC-IIDM closed-loop = acc_iidm_open + integrazione.
%  La matematica IIDM NON e' duplicata qui: `acc_iidm_open.m` viene letto a build-time e inlinato
%  come funzione locale (le locali hanno precedenza sul path -> blocco self-contained, zero deriva).
%  E' l'unica fonte, condivisa col blocco SP2 `Donatello_ACC_IIDM`. Cancello: `run_plant_parity`.
  here = fileparts(mfilename('fullpath'));
  src = fileread(fullfile(here, 'acc_iidm_open.m'));
  L = {
    'function out = PLANT(in)'
    '%#codegen'
    '% Plant ACC-IIDM self-contained. in=[v_l;v0;T;s0;a;b] (6x1), out=[s;v;accel] (3x1).'
    '% accel = acc_iidm_open(...) (UNICA fonte della matematica IIDM) + integrazione balistica.'
    '  DT = 0.1; NORM_S_MAX = 150;'
    '  vl = in(1); v0 = max(in(2),1e-3); T = max(in(3),1e-3);'
    '  s0 = in(4); a = max(in(5),1e-3); b = max(in(6),1e-3);'
    '  % `if isempty(started)` NON e'' intercambiabile con `if ~started`: il codegen riconosce'
    '  % letteralmente isempty(<persistent>) come prova di definizione. Col test sul VALORE fallisce'
    '  % con "Persistent variable ''v'' is undefined on some execution paths". Vedi README sez.Gotcha.'
    '  persistent s v started'
    '  if isempty(started)'
    '    v = 0.8*v0; s = s0 + v*T; started = true; rst = true;'
    '  else'
    '    rst = false;'
    '  end'
    '  dv = v - vl;'
    '  accel = acc_iidm_open(s, v, dv, vl, [v0; T; s0; a; b], rst);'
    '  % --- integrazione balistica (s usa la v vecchia) ---'
    '  v_old = v;'
    '  v = min(max(v + accel*DT, 0), 1.2*v0);'
    '  s = min(max(s + (vl - v_old)*DT, 0.5*s0), NORM_S_MAX);'
    '  out = [s; v; accel];'
    'end'
    ''
    '% ==== funzione locale INLINATA dal sorgente vero (build_plant_lib la legge a build-time) ===='
  };
  code = [strjoin(L, newline) newline newline src];
end
