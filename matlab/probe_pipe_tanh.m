function probe_pipe_tanh(cfgs)
%PROBE_PIPE_TANH  [B2.0-2b F1, make-or-break] HDL Coder riesce a PIPELINARE bit-exact il tanh nativo
%  (stadio phase==6 di Donatello_ACC_IIDM_M, 207 livelli) coi suoi attributi automatici? Genera il VHDL
%  del blocco M in piu' config di pipeline, in cartelle separate (matlab/hdl_pipe/<tag>), per la sintesi
%  OOC (scripts/synth_acc_iidm.tcl -> RESULT/CRITPATH = il verdetto). NON tocca la libreria committata:
%  lavora su un modello scratch m_pipe_<tag> con una COPIA del blocco (LinkStatus=none), come
%  probe_acciidm_sharing.
%
%  Leve (attributi HDL Coder, NON sorgente: il tanh e' un operatore nativo atomico, non spezzabile a mano):
%   - OutputPipeline (subsystem): N registri sull'uscita del DUT.
%   - DistributedPipelining (subsystem, richiede OutputPipeline>=1): ridistribuisce quei registri
%     ATTRAVERSO la logica combinatoria -> e' cio' che POTREBBE spezzare i 207 livelli del tanh.
%   - ClockRatePipelining (MODEL): registri a clock-rate sfruttando l'oversampling del time-mux.
%  Verdetto make-or-break: se NESSUNA config alza Fmax lasciando il critpath sul tanh (st.dd -> th),
%  il tool NON pipelina il tanh nativo -> F1 si ferma a 9,30 (onesto), senza aprire il core.
  if nargin < 1 || isempty(cfgs)
    % {tag, OutputPipeline, DistributedPipelining, ClockRatePipelining}
    cfgs = { 'baseline', 0, 'off', 'off'
             'op2_dist', 2, 'on',  'off'
             'op4_dist', 4, 'on',  'off'
             'op8_dist', 8, 'on',  'off'
             'op4_crp',  4, 'on',  'on'  };
  end
  md  = 'D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab';
  addpath(md);
  out = fullfile(md, 'hdl_pipe'); if exist(out,'dir'), rmdir(out,'s'); end; mkdir(out);
  lib = 'snn_champions_lib';
  blk = 'Donatello_ACC_IIDM_M';

  fprintf('\n==== PROBE pipeline tanh (B2.0-2b F1, make-or-break) ====\n');
  for i = 1:size(cfgs,1)
    tag = cfgs{i,1}; op = cfgs{i,2}; dist = cfgs{i,3}; crp = cfgs{i,4};
    bdclose('all');
    load_system(fullfile(md,[lib '.slx'])); set_param(lib,'Lock','off');
    mdl = ['m_pipe_' tag]; if bdIsLoaded(mdl), close_system(mdl,0); end
    new_system(mdl); load_system(mdl);
    dut = [mdl '/DUT'];
    add_block([lib '/' blk], dut);
    try, set_param(dut,'LinkStatus','none'); catch, end     % slink: senza, la chart e' read-only
    vals = {'10','6','2','4'};
    for j = 1:4
      add_block('simulink/Sources/Constant',[mdl '/i' num2str(j)], ...
                'Value',vals{j},'OutDataTypeStr','fixdt(1,32,20)','SampleTime','1');
      add_line(mdl,['i' num2str(j) '/1'],['DUT/' num2str(j)]);
    end
    add_block('built-in/Outport',[mdl '/o'],'Port','1'); add_line(mdl,'DUT/1','o/1');
    set_param(mdl,'Solver','FixedStepDiscrete','FixedStep','1','StopTime','10');

    applied = '';
    if op > 0
      try, hdlset_param(dut,'OutputPipeline',op); applied=[applied sprintf('OP=%d ',op)];
      catch e, fprintf('[%s] OutputPipeline: %s\n',tag,e.message); end
    end
    try, hdlset_param(dut,'DistributedPipelining',dist); applied=[applied 'DIST=' dist ' '];
    catch e, fprintf('[%s] DistributedPipelining: %s\n',tag,e.message); end
    try, hdlset_param(mdl,'ClockRatePipelining',crp); applied=[applied 'CRP=' crp];
    catch e, fprintf('[%s] ClockRatePipelining: %s\n',tag,e.message); end

    tgt = fullfile(out, tag);
    try
      set_param(mdl,'SimulationCommand','update');          % propaga i tipi, rivela errori chart
      makehdl(dut,'TargetLanguage','VHDL','TargetDirectory',tgt,'GenerateHDLTestBench','off');
      v = dir(fullfile(tgt,'**','*.vhd'));
      fprintf('>> %-10s applied[%s]: VHDL OK (%d file) -> %s\n', tag, strtrim(applied), numel(v), tgt);
    catch e
      fprintf('>> %-10s FALLITO: %s\n', tag, regexprep(e.message,'\s+',' '));
    end
    close_system(mdl,0);
  end
  bdclose('all');
  fprintf('\nVHDL per la sintesi OOC in %s (una cartella per config).\n', out);
  fprintf('Sintesi: vivado -mode batch -source scripts/synth_acc_iidm.tcl -tclargs %s\\<tag> %s\\<tag>\\synth <tag>\n', out, out);
end
