function sensitivity_A1()
%SENSITIVITY_A1  [Fase B2.0-2a] Rompe apposta 1 LSB su un param del golden: A-1 DEVE riportare
%  nMismatch>=1. Se resta 0, il testbench e' CIECO (non confronta davvero) -> da aggiustare prima di
%  fidarsene ("un cancello che non puo' fallire non e' un cancello").
  here = fileparts(mfilename('fullpath'));
  build_champion_golden();
  hdlsrc = fullfile(here,'hdlsrc_donatello_champion','rtlgen_mdl');
  od = fullfile(here,'axi','champion');
  rtl_export_vectors('snn', 1, 'sens', od);
  gf = fullfile(od,'gold_sens.mem'); L = strsplit(strtrim(fileread(gf)), newline);
  L{1} = sprintf('%06X', bitxor(uint32(hex2dec(L{1})), uint32(1)));   % +1 LSB sul 1o param
  f = fopen(gf,'w'); fprintf(f,'%s\n', L{:}); fclose(f);
  m = load(fullfile(od,'meta_sens.mat'));
  res = rtl_run_xsim(od, hdlsrc, 'sens', m.K, 500);
  assert(res.nMismatch >= 1, ['SENSIBILITA FALLITA: 1 LSB corrotto ma A-1 vede 0 mismatch -> ' ...
         'il cancello e'' CIECO.']);
  fprintf('=== SENSIBILITA A-1 OK: 1 LSB corrotto -> nMismatch=%d (il cancello vede) ===\n', res.nMismatch);
end
