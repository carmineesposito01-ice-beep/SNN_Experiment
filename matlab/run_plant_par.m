function res = run_plant_par(trajList)
%RUN_PLANT_PAR  [Fase B2.0-2a-M2 B.2] Cancello PLANT-PAR: il plant EGO riprodotto nel testbench Verilog
%  (real) == il plant di riferimento (cl_ref_acciidm_m), fed la stessa accel, SENZA RTL. Se combacia
%  bit-exact, il plant-nel-TB e' fedele -> l'anello live puo' fidarsene. Prova di sensibilita': con SENS
%  (dv = ve invece di ve_prev) DEVE divergere. E' l'anti-divergenza: plant e controllore verificati SEPARATI.
  if nargin < 1 || isempty(trajList), trajList = [1 7 23]; end
  here = fileparts(mfilename('fullpath'));
  build_acciidm_m_golden();
  od = fullfile(here,'axi','acciidm_m');
  totMis = 0; totN = 0;
  for t = trajList(:).'
    K = cl_export_plant_par(t, 200, 500, od);
    r = run_pp(od, K, '');
    totMis = totMis + r.nMismatch; totN = totN + r.n;
    fprintf('  traj %-3d: PLANT-PAR nMismatch = %d / %d (firstbad=%d)\n', t, r.nMismatch, r.n, r.firstbad);
  end
  res = struct('nMismatch', totMis, 'n', totN);
  assert(totMis == 0, 'PLANT-PAR FALLITO: il plant-nel-TB != riferimento (%d/%d)', totMis, totN);
  fprintf('=== PLANT-PAR PASSATO: plant-nel-TB == riferimento su %d/%d ===\n', totN, totN);
  % sensibilita: con SENS (dv sbagliato) deve fallire
  K = cl_export_plant_par(trajList(1), 200, 500, od);
  rs = run_pp(od, K, 'sens');
  assert(rs.nMismatch >= 1, 'SENSIBILITA PLANT-PAR FALLITA: SENS non diverge -> cancello CIECO');
  fprintf('=== SENSIBILITA PLANT-PAR OK: ve_prev->ve -> nMismatch=%d ===\n', rs.nMismatch);
end

function r = run_pp(od, K, sens)
  [~, out] = system(['cd /d "' od '" && bash run_xsim_plant_par.sh ' num2str(K) ' ' sens]);
  tok = regexp(out, 'RTLRES nMismatch=(\d+) n=(\d+) firstbad=(-?\d+)', 'tokens', 'once');
  assert(~isempty(tok), 'xsim non ha prodotto RTLRES. Output:\n%s', out);
  r = struct('nMismatch', str2double(tok{1}), 'n', str2double(tok{2}), 'firstbad', str2double(tok{3}));
end
