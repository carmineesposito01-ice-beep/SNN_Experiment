function dmax = probe_divide_bitexact(P, latMode, rnd)
%PROBE_DIVIDE_BITEXACT  [SP4-M-FSM G1, make-or-break] HDLMathLib/Divide e' bit-identico a divide()-SP3
%  sulle coppie reali P? P (Nx2) = [num den] (double, da collect_div_pairs). Confronta il dataOut del
%  blocco (ShiftAdd, rounding rnd, OutType T.acc) con divide(numerictype(T.acc),num,den) di SP3.
%    rnd='Zero'    -> replica SP3 (fimath acc_types): atteso dmax = 0.
%    rnd='Nearest' -> PROVA DI SENSIBILITA': il gate deve DIVERGERE (dmax>0), o non discrimina il rounding.
%
%  VETTORIALE (non streaming): il blocco processa tutte le N coppie element-wise in un ingresso vettoriale
%  [N x 1] costante -> bastano ~60 passi (finche' dataOut si stabilizza dopo la latenza) invece di N passi.
%  Da O(N passi) a O(latenza): 300k coppie in secondi, non ~23 min. (L'accelerator mode NON e' usabile: il
%  blocco Divide non compila in accelerator, 'ValidLine' senza tipi.)
  % latMode='Zero' = blocco COMBINATORIO (latenza 0): stesso ShiftAdd/RndMeth -> stesso valore bit-identico
  % del pipelinato (la pipeline sposta i bit nel TEMPO, non li cambia), ma la sim e' 1 passo invece di ~50
  % -> il gate su 300k coppie gira in secondi. La LATENZA/pipeline le misura il Task 4 (OOC), non il gate.
  if nargin < 2 || isempty(latMode), latMode = 'Zero'; end
  if nargin < 3 || isempty(rnd),     rnd     = 'Zero'; end
  Tt = acc_types('fixed'); acc = Tt.acc; A = numerictype(acc);
  num = cast(P(:,1), 'like', acc); den = cast(P(:,2), 'like', acc);
  qref = divide(A, num, den);                       % riferimento SP3
  qb   = run_divide_block(P(:,1), P(:,2), A, latMode, rnd);
  assert(numel(qb) == numel(qref), 'run_divide_block ha reso %d risultati su %d attesi', numel(qb), numel(qref));
  dmax = max(abs(double(qb) - double(qref)));
  fprintf('probe_divide_bitexact: N=%d lat=%s rnd=%-8s -> dmax = %.6g\n', numel(qref), latMode, rnd, dmax);
end


function q = run_divide_block(numD, denD, A, latMode, rnd)
%RUN_DIVIDE_BLOCK  Le N coppie (num,den) come UN ingresso vettoriale [N x 1] costante attraverso
%  HDLMathLib/Divide; il dataOut si stabilizza dopo la latenza -> prendo l'ultimo passo. Porte fissate
%  (micro-test): /1 dividend, /2 divisor, /3 validIn; out /1 dataOut.
  N = numel(numD);
  dts = sprintf('fixdt(1,%d,%d)', A.WordLength, A.FractionLength);
  assignin('base','dnv', numD(:)); assignin('base','ddv', denD(:));
  mdl = 'pdb'; if bdIsLoaded(mdl), close_system(mdl,0); end
  new_system(mdl); load_system(mdl);
  add_block('simulink/Sources/Constant',[mdl '/sn'],'Value','dnv','SampleTime','1');
  add_block('simulink/Sources/Constant',[mdl '/sd'],'Value','ddv','SampleTime','1');
  add_block('simulink/Signal Attributes/Data Type Conversion',[mdl '/cn'],'OutDataTypeStr',dts);
  add_block('simulink/Signal Attributes/Data Type Conversion',[mdl '/cd'],'OutDataTypeStr',dts);
  add_block('simulink/Sources/Constant',[mdl '/v1'],'Value','true(size(dnv))','OutDataTypeStr','boolean','SampleTime','1');
  add_block('HDLMathLib/Divide',[mdl '/DUT']);
  set_param([mdl '/DUT'],'latencyMode',latMode,'RndMeth',rnd,'OutDataTypeStr',dts);
  add_block('simulink/Sinks/To Workspace',[mdl '/oq'],'VariableName','oq','SaveFormat','Array','SampleTime','1');
  add_line(mdl,'sn/1','cn/1'); add_line(mdl,'sd/1','cd/1');
  add_line(mdl,'cn/1','DUT/1'); add_line(mdl,'cd/1','DUT/2'); add_line(mdl,'v1/1','DUT/3');
  add_line(mdl,'DUT/1','oq/1');
  stopT = 3; if ~strcmpi(latMode,'Zero'), stopT = 50; end   % Zero=combinatorio (1 passo basta); pipelinato: > latenza
  set_param(mdl,'Solver','FixedStepDiscrete','FixedStep','1','StopTime',num2str(stopT),'SaveOutput','off');
  so = sim(mdl);
  oq = so.get('oq');
  q = double(oq(end,:)).';                          % ultimo passo (dopo latenza) = i N risultati stabili
  close_system(mdl,0);
end
