function check_split_f1()
% Fase 1 - due verifiche:
%   (A) NON-REGRESSIONE: archStyle='chart' deve dare lo STESSO comportamento di prima (dmax=0 basta,
%       la conferma dell'Fmax=41,129 la da' la sintesi dopo). Prova che estrarre decode_phase_code
%       non ha rotto la chart unica.
%   (B) SPLIT: archStyle='split' costruisce ed e' bit-exact?
  HOLD = 600;
  for cfg = {{'chart','p3'}, {'split','p3'}}
    a = cfg{1}{1}; v = cfg{1}{2};
    fprintf('\n=== F1 arch=%s decode=%s ===\n', a, v);
    try
      build_hdl_variants(v, 'snn_variants/snn_b2_fsm_R5.m', 'shared', a);
      d = run_block_traj_test(40, 'Donatello_LUT64', HOLD, 1);
      fprintf('F1-GATE arch=%-6s dmax = %.6g\n', a, d);
    catch ME
      fprintf('F1-GATE arch=%-6s FALLITO: %s\n', a, ME.message);
    end
  end
end
