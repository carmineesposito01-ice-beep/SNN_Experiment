function build_library()
%BUILD_LIBRARY  Genera snn_champions_lib.slx: 4 blocchi champion SELF-CONTAINED.
%  Ogni blocco = Subsystem con porte scalari (s,v,dv,v_l -> v0,T,s0,a,b) e una MATLAB
%  Function che INLINA tutto: pesi bakati + normalizzazione + forward ALIF (10 tick,
%  stato persistent DEL BLOCCO) + decode. Nessuna dipendenza da file .m esterni ->
%  trascinabile in qualsiasi modello/cartella senza addpath.
%
%  Nota: il core type-parametrizzato (snn_core.m ecc.) resta separato per la fase 2-HDL
%  e per run_parity_tests.m; questi blocchi sono la versione double self-contained.
  here = fileparts(mfilename('fullpath'));
  d = load(fullfile(here, 'champions_export.mat')); champs = d.champions;
  if iscell(champs), champs = [champs{:}]; end
  lib = 'snn_champions_lib';
  if bdIsLoaded(lib), close_system(lib, 0); end
  if isfile(fullfile(here, [lib '.slx'])), delete(fullfile(here, [lib '.slx'])); end
  new_system(lib, 'Library');

  in_names  = {'s', 'v', 'dv', 'v_l'};       % dv = v - v_l
  out_names = {'v0', 'T', 's0', 'a', 'b'};
  for i = 1:numel(champs)
    c = champs(i); name = char(string(c.name));
    sub = [lib '/' name];
    add_block('built-in/Subsystem', sub);
    add_block('simulink/User-Defined Functions/MATLAB Function', [sub '/SNN']);
    chart = sfroot().find('-isa', 'Stateflow.EMChart', 'Path', [sub '/SNN']);
    chart.Script = inlined_code(c);            % <-- self-contained, pesi bakati
    add_block('simulink/Signal Routing/Mux',   [sub '/mux'],   'Inputs', '4');
    add_block('simulink/Signal Routing/Demux', [sub '/demux'], 'Outputs', '5');
    for j = 1:4
      add_block('built-in/Inport', [sub '/' in_names{j}], 'Port', num2str(j));
      add_line(sub, [in_names{j} '/1'], ['mux/' num2str(j)]);
    end
    add_line(sub, 'mux/1', 'SNN/1'); add_line(sub, 'SNN/1', 'demux/1');
    for j = 1:5
      add_block('built-in/Outport', [sub '/' out_names{j}], 'Port', num2str(j));
      add_line(sub, ['demux/' num2str(j)], [out_names{j} '/1']);
    end
  end
  set_param(lib, 'EnableLBRepository', 'on');
  save_system(lib, fullfile(here, [lib '.slx']));
  close_system(lib, 0);
  fprintf('Built %s.slx with %d SELF-CONTAINED blocks\n', lib, numel(champs));
end


function code = inlined_code(c)
%INLINED_CODE  Costruisce il testo della MATLAB Function self-contained per un champion.
  M = @(x) mat2str(double(x), 17);
  L = {
    'function params = SNN(x_phys)'
    '%#codegen'
    '% Blocco champion SELF-CONTAINED: pesi bakati + forward ALIF + decode, zero dipendenze .m.'
    ['  W_IN  = ' M(c.fc_weight) ';']           % (32x4) po2
    ['  U     = ' M(c.rec_U) ';']               % (32xR) po2
    ['  V     = ' M(c.rec_V) ';']               % (Rx32) po2
    ['  DEL   = ' M(c.delays) ';']              % (32x4) ritardi interi
    ['  BTH   = ' M(c.base_threshold(:)) ';']   % (32x1)
    ['  TJ    = ' M(c.thresh_jump(:)) ';']      % (32x1)
    ['  LD    = ' M(c.leak_div(:)) ';']         % (32x1) leak_div (=8)
    ['  W_OUT = ' M(c.readout) ';']             % (5x32) po2
    ['  P_LO  = ' M(c.param_lo(:)) ';']         % (5x1)
    ['  P_HI  = ' M(c.param_hi(:)) ';']         % (5x1)
    ['  D_OFF = ' M(c.decode_offset(:)) ';']    % (5x1)
    ['  L_TAU = ' M(c.logit_tau(:)) ';']        % (5x1)
    ['  NRM   = ' M(c.norm(:)) ';']             % (4x1) [S;V;DV;VL]
    '  NT = 10; MAXD = 6; H = size(W_IN, 1);'
    '  % --- normalizzazione (fisico -> [0,1]) ---'
    '  xin = x_phys(:);'
    '  dvc = min(max(xin(3), -NRM(3)), NRM(3));'
    '  xn  = [xin(1)/NRM(1); xin(2)/NRM(2); (dvc + NRM(3))/(2*NRM(3)); xin(4)/NRM(4)];'
    '  % --- stato persistente (registri del blocco) ---'
    '  persistent Vm fat sprev Vli xbuf started'
    '  if isempty(started)'
    '    Vm = zeros(H,1); fat = zeros(H,1); sprev = zeros(H,1);'
    '    Vli = zeros(5,1); xbuf = zeros(4, MAXD); started = true;'
    '  end'
    '  % --- NT tick SNN interni ---'
    '  for k = 1:NT'
    '    xbuf(:, 2:end) = xbuf(:, 1:end-1); xbuf(:, 1) = xn;'
    '    Iin = zeros(H, 1);'
    '    for dd = 0:MAXD-1'
    '      mask = double(DEL == dd);'
    '      Iin = Iin + (W_IN .* mask) * xbuf(:, dd+1);'
    '    end'
    '    rec = U * (V * sprev);'
    '    Vm  = Vm - Vm ./ LD + Iin + rec;'
    '    eth = BTH + max(fat, 0);'
    '    s   = double(Vm >= eth);'
    '    fat = fat - fat ./ LD + s .* max(TJ, 0);'
    '    Vm  = Vm - s .* eth;'
    '    sprev = s;'
    '    Vli = Vli - Vli ./ 8 + W_OUT * s;'
    '  end'
    '  % --- decode -> 5 parametri fisici ---'
    '  adj = (Vli - D_OFF) ./ L_TAU;'
    '  params = P_LO + (P_HI - P_LO) .* (1 ./ (1 + exp(-adj)));'
    'end'
  };
  code = strjoin(L, newline);
end
