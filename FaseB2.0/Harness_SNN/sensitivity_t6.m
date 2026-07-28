function sensitivity_t6()
%SENSITIVITY_T6  Prova di sensibilita di T6-EXACT: 1 LSB corrotto sul golden -> DEVE vedere nMismatch>=1.
%  File a se (non local function) per essere chiamabile da matlab -batch. Riusa TB/runner/ROOT dell'harness.
  here = fileparts(mfilename('fullpath')); mroot = fullfile(here,'..','..','matlab');
  addpath(mroot); addpath(fullfile(here,'..','common'));
  ROOT='D:/zbd_tier'; hdlsrc=fullfile(mroot,'hdlsrc_donatello_tier','rtlgen_mdl');
  tb=fullfile(here,'tb_tier_stream.v'); runner=fullfile(here,'..','common','rtl_run_xsim.sh');
  fwd = @(p) strrep(p,'\','/');
  if ~exist(fullfile(hdlsrc,'Donatello_Tier.vhd'),'file')
    info = rtl_gen_dut('Donatello_Tier', fullfile(mroot,'hdlsrc_donatello_tier'), 'VHDL', {'TIER','BALANCED','NFRAC','13'});
    hdlsrc = info.outdir;
  end
  tier_export_vectors(1, 'sens_1', ROOT);                 % 1 traiettoria -> stim_sens_1.mem, gold_sens_1.mem
  ds = load(fullfile(mroot,'test_dataset.mat')); K1 = size(ds.trajectories{1}.val,2);
  gf = fullfile(ROOT,'gold_sens_1.mem'); L = strsplit(strtrim(fileread(gf)), newline);
  vv = hex2dec(L{1}); L{1} = sprintf('%06X', bitxor(uint32(vv), uint32(1)));   % +1 LSB sul 1o param
  f = fopen(gf,'w'); fprintf(f,'%s\n', L{:}); fclose(f);
  cmd = sprintf('bash "%s" "%s" "%s" "%s" %d 500 1 stim_sens gold_sens', fwd(runner), ROOT, fwd(hdlsrc), fwd(tb), K1);
  [~,out] = system(cmd);
  nm = str2double(regexp(out,'RTLRES nMismatch=(\d+)','tokens','once'));
  assert(nm>=1, 'SENSIBILITA FALLITA: 1 LSB corrotto ma T6-EXACT vede 0 -> cancello CIECO');
  fprintf('=== SENSIBILITA T6-EXACT OK: 1 LSB corrotto -> nMismatch=%d ===\n', nm);
end
