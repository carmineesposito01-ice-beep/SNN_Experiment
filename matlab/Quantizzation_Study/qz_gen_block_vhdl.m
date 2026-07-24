function outdir = qz_gen_block_vhdl(nfrac, outdir)
%QZ_GEN_BLOCK_VHDL  [Quantizzation_Study] Genera il VHDL del blocco Donatello (forward SNN splitpipe +
%  decode LUT-64) a un dato nfrac, in un modello TEMPORANEO (la libreria snn_champions_lib.slx NON e'
%  toccata). Riusa i mattoni condivisi (mount_split/snn_chart_code/dec_chart_code/rtl_gen_dut logic).
%
%  ⚠️ CORREZIONE AL PIANO 2026-07-24: la parametrizzazione nfrac si applica all'INTERO snnCode, non al solo
%  srcFsm. snn_chart_code emette DUE `snn_types('fixed',13)`: il `Tt` del normalize (l'uscita xn = tipo V) e
%  il core snn_b2_fsm. Per spec §1 nfrac scala V (= uscita normalize) -> entrambi vanno scalati, altrimenti
%  a nfrac basso il normalize resterebbe a 13 (risorse sovrastimate). Il DECODE resta En13 (lo studio varia
%  il core, non il decode; il cast raw@En_nfrac -> En13 e' lossless per nfrac<=13).
%
%  Config di riferimento: forward corrente + SPLITPIPE + decode 'p5' (= tier FAST-like, massimo Fmax). Le
%  curve caratterizzano il TREND risorse/potenza/Fmax vs nfrac + il ginocchio (che e' tier-INDIPENDENTE,
%  guidato dall'accuratezza); il tier deployato (BAL) sposta gli assoluti, non il ginocchio.
  if nargin < 2 || isempty(outdir), outdir = 'D:/zbd_qz/nX'; end
  mroot = fileparts(fileparts(mfilename('fullpath')));   % .../matlab
  addpath(mroot);
  gen_b2_rom('Donatello');
  srcRom   = fileread(fullfile(mroot,'b2_rom_active.m'));
  srcTypes = fileread(fullfile(mroot,'snn_types.m'));
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

  % snnCode di riferimento (con i suoi 13), poi parametrizza TUTTI i snn_types('fixed',13) -> nfrac
  snnRef = snn_chart_code(srcRom, srcTypes, srcFsm, nrm, true);   % pipe=true (splitpipe)
  pat = "snn_types\(\s*'fixed'\s*,\s*13\s*\)";
  snnCode = regexprep(snnRef, pat, sprintf("snn_types('fixed', %d)", nfrac));
  nsub = numel(regexp(snnRef, pat));
  assert(nsub >= 2, 'attesi >=2 snn_types(''fixed'',13) in snnCode (Tt+core), trovati %d', nsub);
  if nfrac == 13
    assert(isequal(snnCode, snnRef), 'param a nfrac=13 NON e'' no-op');   % cancello bit-exact
  end
  decCode = dec_chart_code(srcLut, 'p5', 64, 'shared');           % decode fisso En13 (FAST)

  mdl = 'qz_gen_mdl'; if bdIsLoaded(mdl), close_system(mdl,0); end
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
