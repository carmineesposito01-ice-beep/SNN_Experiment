function dmax = run_acciidm_m_dataset(maxTraj)
%RUN_ACCIIDM_M_DATASET  [SP4-M-FSM G2] Parita' sul DATASET INTERO: il model FSM (acc_iidm_fsm, divisioni
%  esplicitate q1->q5) e' bit-identico al riferimento SP3 (acc_iidm_open) sull'accel di OGNI control-step?
%  `assert dmax==0`. Riporta *quanti su quanti* (lezione §2.1: il cancello vecchio guardava 16 campioni
%  su 1000 e mancava l'82,4% delle divergenze -> qui si guarda il dataset intero).
%
%  Entrambi i lati via MEX (collect_step_mex = acc_iidm_open, fsm_step_mex = acc_iidm_fsm): in fi
%  interpretato costerebbe ~47 min (muro di Donatello). Prerequisito: build_acc_iidm_fsm_mex.
%
%  PROVA DI SENSIBILITA' (da rifare se si tocca la FSM): invertire due divisioni in acc_iidm_fsm (es.
%  usare q2 al posto di q3) DEVE far fallire questo cancello.
  here = fileparts(mfilename('fullpath'));
  if nargin < 1 || isempty(maxTraj), maxTraj = inf; end
  assert(~isempty(which('collect_step_mex')) && ~isempty(which('fsm_step_mex')), ...
         'MEX mancanti: esegui build_acc_iidm_fsm_mex');
  ds = load(fullfile(here,'test_dataset.mat')); tr = ds.trajectories;
  d  = load(fullfile(here,'champions_export.mat')); champs = d.champions;
  if iscell(champs), champs = [champs{:}]; end
  c  = champs(find(arrayfun(@(x) strcmp(char(string(x.name)),'Donatello'), champs),1));
  W  = champ_weights(c); Tp = numerictype(1,21,13);
  nT = min(numel(tr), maxTraj);
  dmax = 0; nstep = 0; ndiff = 0;
  for t = 1:nT
    R   = double(snn_traj_fixed_r16_mex(tr{t}.val, W));
    val = double(fi(double(tr{t}.val),1,32,20));
    K   = size(val,2);
    clear collect_step_mex fsm_step_mex;            % stato OU pulito a inizio traiettoria
    for k = 1:K
      p     = double(snn_decode_lut(fi(R(k,:).',Tp),64));
      aOpen = double(collect_step_mex(val(1,k),val(2,k),val(3,k),val(4,k), p, k==1));
      aFsm  = double(fsm_step_mex(   val(1,k),val(2,k),val(3,k),val(4,k), p, k==1));
      dk = abs(aFsm - aOpen);
      if dk > 0, ndiff = ndiff + 1; end
      dmax  = max(dmax, dk);
      nstep = nstep + 1;
    end
    if mod(t,5)==0 || t==nT
      fprintf('  G2 traj %d/%d (%d control-step, dmax=%.3g)\n', t, nT, nstep, dmax);
    end
  end
  fprintf('G2 run_acciidm_m_dataset: dmax=%.6g | divergenti %d/%d control-step (%d traiettorie)\n', ...
          dmax, ndiff, nstep, nT);
  assert(dmax == 0, 'G2 FALLITO: acc_iidm_fsm != acc_iidm_open (dmax=%.6g su %d/%d control-step)', ...
         dmax, ndiff, nstep);
  fprintf('=== G2 PASSATO: model FSM bit-identico al riferimento su %d/%d control-step ===\n', nstep, nstep);
end
