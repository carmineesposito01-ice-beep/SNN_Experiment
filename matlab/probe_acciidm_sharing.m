function probe_acciidm_sharing()
%PROBE_ACCIIDM_SHARING  [SP4-M Task 1, make-or-break] Il resource sharing di HDL Coder condivide+sequenzia
%  le 5 divide() dell'ACC-IIDM? Genera il VHDL del blocco Donatello_ACC_IIDM in piu' config, in cartelle
%  separate (matlab/hdl_sp4m/<tag>), e conta i divisori nel VHDL come PRE-INDICATORE grezzo. Il VERDETTO
%  e' la sintesi OOC (scripts/synth_acc_iidm.tcl -> RESULT/CRITPATH). NON tocca la libreria committata:
%  lavora su copie in modelli scratch m_<tag>.
%
%  STRUTTURA REALE (verificata su build_hdl_variants.m):
%   - Donatello_ACC_IIDM e' un Subsystem che contiene la MATLAB Function 'SNN_ACC';
%   - le 5 divisioni stanno DENTRO quella chart (acc_iidm_open inlinato).
%  Quindi il resource sharing degli OPERATORI si applica sul blocco MATLAB Function interno
%  (DUT/SNN_ACC), non sul subsystem esterno; e il blocco copiato va SLINKATO dalla libreria
%  (LinkStatus=none) o il contenuto resta read-only -> hdlset_param fallirebbe per un artefatto,
%  dando un FALSO "config non basta". (Root cause, non workaround.)
  md = 'D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab';
  addpath(md);
  out = fullfile(md, 'hdl_sp4m'); if exist(out,'dir'), rmdir(out,'s'); end; mkdir(out);
  lib = 'snn_champions_lib';

  % {tag, SharingFactor, ClockRatePipelining}
  cfgs = { 'baseline',  1,  'off'      % = SP3 (nessuna condivisione): riferimento, deve riprodurre ~10846 LUT / ~2.0 MHz
           'share5_cp', 5,  'on'       % condividi fino a 5 -> 1 divisore, sequenziato via clock-rate pipelining
           'share5',    5,  'off' };   % condividi senza clock-rate pipelining (vediamo se sequenzia lo stesso)

  fprintf('\n==== PROBE resource sharing ACC-IIDM (SP4-M Task 1, make-or-break) ====\n');
  for i = 1:size(cfgs,1)
    tag = cfgs{i,1}; sf = cfgs{i,2}; crp = cfgs{i,3};
    bdclose('all');
    load_system(fullfile(md,[lib '.slx'])); set_param(lib,'Lock','off');
    mdl = ['m_' tag]; if bdIsLoaded(mdl), close_system(mdl,0); end
    new_system(mdl); load_system(mdl);
    dut = [mdl '/DUT'];
    add_block([lib '/Donatello_ACC_IIDM'], dut);
    % SLINK dalla libreria: senza, il contenuto (la MATLAB Function) e' read-only e hdlset_param sul
    % blocco interno fallisce -> falso negativo. Se non e' linkato, no-op.
    try, set_param(dut,'LinkStatus','none'); catch, end

    % harness: 4 Constant fixed (s,v,dv,v_l) -> DUT -> 1 Outport (accel)
    vals = {'10','6','2','4'};
    for j=1:4
      add_block('simulink/Sources/Constant',[mdl '/i' num2str(j)], ...
                'Value',vals{j},'OutDataTypeStr','fixdt(1,32,20)','SampleTime','1');
      add_line(mdl,['i' num2str(j) '/1'],['DUT/' num2str(j)]);
    end
    add_block('built-in/Outport',[mdl '/o'],'Port','1'); add_line(mdl,'DUT/1','o/1');
    set_param(mdl,'Solver','FixedStepDiscrete','FixedStep','1','StopTime','10');

    % --- config di resource sharing ---
    % Punto GIUSTO: la MATLAB Function interna (le divisioni stanno li'). Fallback: il subsystem esterno.
    % Ogni set in try/catch: un nome/param non valido e' un DATO (lo stampa), non blocca le altre config.
    fcn = [dut '/SNN_ACC'];
    applied = '';
    if sf > 1
      if getSimulinkBlockHandle(fcn) > 0
        try
          hdlset_param(fcn,'SharingFactor',sf); applied=[applied 'fcn.SF ']; %#ok<AGROW>
        catch e, fprintf('[%s] SharingFactor su SNN_ACC: %s\n',tag,e.message); end
      else
        fprintf('[%s] ATTENZIONE: %s non trovato (struttura cambiata?)\n',tag,fcn);
      end
      try
        hdlset_param(dut,'SharingFactor',sf); applied=[applied 'dut.SF ']; %#ok<AGROW>
      catch e, fprintf('[%s] SharingFactor su DUT: %s\n',tag,e.message); end
    end
    try
      hdlset_param(mdl,'ClockRatePipelining',crp); applied=[applied 'CRP=' crp]; %#ok<AGROW>
    catch e, fprintf('[%s] ClockRatePipelining: %s\n',tag,e.message); end

    tgt = fullfile(out, tag);
    try
      set_param(mdl,'SimulationCommand','update');   % propaga i tipi, rivela errori chart
      makehdl(dut,'TargetLanguage','VHDL','TargetDirectory',tgt,'GenerateHDLTestBench','off');
      v = dir(fullfile(tgt,'**','*.vhd'));
      nd = count_dividers(v);
      fprintf('>> %-10s SF=%d CRP=%-3s applied[%s]: VHDL OK (%d file, %d byte) | divisori~%d -> %s\n', ...
              tag, sf, crp, strtrim(applied), numel(v), sum([v.bytes]), nd, tgt);
    catch e
      fprintf('>> %-10s FALLITO: %s\n', tag, regexprep(e.message,'\s+',' '));
    end
    close_system(mdl,0);
  end
  bdclose('all');
  fprintf('\nVHDL per la sintesi OOC in %s (una cartella per config).\n', out);
  fprintf('Prossimo: sintesi OOC baseline/share5_cp/share5 -> RESULT/CRITPATH (il verdetto).\n');
end

function n = count_dividers(v)
%COUNT_DIVIDERS  Pre-indicatore GREZZO (non il verdetto): conta nel VHDL i token che contengono 'div'.
%  Rumoroso in assoluto (pesca anche commenti/segnali), ma a parita' di codice il CONFRONTO
%  baseline<->share e' indicativo: se il sharing riduce i divisori reali, il conteggio scende.
  n = 0;
  for k = 1:numel(v)
    try
      t = fileread(fullfile(v(k).folder, v(k).name));
    catch, continue; end
    n = n + numel(regexpi(t,'\<[A-Za-z_]*div[A-Za-z0-9_]*\>','match'));
  end
end
