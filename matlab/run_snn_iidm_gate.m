function run_snn_iidm_gate(K, holdC, trajIdx)
%RUN_SNN_IIDM_GATE  Il blocco composto Donatello_SNN_IIDM (Tier@BAL + align + ACC-IIDM) riproduce
%  acc_iidm_open(fisici, params-decode64) sul dataset -> dmax=0. Prova che l'allineamento e' corretto:
%  su ingresso COSTANTE deve fare UNA sola inferenza (se ne fa due, il doppio-edge/OU e' rotto).
  if nargin<1||isempty(K),       K=25;   end
  if nargin<2||isempty(holdC),   holdC=1000; end   % >= latenza SNN(~406)+align+IIDM(~150) ; margine
  if nargin<3||isempty(trajIdx), trajIdx=1; end
  here=fileparts(mfilename('fullpath'));
  ds=load(fullfile(here,'test_dataset.mat')); tr=ds.trajectories; tr=tr(trajIdx);
  d=load(fullfile(here,'champions_export.mat')); champs=d.champions; if iscell(champs), champs=[champs{:}]; end
  c=champs(find(arrayfun(@(x) strcmp(char(string(x.name)),'Donatello'),champs),1));
  W=champ_weights(c); Tp=numerictype(1,21,13);
  valRaw=double(tr{1}.val); val=double(fi(valRaw,1,32,20));
  Rmex=double(snn_traj_fixed_r16_mex(tr{1}.val,W));

  % riferimento: acc_iidm_open(fisici, decode64-params), OU sequenziale
  clear acc_iidm_open; Tf=acc_types('fixed',8); aRef=zeros(K,1);
  for k=1:K
    p=double(fi(double(snn_decode_lut(fi(Rmex(k,:).',Tp),64)),1,32,20));
    aRef(k)=double(acc_iidm_open(val(1,k),val(2,k),val(3,k),val(4,k), p, k==1, Tf));
  end

  % --- controllo di allineamento: ingresso COSTANTE -> UNA sola inferenza ---
  A0=drive_snn_iidm(val(:,1)*ones(1,3), 1300, 1300);
  chg=find(abs(diff(A0))>0);
  assert(~isempty(chg),'accel non cambia mai: blocco fermo o composizione rotta');
  lat=chg(1);
  fprintf('latenza composto = %d clk ; su ingresso costante: %d aggiornamenti di accel\n', lat, numel(chg));
  assert(numel(chg)==1, ['ALLINEAMENTO ROTTO: %d inferenze su ingresso costante (doppio-edge / OU due volte)'], numel(chg));

  % --- streaming sul dataset ---
  A=drive_snn_iidm(val(:,1:K), holdC, K*holdC+40);
  idx=holdC*(0:K-1).'+lat+1; idx=idx(idx<=numel(A)); aBlk=A(idx);
  n=min(numel(aBlk),K); assert(n==K,'attesi %d aggiornamenti, trovati %d',K,n);
  dmax=max(abs(aBlk(1:n)-aRef(1:n)));
  fprintf('Donatello_SNN_IIDM su %d control-step: dmax vs acc_iidm_open = %.4g\n', n, dmax);
  assert(dmax==0, 'composto != acc_iidm_open (dmax=%.4g): allineamento o composizione errati', dmax);
  fprintf('=== SNN_IIDM GATE PASSATO: composto bit-exact, 1 inferenza/control-step ===\n');
end

function A=drive_snn_iidm(seq, hold, stopT)
  K=size(seq,2); assignin('base','stim_si',[(0:K-1).'*hold, seq.']);
  mdl='blk_snn_iidm'; if bdIsLoaded(mdl), close_system(mdl,0); end
  new_system(mdl); load_system(mdl);
  add_block('snn_champions_lib/Donatello_SNN_IIDM',[mdl '/DUT']);
  add_block('simulink/Sources/From Workspace',[mdl '/src'],'VariableName','stim_si', ...
            'SampleTime','1','Interpolate','off','OutputAfterFinalValue','Holding final value');
  add_block('simulink/Signal Routing/Demux',[mdl '/dm'],'Outputs','4'); add_line(mdl,'src/1','dm/1');
  for j=1:4
    add_block('simulink/Signal Attributes/Data Type Conversion',[mdl '/c' num2str(j)],'OutDataTypeStr','fixdt(1,32,20)');
    add_line(mdl,['dm/' num2str(j)],['c' num2str(j) '/1']); add_line(mdl,['c' num2str(j) '/1'],['DUT/' num2str(j)]);
  end
  add_block('simulink/Sinks/To Workspace',[mdl '/Aw'],'VariableName','Aw','SaveFormat','Array'); add_line(mdl,'DUT/1','Aw/1');
  set_param(mdl,'Solver','FixedStepDiscrete','FixedStep','1','StopTime',num2str(stopT),'SaveOutput','off');
  so=sim(mdl); A=double(so.get('Aw')); close_system(mdl,0);
end
