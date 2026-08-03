function sensitivity_B1()
%SENSITIVITY_B1  [Fase B2.0-2a-M2] 1 LSB su un accel golden -> B-1 DEVE riportare nMismatch>=1. Se resta
%  0 il testbench e' CIECO. Gemello di sensitivity_A1 per Harness B.
  here = fileparts(mfilename('fullpath'));
  build_acciidm_m_golden();
  hdlsrc = fullfile(here,'hdlsrc_donatello_acc_iidm_m_v','rtlgen_mdl');
  od = fullfile(here,'axi','acciidm_m');
  rtl_export_vectors('ctrl', 1, 'sens', od);
  gf = fullfile(od,'gold_sens.mem'); L = strsplit(strtrim(fileread(gf)), newline);
  L{1} = sprintf('%04X', bitxor(uint32(hex2dec(L{1})), uint32(1)));   % +1 LSB sul 1o accel
  f = fopen(gf,'w'); fprintf(f,'%s\n', L{:}); fclose(f);
  m = load(fullfile(od,'meta_sens.mat'));
  r = rtl_run_xsim(od, hdlsrc, 'sens', m.K, 500, 'run_xsim_acciidm_m.sh');
  assert(r.nMismatch >= 1, 'SENSIBILITA B-1 FALLITA: 1 LSB corrotto ma nMismatch=0 -> cancello CIECO.');
  fprintf('=== SENSIBILITA B-1 OK: 1 LSB -> nMismatch=%d ===\n', r.nMismatch);
end
