function res = run_closed_loop(trajList)
%RUN_CLOSED_LOOP  [Fase B2.0-2a-M2 B.2] Anello LIVE: controllore RTL <-> plant nel TB, retroazione su accel.
%  Cancelli: B-LOOP (traiettoria RTL == riferimento cl_ref_acciidm_m, dmax=0) e BEHAV (gap sempre > 0,
%  nessuna collisione). Prerequisiti gia' verdi: B-1 (controllore RTL == blocco) e PLANT-PAR (plant fedele)
%  -> se qui diverge, la colpa e' solo nell'integrazione (conversioni/timing), superficie stretta.
  if nargin < 1 || isempty(trajList), trajList = [1 7 23]; end
  here = fileparts(mfilename('fullpath'));
  build_acciidm_m_golden();
  hdlsrc = fullfile(here,'hdlsrc_donatello_acc_iidm_m_v','rtlgen_mdl');
  if ~exist(fullfile(hdlsrc,'Donatello_ACC_IIDM_M.v'),'file')
    info = rtl_gen_dut('Donatello_ACC_IIDM_M', [], 'Verilog'); hdlsrc = info.outdir;
  end
  od = fullfile(here,'axi','acciidm_m');
  totMis = 0; totN = 0; totGap = 0; firstbadTraj = -1;
  for t = trajList(:).'
    K = cl_export_plant_par(t, 200, 500, od);
    r = run_cl(od, hdlsrc, K, 500);
    totMis = totMis + r.nMismatch; totN = totN + r.n; totGap = totGap + r.gap_bad;
    if r.firstbad >= 0 && firstbadTraj < 0, firstbadTraj = t; end
    fprintf('  traj %-3d: B-LOOP nMismatch = %d / %d (firstbad=%d) | BEHAV gap<=0: %d\n', ...
            t, r.nMismatch, r.n, r.firstbad, r.gap_bad);
  end
  res = struct('nMismatch', totMis, 'n', totN, 'gap_bad', totGap);
  assert(totMis == 0, 'B-LOOP FALLITO: anello RTL != riferimento (%d/%d, prima traj %d)', totMis, totN, firstbadTraj);
  assert(totGap == 0, 'BEHAV FALLITO: collisione nell''anello RTL (gap<=0 in %d control-step)', totGap);
  fprintf('=== B-LOOP + BEHAV PASSATI: anello RTL == riferimento su %d/%d, gap sempre > 0 ===\n', totN, totN);
end

function r = run_cl(od, hdlsrc, K, HOLD)
  [~, out] = system(['cd /d "' od '" && bash run_xsim_closed.sh "' strrep(hdlsrc,'\','/') '" ' ...
                     num2str(K) ' ' num2str(HOLD)]);
  tok = regexp(out, 'RTLRES nMismatch=(\d+) n=(\d+) firstbad=(-?\d+) gap_bad=(\d+)', 'tokens', 'once');
  assert(~isempty(tok), 'xsim non ha prodotto RTLRES. Output:\n%s', out);
  r = struct('nMismatch', str2double(tok{1}), 'n', str2double(tok{2}), ...
             'firstbad', str2double(tok{3}), 'gap_bad', str2double(tok{4}));
end
