function res = run_rtl_validate(harness, trajList, mode)
%RUN_RTL_VALIDATE  [Fase B2.0-2a] Orchestratore Harness A: genera il golden FEDELE al blocco, i vettori,
%  invoca xsim, fa il parse di RTLRES e assert-a il cancello A-1 (RTL == blocco, bit-exact).
%    res = run_rtl_validate('snn', [1 7 23], 'reduced')
%  Cancello A-1: nMismatch == 0. Prova di sensibilita' a se': sensitivity_A1 (1 LSB -> deve fallire).
  if nargin < 1 || isempty(harness),  harness  = 'snn'; end
  if nargin < 2 || isempty(trajList), trajList = [1 7 23]; end
  if nargin < 3 || isempty(mode),     mode     = 'reduced'; end
  assert(strcmp(harness,'snn'), 'Milestone 1: solo harness ''snn''');
  here = fileparts(mfilename('fullpath'));
  build_champion_golden();                                   % golden fedele (estrae + codegen se serve)
  hdlsrc = fullfile(here,'hdlsrc_donatello_champion','rtlgen_mdl');
  if ~exist(fullfile(hdlsrc,'Donatello_Champion.vhd'),'file')
    info = rtl_gen_dut('Donatello_Champion'); hdlsrc = info.outdir;
  end
  od = fullfile(here,'axi','champion');
  % PER-TRAIETTORIA: l'RTL in xsim non resetta lo stato ricorrente fra traiettorie, ma il golden lo
  % azzera (clear del MEX) a ogni traiettoria. Ogni traiettoria = un run xsim a se' (parte col reset).
  totMis = 0; totN = 0; firstbadTraj = -1;
  for t = trajList(:).'
    tag = sprintf('%s_t%d', mode, t);
    rtl_export_vectors('snn', t, tag, od);
    m = load(fullfile(od,['meta_' tag '.mat']));
    r = rtl_run_xsim(od, hdlsrc, tag, m.K, 500);
    totMis = totMis + r.nMismatch; totN = totN + r.n;
    if r.firstbad >= 0 && firstbadTraj < 0, firstbadTraj = t; end
    fprintf('  traj %-3d: nMismatch = %d / %d (firstbad=%d)\n', t, r.nMismatch, r.n, r.firstbad);
  end
  res = struct('nMismatch', totMis, 'n', totN, 'firstbadTraj', firstbadTraj);
  fprintf('A-1 [%s]: nMismatch = %d / %d su %d traiettorie x 1000 x 5 param\n', ...
          mode, totMis, totN, numel(trajList));
  assert(totMis == 0, ['A-1 FALLITO: il VHDL del champion NON riproduce il blocco ' ...
         '(%d/%d disallineati, prima traj %d).'], totMis, totN, firstbadTraj);
  fprintf('=== A-1 PASSATO: Donatello_Champion RTL bit-exact al blocco su %d/%d ===\n', totN, totN);
end
