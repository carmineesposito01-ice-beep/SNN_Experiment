function [nBadTraj, nBadStep] = run_b2_parity_dataset(name)
%RUN_B2_PARITY_DATASET  Cancello ESTESO: parità FSM(B2) vs core sull'INTERO `test_dataset.mat`.
%  Perché esiste: `run_b2_parity` gira solo sulla sequenza golden `c.x_phys` = **16 campioni**, e la
%  divergenza FSM-vs-core compare mediamente dopo **~100** control-step → il cancello era **cieco**
%  (HDL_PHASE §2.1: con quel buco, 82,4% dei control-step del dataset divergeva a cancello VERDE).
%  Questo confronta il raw del forward serializzato (`snn_traj_b2` → `snn_b2_fsm`) con quello del
%  core (`snn_traj_fixed` → `snn_core`) su **60 traiettorie × 1000 control-step**, a parità di `xn`.
%
%  Atteso: **0 traiettorie e 0 control-step divergenti**.
%
%  ⚠️ Richiede i MEX: il `fi` interpretato sarebbe ~20 milioni di chiamate (inutilizzabile).
%     Il MEX di `snn_traj_b2` **bake la ROM** (`coder.const`) → viene **ricompilato a ogni champion**.
%
%  [nBadTraj, nBadStep] = run_b2_parity_dataset('Donatello')
  if nargin < 1, name = 'Donatello'; end
  here = fileparts(mfilename('fullpath'));

  d = load(fullfile(here, 'champions_export.mat')); champs = d.champions;
  if iscell(champs), champs = [champs{:}]; end
  idx = find(arrayfun(@(x) strcmp(char(string(x.name)), name), champs), 1);
  assert(~isempty(idx), 'champion %s non trovato', name);
  c = champs(idx); W = champ_weights(c); nrm = double(c.norm(:));
  rnk = double(c.rank);
  assert(any(rnk == [8 16]), 'rango %d senza MEX del core (servono r8/r16)', rnk);

  % ROM del champion + MEX del forward serializzato (la ROM e' baked -> ricompilare sempre)
  gen_b2_rom(name);
  clear snn_traj_b2_mex b2_rom_active snn_b2_fsm; rehash;
  valt = coder.typeof(zeros(4, 1000), [4 Inf], [false true]);
  evalc("codegen('snn_traj_b2', '-args', {valt, coder.typeof(zeros(4,1))}, '-o', 'snn_traj_b2_mex')");

  ds = load(fullfile(here, 'test_dataset.mat')); tr = ds.trajectories;
  nT = numel(tr); nBadTraj = 0; nBadStep = 0; totStep = 0; worst = 0;
  for k = 1:nT
    clear snn_traj_b2_mex;                                  % stato FSM da zero per ogni traiettoria
    Rfsm = snn_traj_b2_mex(tr{k}.val, nrm);
    if rnk == 16, Rcore = double(snn_traj_fixed_r16_mex(tr{k}.val, W));
    else,         Rcore = double(snn_traj_fixed_r8_mex(tr{k}.val, W)); end
    dd = max(abs(Rfsm - Rcore), [], 2);
    nb = nnz(dd > 0);
    totStep = totStep + numel(dd); nBadStep = nBadStep + nb;
    if nb > 0, nBadTraj = nBadTraj + 1; worst = max(worst, max(dd)); end
  end
  fprintf('%-13s dataset parity: %d/%d traiettorie e %d/%d control-step divergenti (max raw %.4g)\n', ...
          name, nBadTraj, nT, nBadStep, totStep, worst);
  assert(nBadStep == 0, ['%s: il forward B2 NON e'' bit-exact vs il core su %d/%d control-step ' ...
         '(max raw %.4g) -> vedi HDL_PHASE §2.1'], name, nBadStep, totStep, worst);
end
