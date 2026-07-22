function check_a3()
% Preflight [A3]: (a) decode_c ricomposta e' bit-exact? (b) la variante p6 costruisce ed e' bit-exact?
% HOLD ampio: p6 ha 6 fasi -> latenza maggiore (fused 401, p3 403, p5 405, p6 attesa 406).
  HOLD = 600;
  for v = {'fused','p6'}
    vv = v{1};
    fprintf('\n=== A3 variante %s ===\n', vv);
    try
      build_hdl_variants(vv);
      dmax = run_block_traj_test(40, 'Donatello_LUT64', HOLD, 1);
      fprintf('A3-GATE %-6s dmax = %.6g\n', vv, dmax);
    catch ME
      fprintf('A3-GATE %-6s FALLITO: %s\n', vv, ME.message);
    end
  end
end
