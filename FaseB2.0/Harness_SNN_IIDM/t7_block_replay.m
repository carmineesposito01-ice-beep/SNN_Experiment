function A = t7_block_replay(X, hold)
%T7_BLOCK_REPLAY  Pilota il BLOCCO COMPOSTO `Donatello_SNN_IIDM` in Simulink sulla sequenza di ingressi
%  X (4 x N, gia' quantizzati a fixdt(1,32,20) con FLOOR) e restituisce l'accel a fine control-step.
%
%  E' il RIFERIMENTO di T7a: il DUT e' il composto, quindi il riferimento dev'essere il composto.
%
%  ⚠️ NON usare `acciidm_m_traj` come riferimento del composto: e' l'estrazione verbatim del blocco
%     MONOLITICO DEPRECATO `Donatello_ACC_IIDM_M`, e NON gli e' equivalente. Misurato il 2026-07-30 su
%     una traiettoria reale di 600 control-step: **385 scarti**, primo al passo 195. L'equivalenza era
%     stata provata solo su 4 control-step (T5) e 6 (P4) — campioni troppo piccoli per vederlo.
%
%  MODO D'USO (non circolare): si passa la sequenza di ingressi che l'RTL ha EFFETTIVAMENTE ricevuto,
%  registrata dal testbench. Il confronto risponde a "dati questi ingressi, il blocco produce lo stesso
%  accel dell'RTL?" — che e' esattamente la domanda di equivalenza. La correttezza del plant che genera
%  quegli ingressi e' provata a parte da PLANT-PAR, senza DUT. Plant corretto + DUT corretto => anello
%  corretto.
%
%  X    : 4 x N  [s; v; dv; v_l] quantizzati FLOOR a fixdt(1,32,20)
%  hold : clock per control-step, DEVE superare la latenza del composto (misurata 555 dopo il
%         registro di confine; era 554 prima -- il registro aggiunge 1 clock, non altera i valori)
%  A    : N x 1  accel (Q4.8)
  if nargin < 2 || isempty(hold), hold = 700; end
  assert(hold > 555, 't7_block_replay: hold=%d non supera la latenza misurata del composto (555)', hold);
  assert(size(X,1) == 4, 't7_block_replay: X deve essere 4 x N, ricevuto %s', mat2str(size(X)));
  N = size(X,2);

  here = fileparts(mfilename('fullpath'));
  ml   = fullfile(here,'..','..','matlab');
  if ~bdIsLoaded('snn_champions_lib'), load_system(fullfile(ml,'snn_champions_lib.slx')); end

  assignin('base','stim_t7rep', [(0:N-1).'*hold, X.']);
  mdl = 't7_replay_mdl'; if bdIsLoaded(mdl), close_system(mdl,0); end
  new_system(mdl); load_system(mdl);
  add_block('snn_champions_lib/Donatello_SNN_IIDM',[mdl '/DUT']);
  add_block('simulink/Sources/From Workspace',[mdl '/src'],'VariableName','stim_t7rep', ...
            'SampleTime','1','Interpolate','off','OutputAfterFinalValue','Holding final value');
  add_block('simulink/Signal Routing/Demux',[mdl '/dm'],'Outputs','4'); add_line(mdl,'src/1','dm/1');
  for j = 1:4
    add_block('simulink/Signal Attributes/Data Type Conversion',[mdl '/c' num2str(j)], ...
              'OutDataTypeStr','fixdt(1,32,20)');
    add_line(mdl,['dm/' num2str(j)],['c' num2str(j) '/1']);
    add_line(mdl,['c' num2str(j) '/1'],['DUT/' num2str(j)]);
  end
  add_block('simulink/Sinks/To Workspace',[mdl '/Aw'],'VariableName','Aw','SaveFormat','Array');
  add_line(mdl,'DUT/1','Aw/1');
  set_param(mdl,'Solver','FixedStepDiscrete','FixedStep','1', ...
            'StopTime',num2str(N*hold+40),'SaveOutput','off');
  so = sim(mdl); Aall = double(so.get('Aw')); close_system(mdl,0);

  idx = hold*(1:N).' - 20;                 % campiona a fine control-step, oltre la latenza
  assert(max(idx) <= numel(Aall), 't7_block_replay: simulazione troppo corta (%d campioni)', numel(Aall));
  A = Aall(idx);
end
