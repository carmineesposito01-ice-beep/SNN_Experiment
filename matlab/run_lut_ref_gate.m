function run_lut_ref_gate(Ns, K, holdC, trajIdx)
%RUN_LUT_REF_GATE  Cancello del blocco combinato Donatello_LUT (architettura splitpipe): per ogni N il
%  blocco (popup NLUT=N) riproduce ESATTAMENTE il riferimento MEX + snn_decode_lut(.,N) in streaming su una
%  traiettoria reale del dataset. Sostituisce run_lut_combine_gate (i singoli storici non esistono piu': la
%  verifica ora e' vs il RIFERIMENTO, non vs i singoli).
%  + SENSIBILITA': il blocco@16 deve DIFFERIRE dal riferimento@64 (un cancello che non puo' fallire non e'
%    un cancello: discrimina N).
%  Atteso: dmax=0 per ogni N; sensibilita' > 0.
  if nargin<1||isempty(Ns),      Ns=[16 32 64 128 256 512]; end
  if nargin<2||isempty(K),       K=25; end
  if nargin<3||isempty(holdC),   holdC=600; end       % >= latenza (splitpipe ~406); qualunque valore >= latenza
  if nargin<4||isempty(trajIdx), trajIdx=1; end
  here=fileparts(mfilename('fullpath'));
  ds=load(fullfile(here,'test_dataset.mat')); tr=ds.trajectories; tr=tr(trajIdx);
  d=load(fullfile(here,'champions_export.mat')); champs=d.champions; if iscell(champs), champs=[champs{:}]; end
  c=champs(find(arrayfun(@(x) strcmp(char(string(x.name)),'Donatello'), champs),1));
  W=champ_weights(c); Tp=numerictype(1,21,13);
  val=double(tr{1}.val);
  Rmex=double(snn_traj_fixed_r16_mex(tr{1}.val, W));

  % latenza (ingresso costante -> 1 sola inferenza edge-triggered)
  P0=drive_lut('Donatello_LUT','64', val(:,1)*ones(1,3), 800, 800);
  chg=find(any(abs(diff(P0,1,1))>0,2));
  assert(~isempty(chg),'nessun aggiornamento params (FSM ferma?)');
  assert(numel(chg)==1,'non edge-triggered su ingresso costante (%d update)',numel(chg));
  lat=chg(1);
  fprintf('latenza inferenza = %d clock (edge-trigger OK); hold=%d\n', lat, holdC);
  assert(holdC>=lat,'hold=%d < latenza=%d',holdC,lat);

  allok=true; store=struct();
  for N=Ns
    p_ref=zeros(K,5);
    for k=1:K, p_ref(k,:)=double(snn_decode_lut(fi(Rmex(k,:).',Tp),N)).'; end
    Pc=sampleseq(drive_lut('Donatello_LUT', num2str(N), val(:,1:K), holdC, K*holdC+20), holdC, lat, K);
    dcr=max(max(abs(Pc-p_ref)));
    fprintf('LUT-%-3d  blocco-vs-ref = %.4g\n', N, dcr);
    if dcr~=0, allok=false; end
    store.(sprintf('N%d',N))=Pc;
  end

  % SENSIBILITA': blocco@16 vs riferimento@64 -> deve differire
  ref64=zeros(K,5);
  for k=1:K, ref64(k,:)=double(snn_decode_lut(fi(Rmex(k,:).',Tp),64)).'; end
  dsens=max(max(abs(store.N16 - ref64)));
  fprintf('SENSIBILITA'' blocco@16 vs riferimento@64 = %.4g (deve essere > 0)\n', dsens);
  assert(dsens>0,'il cancello NON discrimina N (blocco@16 == riferimento@64)');
  assert(allok,'qualche N ha dmax != 0 vs riferimento');
  fprintf('=== LUT REF GATE PASSATO: blocco splitpipe bit-exact al riferimento su %d control-step, e discrimina N ===\n', K);
end

function S=sampleseq(P, hold, lat, K)
  idx=hold*(0:K-1).'+lat+1; idx=idx(idx<=size(P,1));
  S=P(idx,:); n=size(S,1);
  assert(n==K,'attesi %d campioni, trovati %d (hold/stopT insufficienti?)',K,n);
end

function P=drive_lut(blockName, nlutStr, seq, hold, stopT)
  K=size(seq,2); ts=[(0:K-1).'*hold, seq.']; assignin('base','stimTS_lrg',ts);
  mdl='blk_lut_refgate'; if bdIsLoaded(mdl), close_system(mdl,0); end
  new_system(mdl); load_system(mdl);
  add_block(['snn_champions_lib/' blockName], [mdl '/DUT']);
  if ~isempty(nlutStr), set_param([mdl '/DUT'],'NLUT',nlutStr); end
  add_block('simulink/Sources/From Workspace', [mdl '/src'], 'VariableName','stimTS_lrg', ...
            'SampleTime','1','Interpolate','off','OutputAfterFinalValue','Holding final value');
  add_block('simulink/Signal Routing/Demux', [mdl '/dm'], 'Outputs','4'); add_line(mdl,'src/1','dm/1');
  for j=1:4
    add_block('simulink/Signal Attributes/Data Type Conversion', [mdl '/c' num2str(j)], ...
              'OutDataTypeStr','fixdt(1,32,20)');
    add_line(mdl,['dm/' num2str(j)],['c' num2str(j) '/1']); add_line(mdl,['c' num2str(j) '/1'],['DUT/' num2str(j)]);
  end
  add_block('simulink/Signal Routing/Mux', [mdl '/mx'], 'Inputs','5');
  for j=1:5, add_line(mdl,['DUT/' num2str(j)],['mx/' num2str(j)]); end
  add_block('simulink/Sinks/To Workspace', [mdl '/Pw'], 'VariableName','Pw','SaveFormat','Array');
  add_line(mdl,'mx/1','Pw/1');
  set_param(mdl,'Solver','FixedStepDiscrete','FixedStep','1','StopTime',num2str(stopT),'SaveOutput','off');
  so=sim(mdl); P=double(so.get('Pw')); close_system(mdl,0);
end
