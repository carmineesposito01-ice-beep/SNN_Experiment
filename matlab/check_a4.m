function check_a4()
% Preflight [A4]: le due forme di init producono lo stesso comportamento? (shared = storico, perVar = nuovo)
% Il cancello competente per l'EQUIVALENZA e' dmax; quello per l'EFFETTO e' l'Fmax (sintesi, dopo).
  HOLD = 600;
  for st = {'shared','perVar'}
    s = st{1};
    fprintf('\n=== A4 initStyle=%s (decode p3) ===\n', s);
    try
      build_hdl_variants('p3', 'snn_variants/snn_b2_fsm_R5.m', s);
      dmax = run_block_traj_test(40, 'Donatello_LUT64', HOLD, 1);
      fprintf('A4-GATE %-7s dmax = %.6g\n', s, dmax);
    catch ME
      fprintf('A4-GATE %-7s FALLITO: %s\n', s, ME.message);
    end
  end
end
