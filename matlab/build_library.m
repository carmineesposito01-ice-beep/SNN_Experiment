function build_library()
%BUILD_LIBRARY  Genera snn_champions_lib.slx (4 blocchi) + <name>_weights.m dai champion.
%  Ogni blocco = Subsystem con un MATLAB Function block che chiama
%  snn_entry('double', x, <name>_weights()) (riusa il core provato in Plan 1).
  here = fileparts(mfilename('fullpath'));
  d = load(fullfile(here, 'champions_export.mat')); champs = d.champions;
  if iscell(champs), champs = [champs{:}]; end
  lib = 'snn_champions_lib';
  if bdIsLoaded(lib), close_system(lib, 0); end
  if isfile(fullfile(here, [lib '.slx'])), delete(fullfile(here, [lib '.slx'])); end
  new_system(lib, 'Library');

  for i = 1:numel(champs)
    c = champs(i); name = char(string(c.name));
    write_weights_fn(fullfile(here, [name '_weights.m']), name, c);
    sub = [lib '/' name];
    add_block('built-in/Subsystem', sub);
    add_block('built-in/Inport',  [sub '/x_phys']);
    add_block('built-in/Outport', [sub '/params']);
    add_block('simulink/User-Defined Functions/MATLAB Function', [sub '/SNN']);
    add_line(sub, 'x_phys/1', 'SNN/1'); add_line(sub, 'SNN/1', 'params/1');
    code = sprintf(['function params = SNN(x_phys)\n%%#codegen\n' ...
                    'params = snn_entry(''double'', x_phys(:), %s_weights());\n' ...
                    'end\n'], name);
    chart = sfroot().find('-isa', 'Stateflow.EMChart', 'Path', [sub '/SNN']);
    chart.Script = code;
  end
  set_param(lib, 'EnableLBRepository', 'on');
  save_system(lib, fullfile(here, [lib '.slx']));
  close_system(lib, 0);
  fprintf('Built %s.slx with %d blocks\n', lib, numel(champs));
end

function write_weights_fn(path, name, c)
  fid = fopen(path, 'w'); assert(fid > 0, 'cannot open %s', path);
  fprintf(fid, 'function W = %s_weights()\n%%#codegen\n', name);
  flds = {'hidden', 'rank', 'n_ticks', 'max_delay', 'fc_weight', 'rec_U', 'rec_V', ...
          'readout', 'delays', 'base_threshold', 'thresh_jump', 'leak_div', ...
          'param_lo', 'param_hi', 'decode_offset', 'logit_tau', 'norm'};
  for k = 1:numel(flds)
    f = flds{k};
    fprintf(fid, '  W.%s = %s;\n', f, mat2str(double(c.(f)), 17));
  end
  fprintf(fid, 'end\n'); fclose(fid);
end
