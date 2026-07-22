function check_a2_variants()
%CHECK_A2_VARIANTS  Preflight [A2]: le tre varianti di decode si costruiscono? E il cancello sui dati
%  resta verde per ciascuna? Si prova PRIMA di lanciare la campagna, per non scoprire dopo un'ora che
%  una variante non compila.
%
%  ⚠️ Il cancello sui DATI non vede se le fasi sono cablate nell'ordine sbagliato (stessi valori, solo
%  disponibili prima): quello lo vede la SINTESI. Qui si prova che (a) costruisce, (b) e' bit-exact.
%  La latenza cresce con le fasi -> hold esplicito ampio.
  here = fileparts(mfilename('fullpath')); cd(here);
  HOLD = 600;                      % > latenza anche con 5 fasi (era 401 con 1 fase)
  vars = {'fused','p3','p5'};
  ok = true;
  for i = 1:numel(vars)
      v = vars{i};
      fprintf('\n=== A2-CHECK variante %s ===\n', v);
      try
          build_hdl_variants(v);
          fprintf('A2-BUILD %-6s OK\n', v);
      catch ME
          fprintf('A2-BUILD %-6s FALLITO: %s\n', v, ME.message);
          ok = false; continue
      end
      try
          dmax = run_block_traj_test(40, 'Donatello_LUT64', HOLD, 1);
          fprintf('A2-GATE  %-6s dmax = %.6g\n', v, dmax);
          if ~(dmax == 0), ok = false; end
      catch ME
          fprintf('A2-GATE  %-6s FALLITO: %s\n', v, ME.message);
          ok = false;
      end
  end
  if ok
      fprintf('\nA2-CHECK-OK tutte e tre le varianti costruiscono e sono bit-exact\n');
  else
      fprintf('\nA2-CHECK-FALLITO almeno una variante ha problemi\n');
  end
end
