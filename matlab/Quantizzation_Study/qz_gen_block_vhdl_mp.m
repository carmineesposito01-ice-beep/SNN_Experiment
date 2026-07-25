function outdir = qz_gen_block_vhdl_mp(nf, outdir)
%QZ_GEN_BLOCK_VHDL_MP  [Quantizzation_Study] Genera il VHDL del blocco Donatello a PRECISIONE MISTA
%  (6 nfrac per-campo, nf = [nV nfat nacc naccw nraw nw]) in un modello TEMPORANEO (la libreria non e' toccata).
%  Copia di qz_gen_block_vhdl: inietta ANCHE il sorgente di qz_snn_types_mp nella chart e sostituisce le
%  chiamate snn_types('fixed',13) -> qz_snn_types_mp('fixed',[nf...]). A nf=[13x6] i tipi coincidono con
%  snn_types('fixed',13) (Task 0 Gate 1) -> il VHDL @full-precision e' equivalente a quello unico @13
%  (verificato dal cancello diff esterno). Il DECODE resta En13.
  if nargin < 2 || isempty(outdir), outdir = 'D:/zbd_qz/mpX'; end
  assert(numel(nf) == 6, 'nf deve avere 6 elementi [V fatigue acc accw raw w]');
  here  = fileparts(mfilename('fullpath'));                 % .../Quantizzation_Study
  mroot = fileparts(here);                                  % .../matlab
  addpath(mroot); addpath(here);
  gen_b2_rom('Donatello');
  srcRom   = fileread(fullfile(mroot,'b2_rom_active.m'));
  % srcTypes = snn_types (per il path 'double' e le chiamate non-'fixed',13) + qz_snn_types_mp (iniettato)
  srcTypes = [fileread(fullfile(mroot,'snn_types.m')) newline newline ...
              fileread(fullfile(here,'qz_snn_types_mp.m'))];
  srcFsm   = fileread(fullfile(mroot,'snn_b2_fsm.m'));
  srcLut   = [fileread(fullfile(mroot,'snn_decode_lut.m')) newline newline ...
              fileread(fullfile(mroot,'decode_a.m'))  newline newline fileread(fullfile(mroot,'decode_a1.m')) newline newline ...
              fileread(fullfile(mroot,'decode_a2.m')) newline newline fileread(fullfile(mroot,'decode_b.m'))  newline newline ...
              fileread(fullfile(mroot,'decode_b1.m')) newline newline fileread(fullfile(mroot,'decode_b2.m')) newline newline ...
              fileread(fullfile(mroot,'decode_c.m'))  newline newline fileread(fullfile(mroot,'decode_c1.m')) newline newline ...
              fileread(fullfile(mroot,'decode_c2.m'))];
  d = load(fullfile(mroot,'champions_export.mat')); champs = d.champions;
  if iscell(champs), champs = [champs{:}]; end
  c = champs(find(arrayfun(@(x) strcmp(char(string(x.name)),'Donatello'), champs),1));
  nrm = double(c.norm(:));

  % snnCode di riferimento (con i suoi 13), poi sostituisce TUTTE le chiamate snn_types('fixed',13) -> per-campo
  snnRef = snn_chart_code(srcRom, srcTypes, srcFsm, nrm, true);   % pipe=true (splitpipe)
  pat = "snn_types\(\s*'fixed'\s*,\s*13\s*\)";
  nsub = numel(regexp(snnRef, pat));
  assert(nsub >= 2, 'attesi >=2 snn_types(''fixed'',13) in snnCode (Tt+core), trovati %d', nsub);
  rep = sprintf("qz_snn_types_mp('fixed', [%d %d %d %d %d %d])", nf(1),nf(2),nf(3),nf(4),nf(5),nf(6));
  snnCode = regexprep(snnRef, pat, rep);
  assert(numel(regexp(snnCode, pat)) == 0, 'restano chiamate snn_types(''fixed'',13) non sostituite');
  assert(contains(snnCode, 'qz_snn_types_mp('), 'sostituzione per-campo non applicata');
  decCode = dec_chart_code(srcLut, 'p5', 64, 'shared');           % decode fisso En13 (FAST)

  mdl = 'qz_gen_mp_mdl'; if bdIsLoaded(mdl), close_system(mdl,0); end
  new_system(mdl); load_system(mdl); cleanup = onCleanup(@() close_system(mdl,0)); %#ok<NASGU>
  sub = [mdl '/Donatello']; add_block('built-in/Subsystem', sub);
  mount_split(sub, {'s','v','dv','v_l'}, {'v0','T','s0','a','b'}, snnCode, decCode);
  if exist(outdir,'dir'), rmdir(outdir,'s'); end
  outdir = rtl_gen_dut_local(sub, outdir);
end


function folder = rtl_gen_dut_local(sub, outdir)
% Copia mirata della logica makehdl di rtl_gen_dut, ma su un SUBSYSTEM gia' costruito in memoria
% (non un blocco di libreria). Avvolge sub con Constant(fixdt 1,32,20) sugli ingressi + Outport sulle uscite.
  mdl = bdroot(sub); blk = get_param(sub,'Name');
  nIn = 4; nOut = 5; vals = {'10','6','2','4'};
  for j = 1:nIn
    add_block('simulink/Sources/Constant', [mdl '/i' num2str(j)], 'Value', vals{min(j,4)}, ...
              'OutDataTypeStr','fixdt(1,32,20)','SampleTime','1');
    add_line(mdl, ['i' num2str(j) '/1'], [blk '/' num2str(j)]);
  end
  for j = 1:nOut
    add_block('built-in/Outport', [mdl '/o' num2str(j)], 'Port', num2str(j));
    add_line(mdl, [blk '/' num2str(j)], ['o' num2str(j) '/1']);
  end
  set_param(mdl,'Solver','FixedStepDiscrete','FixedStep','1','StopTime','10');
  set_param(mdl,'SimulationCommand','update');           % compila: rivela errori nella chart
  makehdl(sub, 'TargetLanguage','VHDL', 'TargetDirectory', outdir, 'GenerateHDLTestBench','off');
  src = dir(fullfile(outdir,'**','*.vhd'));
  assert(~isempty(src), 'nessun VHDL generato');
  assert(any(strcmp({src.name},'DualPortRAM_generic.vhd')), ...
         'manca DualPortRAM -> non e'' l''architettura time-mux del deployato');
  folder = src(1).folder;
end
