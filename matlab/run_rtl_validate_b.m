function res = run_rtl_validate_b(trajList, mode)
%RUN_RTL_VALIDATE_B  [Fase B2.0-2a-M2] Orchestratore Harness B open-loop: golden FEDELE (accel) del
%  controllore, vettori, xsim, cancello B-1 (RTL accel == blocco). Per-traiettoria (reset RTL fra traj).
%    res = run_rtl_validate_b([1 7 23], 'reduced')
%  Cancello B-1: nMismatch == 0. Sensibilita' a se': sensitivity_B1.
  if nargin < 1 || isempty(trajList), trajList = [1 7 23]; end
  if nargin < 2 || isempty(mode),     mode     = 'reduced'; end
  here = fileparts(mfilename('fullpath'));
  build_acciidm_m_golden();                                  % golden fedele accel (estrae + codegen)
  % DUT in VERILOG (registri init a 0: il divisore combinatorio dell'IIDM manderebbe un indice a -1 a
  % time-0 in xsim col VHDL, che parte U -> metavalue). La SNN (M1) resta VHDL.
  hdlsrc = fullfile(here,'hdlsrc_donatello_acc_iidm_m_v','rtlgen_mdl');
  if ~exist(fullfile(hdlsrc,'Donatello_ACC_IIDM_M.v'),'file')
    info = rtl_gen_dut('Donatello_ACC_IIDM_M', [], 'Verilog'); hdlsrc = info.outdir;
  end
  od = fullfile(here,'axi','acciidm_m');
  totMis = 0; totN = 0; firstbadTraj = -1;
  for t = trajList(:).'
    tag = sprintf('%s_t%d', mode, t);
    rtl_export_vectors('ctrl', t, tag, od);
    m = load(fullfile(od,['meta_' tag '.mat']));
    r = rtl_run_xsim(od, hdlsrc, tag, m.K, 500, 'run_xsim_acciidm_m.sh');
    totMis = totMis + r.nMismatch; totN = totN + r.n;
    if r.firstbad >= 0 && firstbadTraj < 0, firstbadTraj = t; end
    fprintf('  traj %-3d: nMismatch = %d / %d (firstbad=%d)\n', t, r.nMismatch, r.n, r.firstbad);
  end
  res = struct('nMismatch', totMis, 'n', totN, 'firstbadTraj', firstbadTraj);
  fprintf('B-1 [%s]: nMismatch = %d / %d su %d traiettorie x 1000 (accel)\n', mode, totMis, totN, numel(trajList));
  assert(totMis == 0, ['B-1 FALLITO: il VHDL del controllore NON riproduce il blocco ' ...
         '(%d/%d disallineati, prima traj %d).'], totMis, totN, firstbadTraj);
  fprintf('=== B-1 PASSATO: Donatello_ACC_IIDM_M RTL bit-exact al blocco su %d/%d (accel) ===\n', totN, totN);
end
