function gate_donatello_a1(skipBuild)
%  gate_donatello_a1(true) salta la ricostruzione della libreria (gia' fatta): ~4 min in meno.
%GATE_DONATELLO_A1  Cancello del disaccoppiamento readout<->decode nel blocco Donatello standalone.
%  Il cambiamento sposta il decode di UN CLOCK (legge `rawl`, il readout latchato, invece di `raw`).
%  La funzione e' invariata per costruzione -- ma "per costruzione" NON e' un cancello: qui si prova
%  sui DATI, su traiettoria reale, che la sequenza di parametri sia identica al riferimento.
  here = fileparts(mfilename('fullpath')); cd(here);
  if nargin < 1 || isempty(skipBuild), skipBuild = false; end

  if ~skipBuild
      fprintf('=== GATE: rigenero la libreria col disaccoppiamento ===\n');
      build_hdl_variants();
  end

  % ⚠️ HOLD ESPLICITO 500. Il default di run_block_traj_test e' 400 e la latenza del blocco era
  % ESATTAMENTE 400: margine zero. Il disaccoppiamento aggiunge +1 clock -> 401 -> il cancello
  % falliva su codice CORRETTO ("hold=400 < latenza=401"). E' lo stesso difetto gia' registrato
  % nell'audit per i cancelli SP2: un default tarato sul filo non e' un default.
  HOLD = 500;

  fprintf('=== GATE: traiettoria reale, blocco Donatello_LUT64 (hold=%d) ===\n', HOLD);
  ok = true;
  for tr = [1 7 23]
      dmax = run_block_traj_test(40, 'Donatello_LUT64', HOLD, tr);
      fprintf('GATE-TRAJ traj=%-3d dmax = %.6g\n', tr, dmax);
      if ~(dmax == 0), ok = false; end
  end

  if ok
      fprintf('GATE-OK bit-exact su tutte le traiettorie provate\n');
  else
      fprintf('GATE-FALLITO almeno una traiettoria diverge\n');
  end
end
