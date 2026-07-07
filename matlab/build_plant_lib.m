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
%PLANT_CODE  Testo della MATLAB Function ACC-IIDM (port 1:1 di core/network.py:acc_iidm_accel).
  L = {
    'function out = PLANT(in)'
    '%#codegen'
    '% Plant ACC-IIDM self-contained. in=[v_l;v0;T;s0;a;b] (6x1), out=[s;v;accel] (3x1).'
    '  DT = 0.1; ALPHA = exp(-DT/1.0); NORM_S_MAX = 150; COOL = 0.99;'
    '  vl = in(1); v0 = max(in(2),1e-3); T = max(in(3),1e-3);'
    '  s0 = in(4); a = max(in(5),1e-3); b = max(in(6),1e-3);'
    '  persistent s v alf vlp started'
    '  if isempty(started)'
    '    v = 0.8*v0; s = s0 + v*T; alf = 0; vlp = vl; started = true;'
    '  end'
    '  % stima a_l (filtro OU su differenze finite del leader)'
    '  alf = ALPHA*alf + (1-ALPHA)*((vl - vlp)/DT); vlp = vl;'
    '  dv = v - vl;'
    '  % --- acc_iidm_accel: IIDM base + CAH + blend ACC ---'
    '  sab = max(sqrt(a*b), 1e-6);'
    '  s_star = s0 + max(v*T + v*dv/(2*sab), 0);'
    '  s_safe = max(s, 2.0);'
    '  v_free = a*(1 - min(v/v0, 10)^4);'
    '  z = min(s_star/s_safe, 20);'
    '  below = (v <= v0);'
    '  a_z = a*(1 - z^2);'
    '  if z < 1'
    '    if below, a_iidm = v_free*(1 - z^2); else, a_iidm = v_free; end'
    '  else'
    '    if below, a_iidm = a_z; else, a_iidm = v_free + a_z; end'
    '  end'
    '  a_l_bar = min(alf, a);'
    '  a_cah = a_l_bar - max(dv,0)^2/(2*s_safe + 1e-6);'
    '  a_cah = min(max(a_cah, -9), a);'
    '  dd = (a_iidm - a_cah)/(b + 1e-6);'
    '  a_blend = (1-COOL)*a_iidm + COOL*(a_cah + b*tanh(dd));'
    '  if a_iidm >= a_cah, accel = a_iidm; else, accel = a_blend; end'
    '  accel = min(max(accel, -9), a);'
    '  % --- integrazione balistica (s usa la v vecchia) ---'
    '  v_old = v;'
    '  v = min(max(v + accel*DT, 0), 1.2*v0);'
    '  s = min(max(s + (vl - v_old)*DT, 0.5*s0), NORM_S_MAX);'
    '  out = [s; v; accel];'
    'end'
  };
  code = strjoin(L, newline);
end
