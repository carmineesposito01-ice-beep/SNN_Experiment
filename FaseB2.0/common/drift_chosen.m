function drift_chosen()
%DRIFT_CHOSEN  [Fase B2.0 T5] Deriva OPEN-LOOP del CONTROLLORE SCELTO (blocco composto Donatello_SNN_IIDM =
%  Donatello_Tier@BALANCED + ACC-IIDM) sull'ACCEL, su test_dataset. E' la grandezza rilevante per la
%  sicurezza: l'accel e' cio' che pilota il veicolo (i 5 parametri contano solo a valle, via IDM).
%
%  Blocco (deployato su FPGA) : local_normalize FISSA + forward B2 + decode LUT-64 + IIDM, ingresso tenuto
%                               -> golden fedele acciidm_m_traj  (PROVATO == blocco composto, Fase 0).
%  Riferimento (ideale)       : snn_normalize (float) + forward B2 + decode LUT-64 + IIDM (collect_step).
%  L'unica differenza e' la normalizzazione: FISSA nel blocco vs FLOAT nel riferimento -> deriva di
%  quantizzazione specifica del deploy. La confronto col budget E_snn (footprint in accel della
%  quantizzazione GIA' accettata della rete): se e' sotto E_snn, e' dominata dalla rete -> trascurabile.
%
%  NB: snn_traj_champion e' STALE (estrae dal blocco Donatello_Champion, RIMOSSO nel riordino 8-blocchi
%      2026-07-27) -> non lo si usa. La deriva sui 5 parametri (bench solo-SNN) e' una PARITA' RTL
%      bit-exact (dmax=0), verificata in T6; qui si misura la fedelta' end-to-end sull'accel.
  here = fileparts(mfilename('fullpath')); ml = fullfile(here,'..','..','matlab'); addpath(ml); cd(ml);
  if ~bdIsLoaded('snn_champions_lib'), load_system('snn_champions_lib'); end
  d = load('champions_export.mat'); ch = d.champions; if iscell(ch), ch = [ch{:}]; end
  c = ch(find(arrayfun(@(x) strcmp(char(string(x.name)),'Donatello'), ch), 1));
  nrm = double(c.norm(:)); Tp = numerictype(1,21,13);

  build_acciidm_m_golden();                                   % golden accel fedele al blocco (local_normalize)
  gen_b2_rom('Donatello'); clear snn_traj_b2_mex; rehash;     % riferimento float (snn_normalize)
  valt = coder.typeof(zeros(4,1000),[4 Inf],[false true]);
  evalc("codegen('snn_traj_b2','-args',{valt,coder.typeof(zeros(4,1))},'-o','snn_traj_b2_mex')");
  assert(~isempty(which('collect_step_mex')), 'MEX collect_step mancante: build_acc_iidm_fsm_mex');
  ds = load('test_dataset.mat'); tr = ds.trajectories;

  % === Fase 0: il golden accel rappresenta DAVVERO il blocco composto scelto? (streaming del blocco reale) ===
  K = 4; hold = 1300; stopT = K*hold + 40; sOff = 20;         % campiono a (hold-20): oltre la latenza composto (~554)
  v1 = double(fi(double(tr{1}.val),1,32,20));
  clear acciidm_m_traj_mex; Ag = acciidm_m_traj_mex(tr{1}.val(:,1:K), 500);
  Aser = drive_snn_iidm(v1(:,1:K), hold, stopT);
  Achk = Aser(hold*(1:K).' - sOff);
  dchk = max(abs(Achk - Ag));
  fprintf('Fase 0  cross-check  Donatello_SNN_IIDM (blocco) vs acciidm_m_traj (golden): dmax=%.4g  (%d step)\n', dchk, K);
  assert(dchk == 0, 'golden acciidm_m_traj NON fedele al blocco composto scelto (dmax=%.4g) -> deriva non attendibile', dchk);

  % === Fase 1: deriva accel sul dataset intero ===
  aerr = [];
  for t = 1:numel(tr)
    val = double(fi(double(tr{t}.val),1,32,20));
    clear acciidm_m_traj_mex; Ablk = acciidm_m_traj_mex(tr{t}.val, 500);         % blocco (local_normalize)
    clear snn_traj_b2_mex;    R    = double(snn_traj_b2_mex(tr{t}.val, nrm));     % riferimento (snn_normalize)
    clear collect_step_mex;   Aref = zeros(numel(Ablk),1);
    for k = 1:numel(Ablk)
      p = double(snn_decode_lut(fi(R(k,:).',Tp), 64));                           % stesso decode LUT-64 del blocco
      Aref(k) = collect_step_mex(val(1,k),val(2,k),val(3,k),val(4,k), p, k==1);
    end
    aerr = [aerr; abs(Ablk(:) - Aref(:))]; %#ok<AGROW>
    if mod(t,10)==0, fprintf('  ... %d/%d traj\n', t, numel(tr)); end
  end

  Ep99 = 0.272054; Emax = 1.48433;                            % budget E_snn (acc_types.m, 60k campioni)
  fprintf(['\n=== DERIVA ACCEL  controllore scelto (Donatello_SNN_IIDM) vs ideale float  (test_dataset, %d traj, %d control-step) ===\n' ...
           '  |Delta accel| [m/s^2]:  max=%.4g   p99=%.4g   mediana=%.4g   media=%.4g\n' ...
           '  budget E_snn (quantizz. rete):  p99=%.4g   max=%.4g\n' ...
           '  deriva / budget:  p99 = %.1f%%   max = %.1f%%\n'], ...
    numel(tr), numel(aerr), max(aerr), prctile(aerr,99), median(aerr), mean(aerr), ...
    Ep99, Emax, 100*prctile(aerr,99)/Ep99, 100*max(aerr)/Emax);
  save(fullfile(here,'drift_chosen.mat'), 'aerr', 'Ep99', 'Emax');
  fprintf('salvato FaseB2.0/common/drift_chosen.mat\n');
end

function A = drive_snn_iidm(seq, hold, stopT)
  K = size(seq,2); assignin('base','stim_si',[(0:K-1).'*hold, seq.']);
  mdl = 'blk_snn_iidm_v'; if bdIsLoaded(mdl), close_system(mdl,0); end
  new_system(mdl); load_system(mdl);
  add_block('snn_champions_lib/Donatello_SNN_IIDM',[mdl '/DUT']);
  add_block('simulink/Sources/From Workspace',[mdl '/src'],'VariableName','stim_si', ...
            'SampleTime','1','Interpolate','off','OutputAfterFinalValue','Holding final value');
  add_block('simulink/Signal Routing/Demux',[mdl '/dm'],'Outputs','4'); add_line(mdl,'src/1','dm/1');
  for j = 1:4
    add_block('simulink/Signal Attributes/Data Type Conversion',[mdl '/c' num2str(j)],'OutDataTypeStr','fixdt(1,32,20)');
    add_line(mdl,['dm/' num2str(j)],['c' num2str(j) '/1']); add_line(mdl,['c' num2str(j) '/1'],['DUT/' num2str(j)]);
  end
  add_block('simulink/Sinks/To Workspace',[mdl '/Aw'],'VariableName','Aw','SaveFormat','Array'); add_line(mdl,'DUT/1','Aw/1');
  set_param(mdl,'Solver','FixedStepDiscrete','FixedStep','1','StopTime',num2str(stopT),'SaveOutput','off');
  so = sim(mdl); A = double(so.get('Aw')); close_system(mdl,0);
end
