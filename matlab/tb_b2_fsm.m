function tb_b2_fsm()
%TB_B2_FSM  [B2] Testbench HDL: guida snn_b2_fsm con la sequenza x_norm golden di Donatello
%  (start + clocking fino a valid). HDL Coder logga gli I/O -> TB VHDL auto per cosim.
  here = fileparts(mfilename('fullpath'));
  % la ROM (b2_rom_active) e' stato GLOBALE: rigenerarla, altrimenti il TB verrebbe costruito col
  % champion lasciato da un run precedente (bug silenzioso: cosim "verde" sul champion sbagliato).
  gen_b2_rom('Donatello');
  clear b2_rom_active snn_b2_fsm; rehash;
  d = load(fullfile(here, 'champions_export.mat')); champs = d.champions;
  if iscell(champs), champs = [champs{:}]; end
  idx = find(arrayfun(@(c) strcmp(char(string(c.name)), 'Donatello'), champs), 1);
  c = champs(idx);
  Tf = snn_types('fixed', 13);
  N = min(size(c.x_norm, 1), 6);
  z4 = cast(zeros(4, 1), 'like', Tf.V);
  for t = 1:N
    xn = cast(c.x_norm(t, :).', 'like', Tf.V);
    [~, valid] = snn_b2_fsm(xn, true);      %#ok
    g = 0;
    while ~valid && g < 400
      [~, valid] = snn_b2_fsm(z4, false);   %#ok
      g = g + 1;
    end
  end
end
