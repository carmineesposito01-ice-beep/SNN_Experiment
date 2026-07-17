function info = rtl_gen_dut(blockName, outdir)
%RTL_GEN_DUT  Genera il VHDL di un blocco di snn_champions_lib verso `outdir` (persistente), scrive
%  l'ordine di compilazione (pkg -> leaf -> top) e STAMPA la dichiarazione ENTITY grezza (nomi/larghezze
%  delle porte, da usare nel TB — non assunte). makehdl non gira su un blocco di libreria: si avvolge in
%  un subsystem nominato come il blocco (cosi' l'entita top ha quel nome). Ingressi driven da Constant
%  fixdt(1,32,20): servono solo a rendere il modello compilabile, non diventano porte (le porte sono
%  quelle del blocco). Modellato su run_block_hdl_gate (che genera VHDL con successo).
  here = fileparts(mfilename('fullpath'));
  if nargin < 2 || isempty(outdir)
    outdir = fullfile(here, ['hdlsrc_' lower(regexprep(blockName,'\W','_'))]);
  end
  if exist(outdir,'dir'), rmdir(outdir,'s'); end
  bdclose('all');
  lib = 'snn_champions_lib';
  if ~bdIsLoaded(lib), load_system(fullfile(here,[lib '.slx'])); end
  mdl = 'rtlgen_mdl'; if bdIsLoaded(mdl), close_system(mdl,0); end
  new_system(mdl); load_system(mdl);
  sub = [mdl '/' blockName];
  add_block([lib '/' blockName], sub);
  nIn  = numel(find_system([lib '/' blockName],'SearchDepth',1,'BlockType','Inport'));
  nOut = numel(find_system([lib '/' blockName],'SearchDepth',1,'BlockType','Outport'));
  vals = {'10','6','2','4'};
  for j = 1:nIn
    add_block('simulink/Sources/Constant', [mdl '/i' num2str(j)], 'Value', vals{min(j,4)}, ...
              'OutDataTypeStr','fixdt(1,32,20)','SampleTime','1');
    add_line(mdl, ['i' num2str(j) '/1'], [blockName '/' num2str(j)]);
  end
  for j = 1:nOut
    add_block('built-in/Outport', [mdl '/o' num2str(j)], 'Port', num2str(j));
    add_line(mdl, [blockName '/' num2str(j)], ['o' num2str(j) '/1']);
  end
  set_param(mdl,'Solver','FixedStepDiscrete','FixedStep','1','StopTime','10');
  set_param(mdl,'SimulationCommand','update');           % compila: rivela errori nella chart
  makehdl(sub, 'TargetLanguage','VHDL', 'TargetDirectory', outdir, 'GenerateHDLTestBench','off');

  vhd = dir(fullfile(outdir,'**','*.vhd'));
  assert(~isempty(vhd), 'nessun VHDL generato per %s', blockName);
  assert(any(strcmp({vhd.name},'DualPortRAM_generic.vhd')), ...
         'manca DualPortRAM -> non e'' l''architettura time-mux del deployato');
  folder = vhd(1).folder;
  topf   = fullfile(folder, [blockName '.vhd']);
  assert(exist(topf,'file')>0, 'manca l''entita top %s.vhd. File generati: %s', ...
         blockName, strjoin({vhd.name}, ', '));

  % ordine di compilazione: package -> leaf (chart, DualPortRAM) -> top
  names = {vhd.name};
  isPkg = ~cellfun(@isempty, regexp(names, '_pkg\.vhd$', 'once'));
  isTop = strcmp(names, [blockName '.vhd']);
  order = [names(isPkg), names(~isPkg & ~isTop), names(isTop)];
  fid = fopen(fullfile(folder,'compile_order.txt'),'w'); fprintf(fid,'%s\n', order{:}); fclose(fid);

  info = struct('outdir', folder, 'top', blockName, 'nIn', nIn, 'nOut', nOut, 'files', {order});
  fprintf('\n=== VHDL generato: %s -> %s (%d file) ===\n', blockName, folder, numel(vhd));
  fprintf('compile order: %s\n', strjoin(order, ' '));

  % stampa la dichiarazione ENTITY grezza (la leggo io: nomi + larghezze reali)
  txt = fileread(topf);
  si = regexpi(txt, ['ENTITY\s+' blockName '\s+IS'], 'start', 'once');
  ei = regexpi(txt, ['END\s+' blockName '\s*;'], 'end', 'once');
  fprintf('\n---- ENTITY %s (grezza) ----\n%s\n----------------------------\n', ...
          blockName, strtrim(txt(si:ei)));
  close_system(mdl, 0);
end
