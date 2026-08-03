function run_lib_dataset_test(trajIdx, K, H)
%RUN_LIB_DATASET_TEST  Costruisce ed esegue snn_lib_dataset_test.slx su una traiettoria del dataset,
%  verificando TUTTI gli 8 blocchi della libreria milestone contro il loro riferimento. Stampa una
%  tabella PASS/dmax. Prova che i blocchi FUNZIONANO sui dati reali dello studio.
%
%    Campioni (4, double, 1 step/campione)   -> ref_params (Python, test_trajectories.mat): max|Δ|
%    Donatello_LUT@64 / Donatello_Tier@BAL13 -> MEX + snn_decode_lut(.,64)               : dmax (atteso 0)
%    Donatello_ACC_IIDM_M / ACC-IIDM         -> acc_iidm_open(., decode64, .)             : dmax (atteso 0)
%
%  trajIdx (def 1), K control-step per gli HDL (def 20), H = hold clock/campione (def 600 >= latenza).
  if nargin<1||isempty(trajIdx), trajIdx=1; end
  if nargin<2||isempty(K), K=20; end
  if nargin<3||isempty(H), H=600; end
  here=fileparts(mfilename('fullpath')); cd(here); addpath(here);
  build_lib_dataset_test();
  lib='snn_champions_lib'; if ~bdIsLoaded(lib), load_system(fullfile(here,[lib '.slx'])); end
  mdl='snn_lib_dataset_test'; if bdIsLoaded(mdl), close_system(mdl,0); end
  load_system(fullfile(here,[mdl '.slx']));

  % ---- dataset + riferimenti ----
  a=load('test_trajectories.mat'); T=a.trajectories; if iscell(T), T=[T{:}]; end
  assert(trajIdx<=numel(T),'traj %d inesistente (ne esistono %d)',trajIdx,numel(T));
  c=T(trajIdx); order=cellstr(c.champion_order); refP=c.ref_params;   % (4x5) ref Python per campione
  valRaw=double(c.val); N=size(valRaw,2); Nc=min(N,1000);
  val=double(fi(valRaw,1,32,20));                    % pre-quantizzato: la DTC del bench e' un no-op

  d=load('champions_export.mat'); champs=d.champions; if iscell(champs), champs=[champs{:}]; end
  cD=champs(find(arrayfun(@(x) strcmp(char(string(x.name)),'Donatello'),champs),1));
  W=champ_weights(cD); Tp=numerictype(1,21,13);
  Rmex=double(snn_traj_fixed_r16_mex(c.val, W));
  pq=zeros(K,5);                                      % params decode64, pre-quantizzati a fixdt(1,32,20)
  for k=1:K, pq(k,:)=double(fi(double(snn_decode_lut(fi(Rmex(k,:).',Tp),64)),1,32,20)).'; end

  clear acc_iidm_open; TfS=acc_types('fixed',8); aS_ref=zeros(K,1);
  for k=1:K, aS_ref(k)=double(acc_iidm_open(val(1,k),val(2,k),val(3,k),val(4,k), pq(k,:).', k==1, TfS)); end
  clear acc_iidm_open; TfM=acc_types('fixed');  aM_ref=zeros(K,1);
  for k=1:K, aM_ref(k)=double(acc_iidm_open(val(1,k),val(2,k),val(3,k),val(4,k), pq(k,:).', k==1, TfM)); end

  % ---- sorgenti + config + sim ----
  assignin('base','fw_fast',  [(0:Nc-1).', valRaw(:,1:Nc).']);      % Campioni: crudi, 1 step/campione
  assignin('base','fw_hold',  [(0:K-1).'*H, val(:,1:K).']);          % HDL: pre-quantizzati, held H
  assignin('base','fw_params',[(0:K-1).'*H, pq]);                     % params sincroni ai fisici, held H
  stopT=max(Nc, K*H)+5;
  set_param(mdl,'StopTime',num2str(stopT));
  set_param([mdl '/Donatello_LUT'],'NLUT','64');
  set_param([mdl '/Donatello_Tier'],'TIER','BALANCED','NFRAC','13');
  so=sim(mdl);

  g=@(nm) so.get(nm);
  idx=H*(1:K).';                                       % fine-hold: uscita stabile del control-step k

  fprintf('\n=== TEST BLOCCHI su traj %d (%s), K=%d control-step, hold=%d ===\n', ...
          trajIdx, char(string(c.scenario)), K, H);
  fprintf('%-24s %-10s %-12s %s\n','blocco','tipo','dmax/|Δ|','esito');

  % Campioni (double): media a regime (2a meta') vs ref_params
  champBlk={'Donatello','Leonardo','Michelangelo','Raffaello'};
  allpass=true;
  for i=1:4
    y=g(['P_' champBlk{i}]); if size(y,1)==5 && size(y,2)~=5, y=y.'; end
    blk=mean(y(floor(Nc/2):Nc,:),1);
    ci=find(strcmp(order,champBlk{i}),1); ref=refP(ci,:);
    dd=max(abs(blk-ref)); pass=isfinite(dd) && dd<0.5;
    fprintf('%-24s %-10s %-12.4g %s\n', champBlk{i}, 'campione', dd, tern(pass));
    allpass=allpass && pass;
  end
  % Estimatori HDL: params @fine-hold vs decode64
  for nm={'Donatello_LUT','Donatello_Tier'}
    y=g(['P_' nm{1}]); ys=y(idx,:); dd=max(max(abs(ys-pq))); pass=(dd==0);
    fprintf('%-24s %-10s %-12.4g %s\n', nm{1}, 'estim.HDL', dd, tern(pass));
    allpass=allpass && pass;
  end
  % Controllori: accel @fine-hold vs acc_iidm_open
  AM=g('A_M'); aM=AM(idx); ddM=max(abs(aM-aM_ref)); passM=(ddM==0);
  fprintf('%-24s %-10s %-12.4g %s\n', 'Donatello_ACC_IIDM_M','contr.', ddM, tern(passM));
  AS=g('A_S'); aS=AS(idx); ddS=max(abs(aS-aS_ref)); passS=(ddS==0);
  fprintf('%-24s %-10s %-12.4g %s\n', 'ACC-IIDM','contr.', ddS, tern(passS));
  allpass=allpass && passM && passS;

  close_system(mdl,0);
  fprintf('----\n');
  assert(allpass, 'ALCUNI BLOCCHI NON PASSANO (vedi tabella)');
  fprintf('=== TUTTI E 8 I BLOCCHI PASSANO sul dataset ===\n');
end

function s=tern(p), if p, s='PASS'; else, s='FAIL'; end, end
