function mount_split(sub, in_names, out_names, snnCode, decCode)
%MOUNT_SPLIT  [SPLIT] DUE MATLAB Function nel subsystem:
%    SNN: s,v,dv,v_l -> raw(5), valid       DEC: raw(5), valid -> v0,T,s0,a,b
%  raw e valid attraversano il confine come segnali -> HDL Coder le sintetizza come entita' distinte.
  add_block('simulink/User-Defined Functions/MATLAB Function', [sub '/SNN']);
  chS = sfroot().find('-isa', 'Stateflow.EMChart', 'Path', [sub '/SNN']); chS.Script = snnCode;
  add_block('simulink/User-Defined Functions/MATLAB Function', [sub '/DEC']);
  chD = sfroot().find('-isa', 'Stateflow.EMChart', 'Path', [sub '/DEC']); chD.Script = decCode;
  for j = 1:4      % ingressi fisici -> SNN
    add_block('built-in/Inport', [sub '/' in_names{j}], 'Port', num2str(j));
    add_line(sub, [in_names{j} '/1'], ['SNN/' num2str(j)]);
  end
  % il confine: SNN uscita 1 = raw, uscita 2 = valid  ->  DEC ingresso 1 = raw, 2 = valid
  add_line(sub, 'SNN/1', 'DEC/1');
  add_line(sub, 'SNN/2', 'DEC/2');
  for j = 1:5      % DEC -> uscite fisiche
    add_block('built-in/Outport', [sub '/' out_names{j}], 'Port', num2str(j));
    add_line(sub, ['DEC/' num2str(j)], [out_names{j} '/1']);
  end
end


