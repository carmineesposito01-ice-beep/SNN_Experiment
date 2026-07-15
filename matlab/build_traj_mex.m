function build_traj_mex()
%BUILD_TRAJ_MEX  Genera due MEX a rango FISSO da snn_traj_fixed:
%    snn_traj_fixed_r16_mex  (rank 16, EventProp: Donatello/Michelangelo)
%    snn_traj_fixed_r8_mex   (rank  8, baseline:  Raffaello/Leonardo)
%  L'harness sceglie il MEX in base al rango del champion (evita coder.StructType varsize).
  here = fileparts(mfilename('fullpath'));
  d = load(fullfile(here, 'champions_export.mat')); champs = d.champions;
  if iscell(champs), champs = [champs{:}]; end
  pick = @(nm) champs(find(arrayfun(@(x) strcmp(char(string(x.name)), nm), champs), 1));
  valt = coder.typeof(zeros(4, 1), [4 Inf], [false true]);   % N (lunghezza traiettoria) variabile
  cfg = coder.config('mex'); cfg.GenerateReport = false;
  W16 = champ_weights(pick('Donatello'));    % rank 16
  codegen('snn_traj_fixed', '-config', cfg, '-args', {valt, coder.typeof(W16)}, '-o', 'snn_traj_fixed_r16_mex');
  fprintf('OK snn_traj_fixed_r16_mex (rank 16)\n');
  W8 = champ_weights(pick('Raffaello'));     % rank 8
  codegen('snn_traj_fixed', '-config', cfg, '-args', {valt, coder.typeof(W8)}, '-o', 'snn_traj_fixed_r8_mex');
  fprintf('OK snn_traj_fixed_r8_mex (rank 8)\n');

  % Kernel PASSO-PASSO per l'anello CHIUSO (rank 16 = Donatello): i due MEX sopra macinano una
  % traiettoria gia' nota, in anello chiuso invece l'ingresso del passo k+1 dipende dall'uscita
  % del passo k. Vedi snn_cl_step.m e run_block_closed_loop_test.m.
  codegen('snn_cl_step', '-config', cfg, ...
          '-args', {zeros(4, 1), coder.typeof(W16), true}, '-o', 'snn_cl_step_mex');
  fprintf('OK snn_cl_step_mex (passo-passo, rank 16)\n');
end
