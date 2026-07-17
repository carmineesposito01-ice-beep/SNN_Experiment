function info = rtl_gen_dut(blockName, outdir, lang)
%RTL_GEN_DUT  Genera l'RTL di un blocco di snn_champions_lib verso `outdir` (persistente), scrive
%  l'ordine di compilazione (pkg -> leaf -> top) e (VHDL) STAMPA la dichiarazione ENTITY grezza.
%  lang = 'VHDL' (default) | 'Verilog'. ⚠️ Il controllore ACC-IIDM_M va in **Verilog**: i registri VHDL
%  partono `U` e il divisore combinatorio dell'IIDM manda un indice-LUT a -1 a time-0 in xsim (metavalue);
%  Verilog inizializza i registri a 0 (`initial`) -> nessun U a time-0. La SNN (no divisore) va bene in VHDL.
%  makehdl non gira su un blocco di libreria: si avvolge in un subsystem nominato come il blocco. Ingressi
%  driven da Constant fixdt(1,32,20): rendono il modello compilabile, non diventano porte.
  here = fileparts(mfilename('fullpath'));
  if nargin < 3 || isempty(lang), lang = 'VHDL'; end
  ext = 'vhd'; if strcmpi(lang,'Verilog'), ext = 'v'; end
  if nargin < 2 || isempty(outdir)
    outdir = fullfile(here, ['hdlsrc_' lower(regexprep(blockName,'\W','_')) ...
                             repmat('_v',1,strcmpi(lang,'Verilog'))]);
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
  makehdl(sub, 'TargetLanguage', lang, 'TargetDirectory', outdir, 'GenerateHDLTestBench','off');

  src = dir(fullfile(outdir,'**',['*.' ext]));
  assert(~isempty(src), 'nessun %s generato per %s', lang, blockName);
  assert(any(strcmp({src.name},['DualPortRAM_generic.' ext])), ...
         'manca DualPortRAM -> non e'' l''architettura time-mux del deployato');
  folder = src(1).folder;
  topf   = fullfile(folder, [blockName '.' ext]);
  assert(exist(topf,'file')>0, 'manca il top %s.%s. File generati: %s', ...
         blockName, ext, strjoin({src.name}, ', '));

  % ordine di compilazione: package -> leaf (chart, DualPortRAM) -> top (per Verilog l'ordine e' innocuo)
  names = {src.name};
  isPkg = ~cellfun(@isempty, regexp(names, ['_pkg\.' ext '$'], 'once'));
  isTop = strcmp(names, [blockName '.' ext]);
  order = [names(isPkg), names(~isPkg & ~isTop), names(isTop)];
  fid = fopen(fullfile(folder,'compile_order.txt'),'w'); fprintf(fid,'%s\n', order{:}); fclose(fid);

  info = struct('outdir', folder, 'top', blockName, 'lang', lang, 'nIn', nIn, 'nOut', nOut, 'files', {order});
  fprintf('\n=== %s generato: %s -> %s (%d file) ===\n', lang, blockName, folder, numel(src));
  fprintf('compile order: %s\n', strjoin(order, ' '));

  if strcmpi(lang,'VHDL')     % stampa l'ENTITY grezza (nomi + larghezze reali per il TB)
    txt = fileread(topf);
    si = regexpi(txt, ['ENTITY\s+' blockName '\s+IS'], 'start', 'once');
    ei = regexpi(txt, ['END\s+' blockName '\s*;'], 'end', 'once');
    fprintf('\n---- ENTITY %s (grezza) ----\n%s\n----------------------------\n', ...
            blockName, strtrim(txt(si:ei)));
  end
  close_system(mdl, 0);
end
